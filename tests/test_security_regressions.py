import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.access_control import ManagedUserForm, create_managed_user
from app.auth import is_login_rate_limited
from app.database import get_connection, get_master_connection
from app.models import (
    create_budget_entry,
    get_all_budget_entries,
    get_budget_entry_by_id,
    get_login_session_owner,
    get_user_by_id,
    upsert_user_login_session,
)
from config import Config


class SecurityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.original_config = {
            "DATABASE_NAME": Config.DATABASE_NAME,
            "ENV": Config.ENV,
            "DEBUG": Config.DEBUG,
            "SECRET_KEY": Config.SECRET_KEY,
            "SESSION_COOKIE_SECURE": Config.SESSION_COOKIE_SECURE,
            "REMEMBER_COOKIE_SECURE": Config.REMEMBER_COOKIE_SECURE,
        }
        self.original_admin_username = os.environ.get("ADMIN_USERNAME")
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "security.db")
        Config.ENV = "testing"
        Config.DEBUG = False
        Config.SECRET_KEY = "test-secret-key"
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "AdminPass-2026"
        with patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": "false"}):
            self.app = create_app()
        self.app.config.update(
            TESTING=True,
            USER_DATABASE_DIR=str(Path(self.temp_dir.name) / "user_databases"),
            WTF_CSRF_ENABLED=False,
        )

    def tearDown(self):
        for key, value in self.original_config.items():
            setattr(Config, key, value)
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
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            return int(row["id"])
        finally:
            conn.close()

    def _login(self, client, user_id, csrf_token="test-token", session_key=None):
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
            session["_csrf_token"] = csrf_token
            if session_key:
                session["account_current_session_key"] = session_key

    def _create_managed_user(self, username, permissions):
        with self.app.app_context():
            return create_managed_user(
                ManagedUserForm(
                    username=username,
                    display_name=username.title(),
                    password="ManagedPass-2026",
                    permissions=set(permissions),
                ),
                created_by_user_id=self._user_id("admin"),
            )

    def test_idor_managed_user_cannot_open_admin_budget_record_by_guessing_id(self):
        create_budget_entry("Income", "January", "Admin private", 1000)
        admin_entry_id = get_all_budget_entries()[0]["id"]
        user_id = self._create_managed_user("budget_user", {"budget"})

        with self.app.test_client() as client:
            self._login(client, user_id)
            response = client.get(f"/budget/edit/{admin_entry_id}")

        self.assertIn(response.status_code, {302, 404})
        if response.status_code == 302:
            self.assertEqual(response.headers["Location"], "/budget/manage")

    def test_idor_managed_user_delete_by_guessed_admin_id_does_not_touch_admin_data(self):
        create_budget_entry("Income", "January", "Admin private", 1000)
        admin_entry_id = get_all_budget_entries()[0]["id"]
        user_id = self._create_managed_user("budget_editor", {"budget"})

        with self.app.test_client() as client:
            self._login(client, user_id)
            response = client.post(
                f"/budget/delete/{admin_entry_id}",
                data={"_csrf_token": "test-token"},
            )

        self.assertIn(response.status_code, {302, 404})
        self.assertIsNotNone(get_budget_entry_by_id(admin_entry_id))

    def test_managed_user_without_user_admin_rights_cannot_create_accounts(self):
        user_id = self._create_managed_user("budget_only", {"budget"})

        with self.app.test_client() as client:
            self._login(client, user_id)
            response = client.post(
                "/account/settings/users/create",
                data={
                    "_csrf_token": "test-token",
                    "username": "attacker-created",
                    "password": "AttackerPass-2026",
                    "permissions": ["budget"],
                },
            )

        self.assertEqual(response.status_code, 302)
        with self.assertRaises(TypeError):
            self._user_id("attacker-created")

    def test_csrf_missing_token_blocks_destructive_budget_request(self):
        create_budget_entry("Income", "January", "Protected", 1000)
        admin_id = self._user_id("admin")

        with self.app.test_client() as client:
            self._login(client, admin_id)
            with client.session_transaction() as session:
                session.pop("_csrf_token")
            response = client.post("/budget/delete-all")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(get_all_budget_entries()), 1)

    def test_csrf_mismatched_token_blocks_destructive_budget_request(self):
        create_budget_entry("Income", "January", "Protected", 1000)
        admin_id = self._user_id("admin")

        with self.app.test_client() as client:
            self._login(client, admin_id, csrf_token="server-token")
            response = client.post(
                "/budget/delete-all",
                data={"_csrf_token": "attacker-token"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(get_all_budget_entries()), 1)

    def test_sql_injection_payload_in_budget_category_is_stored_as_data(self):
        admin_id = self._user_id("admin")
        payload = "x'); DROP TABLE users; --"

        with self.app.test_client() as client:
            self._login(client, admin_id)
            response = client.post(
                "/budget/manage",
                data={
                    "_csrf_token": "test-token",
                    "form_type": "add_entry",
                    "entry_type": "\u0414\u043e\u0445\u043e\u0434",
                    "month_name": "January",
                    "category": payload,
                    "amount": "100",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_all_budget_entries()[0]["category"], payload)
        self.assertIsNotNone(get_user_by_id(admin_id))

    def test_xss_payload_in_budget_category_is_escaped_in_budget_page(self):
        admin_id = self._user_id("admin")
        payload = '<script>alert("xss")</script>'
        create_budget_entry("Income", "January", payload, 100)

        with self.app.test_client() as client:
            self._login(client, admin_id)
            response = client.get("/budget/manage")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertNotIn(payload, body)
        self.assertIn("&lt;script&gt;", body)

    def test_avatar_upload_rejects_executable_extension_and_keeps_profile_clean(self):
        admin_id = self._user_id("admin")

        with self.app.test_client() as client:
            self._login(client, admin_id)
            response = client.post(
                "/account/settings/avatar",
                data={
                    "_csrf_token": "test-token",
                    "avatar_file": (BytesIO(b"<?php echo 'owned';"), "avatar.php"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual((get_user_by_id(admin_id).get("avatar_filename") or ""), "")

    def test_avatar_data_uri_rejects_non_image_mime_type(self):
        admin_id = self._user_id("admin")

        with self.app.test_client() as client:
            self._login(client, admin_id)
            response = client.post(
                "/account/settings/avatar",
                data={
                    "_csrf_token": "test-token",
                    "cropped_avatar_data": "data:text/html;base64,PHNjcmlwdD4=",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual((get_user_by_id(admin_id).get("avatar_filename") or ""), "")

    def test_login_rate_limit_blocks_repeated_password_guessing_by_username_and_ip(self):
        with self.app.test_client() as client:
            with client.session_transaction() as session:
                session["_csrf_token"] = "test-token"
            statuses = [
                client.post(
                    "/login",
                    data={
                        "_csrf_token": "test-token",
                        "username": "admin",
                        "password": f"wrong-{index}",
                    },
                    environ_base={"REMOTE_ADDR": "203.0.113.10"},
                ).status_code
                for index in range(6)
            ]

        self.assertEqual(statuses[:5], [401, 401, 401, 401, 401])
        self.assertEqual(statuses[5], 429)
        self.assertTrue(is_login_rate_limited("admin", "203.0.113.10"))

    def test_stolen_session_key_is_rejected_after_logout_all_devices(self):
        admin_id = self._user_id("admin")
        session_key = "stolen-session-key"
        upsert_user_login_session(
            session_key=session_key,
            user_id=admin_id,
            device="Desktop",
            browser="Chrome",
            ip_address="127.0.0.1",
            first_login_at="2099-01-01T10:00:00",
            last_seen_at="2099-01-01T10:00:00",
        )

        with self.app.test_client() as client:
            self._login(client, admin_id, session_key=session_key)
            logout_response = client.post(
                "/account/settings/logout-all",
                data={"_csrf_token": "test-token"},
            )
            followup_response = client.get("/budget")

        self.assertEqual(logout_response.status_code, 302)
        self.assertEqual(followup_response.status_code, 302)
        self.assertIn("/login", followup_response.headers["Location"])

    def test_user_cannot_deactivate_another_users_session_by_known_session_key(self):
        admin_id = self._user_id("admin")
        victim_id = self._create_managed_user("victim", {"budget"})
        attacker_id = self._create_managed_user("attacker", {"budget"})
        victim_session_key = "victim-known-session"
        upsert_user_login_session(
            session_key=victim_session_key,
            user_id=victim_id,
            device="Victim device",
            browser="Chrome",
            ip_address="127.0.0.1",
            first_login_at="2099-01-01T10:00:00",
            last_seen_at="2099-01-01T10:00:00",
        )
        upsert_user_login_session(
            session_key="attacker-current-session",
            user_id=attacker_id,
            device="Attacker device",
            browser="Firefox",
            ip_address="127.0.0.1",
            first_login_at="2099-01-01T10:00:00",
            last_seen_at="2099-01-01T10:00:00",
        )

        with self.app.test_client() as client:
            self._login(client, attacker_id, session_key="attacker-current-session")
            response = client.post(
                "/account/settings/logout-device",
                data={
                    "_csrf_token": "test-token",
                    "session_keys": victim_session_key,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_login_session_owner(victim_session_key)["is_active"], 1)
        self.assertIsNotNone(get_user_by_id(admin_id))

    def test_production_config_rejects_default_secret_key(self):
        Config.ENV = "production"
        Config.DEBUG = False
        Config.SECRET_KEY = "dev_secret_key_change_me"

        with self.assertRaises(RuntimeError):
            Config.validate_security_settings()

    def test_security_cookie_flags_are_enabled_when_configured(self):
        Config.SESSION_COOKIE_SECURE = True
        Config.REMEMBER_COOKIE_SECURE = True
        with patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": "false"}):
            app = create_app()

        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(app.config["REMEMBER_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["REMEMBER_COOKIE_SAMESITE"], "Lax")
        self.assertTrue(app.config["REMEMBER_COOKIE_SECURE"])

    def test_payload_size_limit_returns_413_before_route_mutates_state(self):
        self.assertLessEqual(self.app.config["MAX_CONTENT_LENGTH"], 8 * 1024 * 1024)

    def test_debug_mode_is_not_enabled_by_default(self):
        self.assertFalse(self.app.config["DEBUG"])


if __name__ == "__main__":
    unittest.main()
