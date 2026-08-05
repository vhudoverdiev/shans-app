import os
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app
from app.bug_reports import build_bug_report_rate_limit_key, get_recent_bug_reports
from app.database import get_master_connection
from config import Config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BugReportTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.original_admin_username = os.environ.get("ADMIN_USERNAME")
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "master.db")
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "AdminPass-2026"
        self.app = create_app()
        self.app.config.update(TESTING=True)

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
            session["_csrf_token"] = "test-token"

    def test_bug_report_api_stores_current_user_report(self):
        admin_id = self._user_id("admin")
        with self.app.test_client() as client:
            self._login_client(client, admin_id)
            response = client.post(
                "/api/bug-reports",
                json={
                    "name": "Владимир",
                    "description": "Не открывается раздел питания.",
                    "page_url": "https://shansplanner.ru/nutrition",
                },
                headers={"X-CSRFToken": "test-token"},
                environ_overrides={"REMOTE_ADDR": "203.0.113.10"},
            )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.get_json()["ok"])

        reports = get_recent_bug_reports()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["user_id"], admin_id)
        self.assertEqual(reports[0]["name"], "Владимир")
        self.assertEqual(reports[0]["ip_address"], "203.0.113.10")

    def test_bug_report_api_limits_three_reports_per_network_per_day(self):
        admin_id = self._user_id("admin")
        with self.app.test_client() as client:
            self._login_client(client, admin_id)
            statuses = []
            for number, ip_address in enumerate(
                ["198.51.100.24", "198.51.100.25", "198.51.100.26", "198.51.100.250"]
            ):
                response = client.post(
                    "/api/bug-reports",
                    json={
                        "name": "Tester",
                        "description": f"Bug number {number}",
                    },
                    headers={"X-CSRFToken": "test-token"},
                    environ_overrides={"REMOTE_ADDR": ip_address},
                )
                statuses.append(response.status_code)

        self.assertEqual(statuses[:3], [201, 201, 201])
        self.assertEqual(statuses[3], 429)
        self.assertEqual(len(get_recent_bug_reports()), 3)
        self.assertEqual(
            build_bug_report_rate_limit_key("198.51.100.24"),
            build_bug_report_rate_limit_key("198.51.100.250"),
        )

    def test_bug_report_api_limits_three_reports_per_user_even_when_network_changes(self):
        admin_id = self._user_id("admin")
        with self.app.test_client() as client:
            self._login_client(client, admin_id)
            statuses = []
            for number, ip_address in enumerate(
                ["198.51.100.24", "198.51.101.24", "203.0.113.24", "203.0.114.24"]
            ):
                response = client.post(
                    "/api/bug-reports",
                    json={
                        "name": "Tester",
                        "description": f"Bug number {number}",
                    },
                    headers={"X-CSRFToken": "test-token"},
                    environ_overrides={"REMOTE_ADDR": ip_address},
                )
                statuses.append(response.status_code)

        self.assertEqual(statuses[:3], [201, 201, 201])
        self.assertEqual(statuses[3], 429)
        self.assertEqual(len(get_recent_bug_reports()), 3)

    def test_bug_reports_tab_is_visible_only_for_main_admin(self):
        admin_id = self._user_id("admin")
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
                    "viewer",
                    "Viewer",
                    generate_password_hash("ViewerPass-2026"),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        viewer_id = self._user_id("viewer")

        with self.app.test_client() as client:
            self._login_client(client, admin_id)
            admin_response = client.get("/account/settings?tab=errors")
            admin_html = admin_response.get_data(as_text=True)

        self.assertEqual(admin_response.status_code, 200)
        self.assertIn('data-account-tab="errors"', admin_html)
        self.assertIn('data-account-panel="errors"', admin_html)

        with self.app.test_client() as client:
            self._login_client(client, viewer_id)
            user_response = client.get("/account/settings?tab=errors")
            user_html = user_response.get_data(as_text=True)

        self.assertEqual(user_response.status_code, 200)
        self.assertNotIn('data-account-tab="errors"', user_html)
        self.assertNotIn('data-account-panel="errors"', user_html)

    def test_bug_report_button_uses_push_inbox_visibility_state(self):
        base_template = (PROJECT_ROOT / "app" / "templates" / "base.html").read_text(
            encoding="utf-8"
        )
        push_client = (PROJECT_ROOT / "app" / "static" / "js" / "push-inbox.js").read_text(
            encoding="utf-8"
        )
        bug_client = (PROJECT_ROOT / "app" / "static" / "js" / "bug-report.js").read_text(
            encoding="utf-8"
        )
        stylesheet = (PROJECT_ROOT / "app" / "static" / "css" / "style.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("js/bug-report.js", base_template)
        self.assertIn('id="bug-report-trigger"', base_template)
        self.assertIn('data-submit-url="{{ url_for(\'submit_bug_report\') }}"', base_template)
        self.assertIn("shans-push-inbox-floating-active", push_client)
        self.assertIn('document.querySelector("[data-bug-report-trigger]")', bug_client)
        self.assertIn('window.fetch(sheet.dataset.submitUrl', bug_client)
        self.assertIn("html.shans-push-inbox-floating-active .bug-report-trigger", stylesheet)


if __name__ == "__main__":
    unittest.main()
