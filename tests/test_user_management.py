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


if __name__ == "__main__":
    unittest.main()
