import sqlite3
import tempfile
import unittest
from pathlib import Path

from config import Config
from app.database import init_db


class VkCleanupTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temporary_directory = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(
            Path(self.temporary_directory.name) / "vk-cleanup-test.db"
        )

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temporary_directory.cleanup()

    def test_init_db_removes_legacy_vk_settings_and_send_locks(self):
        conn = sqlite3.connect(Config.DATABASE_NAME)
        conn.execute(
            """
            CREATE TABLE vk_notification_settings (
                id INTEGER PRIMARY KEY,
                access_token TEXT,
                profile_url TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO vk_notification_settings (id, access_token, profile_url)
            VALUES (1, 'test-secret-token', 'https://vk.example/profile')
            """
        )
        conn.execute(
            """
            CREATE TABLE vk_daily_send_locks (
                send_date TEXT PRIMARY KEY
            )
            """
        )
        conn.execute(
            "INSERT INTO vk_daily_send_locks (send_date) VALUES ('2026-07-24')"
        )
        conn.commit()
        conn.close()

        init_db()

        conn = sqlite3.connect(Config.DATABASE_NAME)
        legacy_tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN ('vk_notification_settings', 'vk_daily_send_locks')
            ORDER BY name
            """
        ).fetchall()
        users_table = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'users'
            """
        ).fetchone()
        conn.close()

        self.assertEqual(legacy_tables, [])
        self.assertEqual(users_table, ("users",))


if __name__ == "__main__":
    unittest.main()
