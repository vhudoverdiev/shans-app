import tempfile
import unittest
from pathlib import Path

from werkzeug.security import check_password_hash

from app.database import get_connection
from config import Config
from create_admin import configure_admins


class CreateAdminTests(unittest.TestCase):
    def setUp(self):
        self._original_database_name = Config.DATABASE_NAME
        self._temporary_directory = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(
            Path(self._temporary_directory.name) / "create-admin-test.db"
        )

    def tearDown(self):
        Config.DATABASE_NAME = self._original_database_name
        self._temporary_directory.cleanup()

    def test_creates_main_admin_and_independent_import_password(self):
        result = configure_admins(
            "site_admin",
            "MainAdmin-2026",
            "ImportAdmin-2026",
        )

        self.assertEqual(result, "created")
        connection = get_connection()
        try:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ?",
                ("site_admin",),
            ).fetchone()
            import_setting = connection.execute(
                "SELECT value FROM app_settings WHERE key = 'system_password'"
            ).fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(user)
        self.assertTrue(check_password_hash(user["password_hash"], "MainAdmin-2026"))
        self.assertTrue(user["otp_secret"])
        self.assertEqual(user["otp_enabled"], 0)
        self.assertEqual(user["display_name"], "site_admin")
        self.assertEqual(user["is_system_admin"], 1)
        self.assertEqual(user["is_active"], 1)
        self.assertEqual(import_setting["value"], "ImportAdmin-2026")

    def test_updates_existing_admin_without_duplicate_and_closes_sessions(self):
        configure_admins("site_admin", "OldMain-2026", "OldImport-2026")
        connection = get_connection()
        try:
            user = connection.execute(
                "SELECT id, otp_secret FROM users WHERE username = ?",
                ("site_admin",),
            ).fetchone()
            original_otp_secret = user["otp_secret"]
            connection.execute(
                """
                INSERT INTO user_login_sessions (
                    session_key, user_id, device, browser, ip_address,
                    first_login_at, last_seen_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    "active-session",
                    user["id"],
                    "Desktop",
                    "Browser",
                    "127.0.0.1",
                    "2026-07-21T00:00:00",
                    "2026-07-21T00:00:00",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        result = configure_admins(
            "site_admin",
            "NewMain-2026",
            "NewImport-2026",
        )

        self.assertEqual(result, "updated")
        connection = get_connection()
        try:
            users = connection.execute(
                "SELECT * FROM users WHERE username = ?",
                ("site_admin",),
            ).fetchall()
            session = connection.execute(
                "SELECT is_active FROM user_login_sessions WHERE session_key = ?",
                ("active-session",),
            ).fetchone()
            import_setting = connection.execute(
                "SELECT value FROM app_settings WHERE key = 'system_password'"
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(len(users), 1)
        self.assertTrue(check_password_hash(users[0]["password_hash"], "NewMain-2026"))
        self.assertEqual(users[0]["otp_secret"], original_otp_secret)
        self.assertEqual(users[0]["is_system_admin"], 1)
        self.assertEqual(users[0]["is_active"], 1)
        self.assertEqual(session["is_active"], 0)
        self.assertEqual(import_setting["value"], "NewImport-2026")

    def test_rejects_short_or_reused_passwords_before_writing_database(self):
        with self.assertRaisesRegex(ValueError, "не менее 8"):
            configure_admins("site_admin", "short", "ImportAdmin-2026")

        with self.assertRaisesRegex(ValueError, "должны отличаться"):
            configure_admins("site_admin", "SamePassword", "SamePassword")

        self.assertFalse(Path(Config.DATABASE_NAME).exists())


if __name__ == "__main__":
    unittest.main()
