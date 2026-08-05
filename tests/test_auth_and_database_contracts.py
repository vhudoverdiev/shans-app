import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

from app.auth import (
    clear_failed_logins,
    clear_failed_logins_for_username,
    is_login_rate_limited,
    register_failed_login,
    verify_user,
)
from app.database import get_connection, get_master_connection, init_db, use_database
from app.models import create_budget_entry, get_all_budget_entries, get_user_by_username
from config import Config


class AuthAndDatabaseContractTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.original_rate_limit_window = Config.LOGIN_RATE_LIMIT_WINDOW_SECONDS
        self.original_rate_limit_max = Config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
        self.temp_dir = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "master.db")
        Config.LOGIN_RATE_LIMIT_WINDOW_SECONDS = 900
        Config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 3
        init_db()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        Config.LOGIN_RATE_LIMIT_WINDOW_SECONDS = self.original_rate_limit_window
        Config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS = self.original_rate_limit_max
        self.temp_dir.cleanup()

    def _insert_user(self, username, password, is_active=1, is_system_admin=0):
        conn = get_master_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    username, display_name, password_hash, otp_secret,
                    otp_enabled, is_system_admin, is_active
                )
                VALUES (?, ?, ?, '', 0, ?, ?)
                """,
                (
                    username,
                    username.title(),
                    generate_password_hash(password),
                    is_system_admin,
                    is_active,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def test_verify_user_accepts_active_user_and_preserves_security_flags(self):
        user_id = self._insert_user("admin", "AdminPass-2026", is_system_admin=1)

        user = verify_user("admin", "AdminPass-2026")

        self.assertIsNotNone(user)
        self.assertEqual(int(user.id), user_id)
        self.assertEqual(user.username, "admin")
        self.assertTrue(user.is_system_admin)
        self.assertTrue(user.is_active)

    def test_verify_user_and_lookup_ignore_username_case(self):
        user_id = self._insert_user("vladimir", "AdminPass-2026", is_system_admin=1)

        user = verify_user("Vladimir", "AdminPass-2026")
        looked_up_user = get_user_by_username("VLADIMIR")

        self.assertIsNotNone(user)
        self.assertEqual(int(user.id), user_id)
        self.assertIsNotNone(looked_up_user)
        self.assertEqual(int(looked_up_user["id"]), user_id)

    def test_verify_user_rejects_wrong_password_and_inactive_account(self):
        self._insert_user("active", "ActivePass-2026")
        self._insert_user("disabled", "DisabledPass-2026", is_active=0)

        self.assertIsNone(verify_user("active", "wrong-password"))
        self.assertIsNone(verify_user("disabled", "DisabledPass-2026"))
        self.assertIsNone(verify_user("missing", "AnyPass-2026"))

    def test_login_rate_limit_is_scoped_by_username_and_ip(self):
        for _ in range(3):
            register_failed_login("Admin", "127.0.0.1")

        self.assertTrue(is_login_rate_limited("admin", "127.0.0.1"))
        self.assertTrue(is_login_rate_limited("ADMIN", "127.0.0.1"))
        self.assertFalse(is_login_rate_limited("admin", "10.0.0.1"))
        self.assertFalse(is_login_rate_limited("other", "127.0.0.1"))

    def test_login_rate_limit_ignores_attempts_outside_window(self):
        old_timestamp = (
            datetime.now(timezone.utc) - timedelta(seconds=901)
        ).isoformat()
        conn = get_master_connection()
        try:
            conn.execute(
                """
                INSERT INTO login_attempts (username, ip_address, attempted_at)
                VALUES (?, ?, ?)
                """,
                ("admin", "127.0.0.1", old_timestamp),
            )
            conn.commit()
        finally:
            conn.close()

        self.assertFalse(is_login_rate_limited("admin", "127.0.0.1"))

    def test_failed_login_cleanup_can_clear_single_ip_or_entire_username(self):
        register_failed_login("admin", "127.0.0.1")
        register_failed_login("admin", "10.0.0.1")
        register_failed_login("other", "127.0.0.1")

        clear_failed_logins("admin", "127.0.0.1")
        deleted_for_username = clear_failed_logins_for_username("admin")

        conn = get_master_connection()
        try:
            remaining = conn.execute(
                "SELECT username, ip_address FROM login_attempts ORDER BY username"
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(deleted_for_username, 1)
        self.assertEqual(
            [(row["username"], row["ip_address"]) for row in remaining],
            [("other", "127.0.0.1")],
        )

    def test_get_connection_rows_support_name_and_index_access(self):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT 'budget' AS section_key, 42 AS priority"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(row["section_key"], "budget")
        self.assertEqual(row[0], "budget")
        self.assertEqual(row["priority"], 42)
        self.assertEqual(row[1], 42)

    def test_use_database_isolates_user_data_and_restores_master_database(self):
        user_database = str(Path(self.temp_dir.name) / "user.db")
        init_db(user_database)
        create_budget_entry("income", "July", "Master", 1000)

        with use_database(user_database):
            self.assertEqual(get_all_budget_entries(), [])
            create_budget_entry("expense", "July", "User", 250)
            self.assertEqual(
                [row["category"] for row in get_all_budget_entries()],
                ["User"],
            )

        self.assertEqual(
            [row["category"] for row in get_all_budget_entries()],
            ["Master"],
        )


if __name__ == "__main__":
    unittest.main()
