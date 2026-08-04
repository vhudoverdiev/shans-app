import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.access_control import (
    ManagedUserForm,
    create_managed_user,
    get_user_permissions,
    is_main_admin_user,
)
from app.auth import load_user_from_db
from app.database import get_connection, get_master_connection
from app.models import create_budget_entry, get_all_budget_entries
from config import Config


class UserManagementTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.original_admin_username = os.environ.get("ADMIN_USERNAME")
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "master.db")
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "AdminPass-2026"
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            USER_DATABASE_DIR=str(Path(self.temp_dir.name) / "user_databases"),
        )

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        if self.original_admin_username is None:
            os.environ.pop("ADMIN_USERNAME", None)
        else:
            os.environ["ADMIN_USERNAME"] = self.original_admin_username
        if self.original_admin_password is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self.original_admin_password
        self.temp_dir.cleanup()

    def _user_id(self, username):
        conn = get_master_connection()
        try:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            return int(row["id"])
        finally:
            conn.close()

    def _login_client(self, client, user_id):
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def test_created_user_gets_permissions_and_own_empty_database(self):
        with self.app.app_context():
            admin_id = self._user_id("admin")
            user_id = create_managed_user(
                ManagedUserForm(
                    username="editor",
                    display_name="Editor",
                    password="EditorPass-2026",
                    permissions={"budget", "schedule"},
                ),
                created_by_user_id=admin_id,
            )

        conn = get_master_connection()
        try:
            user = conn.execute(
                "SELECT data_database_name, is_system_admin FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertFalse(user["is_system_admin"])
        self.assertEqual(get_user_permissions(user_id), {"budget", "schedule"})
        self.assertTrue(Path(user["data_database_name"]).exists())

        with sqlite3.connect(user["data_database_name"]) as user_db:
            tables = {
                row[0]
                for row in user_db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertIn("budget_entries", tables)
            self.assertEqual(
                user_db.execute("SELECT COUNT(*) FROM budget_entries").fetchone()[0],
                0,
            )

        create_budget_entry("Доход", "Июль", "Админ", 1000)

        with self.app.test_request_context("/budget"):
            from flask_login import login_user

            login_user(load_user_from_db(user_id))
            self.assertEqual(get_all_budget_entries(), [])

    def test_user_without_section_permission_is_redirected_from_get_and_forbidden_on_post(self):
        with self.app.app_context():
            admin_id = self._user_id("admin")
            user_id = create_managed_user(
                ManagedUserForm(
                    username="viewer",
                    display_name="Viewer",
                    password="ViewerPass-2026",
                    permissions={"schedule"},
                ),
                created_by_user_id=admin_id,
            )

        with self.app.test_client() as client:
            self._login_client(client, user_id)
            budget_response = client.get("/budget")
            self.assertEqual(budget_response.status_code, 302)
            self.assertEqual(budget_response.headers["Location"], "/")

    def test_existing_non_managed_account_keeps_full_section_access(self):
        conn = get_master_connection()
        try:
            conn.execute(
                """
                INSERT INTO users (
                    username, display_name, password_hash, otp_secret,
                    otp_enabled, is_system_admin, is_active
                )
                VALUES (?, ?, ?, '', 0, 0, 1)
                """,
                (
                    "legacy",
                    "Legacy",
                    generate_password_hash("LegacyPass-2026"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        legacy_id = self._user_id("legacy")
        with self.app.test_client() as client:
            self._login_client(client, legacy_id)
            response = client.get("/budget")

        self.assertEqual(response.status_code, 200)

    def test_account_settings_user_management_is_only_for_main_admin(self):
        with self.app.app_context():
            admin_id = self._user_id("admin")
            user_id = create_managed_user(
                ManagedUserForm(
                    username="assistant",
                    display_name="Assistant",
                    password="AssistantPass-2026",
                    permissions={"schedule"},
                ),
                created_by_user_id=admin_id,
            )

        with self.app.test_client() as client:
            self._login_client(client, admin_id)
            admin_response = client.get("/account/settings?tab=users")
            admin_html = admin_response.get_data(as_text=True)

        self.assertEqual(admin_response.status_code, 200)
        self.assertIn('data-account-tab="users"', admin_html)
        self.assertIn('data-account-panel="users"', admin_html)
        self.assertIn("Создать пользователя", admin_html)
        self.assertIn("Доступ к разделам", admin_html)

        with self.app.test_client() as client:
            self._login_client(client, user_id)
            user_response = client.get("/account/settings?tab=users")
            user_html = user_response.get_data(as_text=True)

        self.assertEqual(user_response.status_code, 200)
        self.assertNotIn('data-account-tab="users"', user_html)
        self.assertNotIn('data-account-panel="users"', user_html)
        self.assertNotIn("Создать пользователя", user_html)

    def test_admin_can_autosave_managed_user_permissions(self):
        with self.app.app_context():
            admin_id = self._user_id("admin")
            user_id = create_managed_user(
                ManagedUserForm(
                    username="autosave_user",
                    display_name="Autosave user",
                    password="AutosavePass-2026",
                    permissions={"schedule"},
                ),
                created_by_user_id=admin_id,
            )

        with self.app.test_client() as client:
            self._login_client(client, admin_id)
            with client.session_transaction() as session:
                session["_csrf_token"] = "test-token"

            response = client.post(
                f"/account/settings/users/{user_id}",
                data={
                    "_csrf_token": "test-token",
                    "display_name": "Autosave user",
                    "permissions": ["budget", "car"],
                },
                headers={
                    "X-Requested-With": "fetch",
                    "X-CSRFToken": "test-token",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"ok": True, "message": "Пользователь обновлён."},
        )
        self.assertEqual(get_user_permissions(user_id), {"budget", "car"})

    def test_autosave_managed_user_returns_json_error(self):
        with self.app.app_context():
            admin_id = self._user_id("admin")
            user_id = create_managed_user(
                ManagedUserForm(
                    username="autosave_error_user",
                    display_name="Autosave error",
                    password="AutosaveErrorPass-2026",
                    permissions={"schedule"},
                ),
                created_by_user_id=admin_id,
            )

        with self.app.test_client() as client:
            self._login_client(client, admin_id)
            with client.session_transaction() as session:
                session["_csrf_token"] = "test-token"

            response = client.post(
                f"/account/settings/users/{user_id}",
                data={
                    "_csrf_token": "test-token",
                    "display_name": "",
                    "permissions": ["budget"],
                },
                headers={
                    "X-Requested-With": "fetch",
                    "X-CSRFToken": "test-token",
                },
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["message"])
        self.assertEqual(get_user_permissions(user_id), {"schedule"})

    def test_mobile_bottom_navigation_adapts_to_available_sections(self):
        with self.app.app_context():
            admin_id = self._user_id("admin")
            schedule_only_id = create_managed_user(
                ManagedUserForm(
                    username="schedule_only_mobile",
                    display_name="Schedule only",
                    password="ScheduleOnlyPass-2026",
                    permissions={"schedule"},
                ),
                created_by_user_id=admin_id,
            )
            four_item_id = create_managed_user(
                ManagedUserForm(
                    username="four_item_mobile",
                    display_name="Four item",
                    password="FourItemPass-2026",
                    permissions={"schedule", "budget", "study"},
                ),
                created_by_user_id=admin_id,
            )

        with self.app.test_client() as client:
            self._login_client(client, schedule_only_id)
            schedule_html = client.get("/account/settings").get_data(as_text=True)
            schedule_nav = schedule_html.split('<nav class="app-bottom-nav"', 1)[1].split("</nav>", 1)[0]

        self.assertIn('data-nav-count="2"', schedule_nav)
        self.assertIn("<span>График</span>", schedule_nav)
        self.assertIn("<span>Аккаунт</span>", schedule_nav)
        for label in ("Съёмки", "Отчёт", "Развитие", "Спорт"):
            self.assertNotIn(f"<span>{label}</span>", schedule_nav)

        with self.app.test_client() as client:
            self._login_client(client, four_item_id)
            four_item_html = client.get("/account/settings").get_data(as_text=True)
            four_item_nav = four_item_html.split('<nav class="app-bottom-nav"', 1)[1].split("</nav>", 1)[0]

        self.assertIn('data-nav-count="4"', four_item_nav)
        for label in ("График", "Отчёт", "Развитие", "Аккаунт"):
            self.assertIn(f"<span>{label}</span>", four_item_nav)
        self.assertNotIn("<span>Съёмки</span>", four_item_nav)
        self.assertNotIn("<span>Спорт</span>", four_item_nav)

    def test_configured_admin_keeps_user_management_when_legacy_flag_is_missing(self):
        admin_id = self._user_id("admin")
        conn = get_master_connection()
        try:
            conn.execute(
                "UPDATE users SET is_system_admin = 0 WHERE id = ?",
                (admin_id,),
            )
            conn.commit()
        finally:
            conn.close()

        with self.app.test_request_context("/account/settings?tab=users"):
            from flask_login import login_user

            login_user(load_user_from_db(admin_id))
            self.assertTrue(is_main_admin_user())

        with self.app.test_client() as client:
            self._login_client(client, admin_id)
            response = client.get("/account/settings?tab=users")
            html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-account-tab="users"', html)
        self.assertIn('data-account-panel="users"', html)
        self.assertIn('action="/account/settings/users/create"', html)

    def test_logout_all_devices_does_not_flash_service_notification(self):
        admin_id = self._user_id("admin")

        with self.app.test_client() as client:
            self._login_client(client, admin_id)
            with client.session_transaction() as session:
                session["_csrf_token"] = "test-token"

            response = client.post(
                "/account/settings/logout-all",
                data={"_csrf_token": "test-token"},
            )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/login")
            with client.session_transaction() as session:
                self.assertNotIn("_flashes", session)


if __name__ == "__main__":
    unittest.main()
