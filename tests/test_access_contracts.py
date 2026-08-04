import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.access_control import ManagedUserForm, create_managed_user
from app.database import get_connection, get_master_connection
from app.models import (
    create_budget_entry,
    create_scenario,
    create_shooting,
    get_all_budget_entries,
)
from app.planner import (
    CALENDAR_PERSONAL,
    CALENDAR_WORK,
    create_booking,
    create_project,
    create_task,
    get_tasks_for_day,
)
from config import Config


class SectionAccessContractTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.original_admin_username = os.environ.get("ADMIN_USERNAME")
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "access.db")
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "AdminPass-2026"
        with patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": "false"}):
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
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            return int(row["id"])
        finally:
            conn.close()

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

    def _login(self, client, user_id):
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
            session["_csrf_token"] = "test-token"

    def test_budget_bulk_and_export_endpoints_require_budget_permission(self):
        user_id = self._create_managed_user("schedule_only", {"schedule"})
        create_budget_entry("income", "July", "Salary", 1000)
        entry_id = get_all_budget_entries()[0]["id"]

        with self.app.test_client() as client:
            self._login(client, user_id)
            export_response = client.get("/budget/export")
            delete_response = client.post(
                f"/budget/delete/{entry_id}",
                data={"_csrf_token": "test-token"},
            )
            delete_selected_response = client.post(
                "/budget/delete-selected",
                data={"_csrf_token": "test-token", "selected_ids": str(entry_id)},
            )
            delete_all_response = client.post(
                "/budget/delete-all",
                data={"_csrf_token": "test-token"},
            )

        self.assertEqual(export_response.status_code, 302)
        self.assertEqual(export_response.headers["Location"], "/")
        self.assertEqual(delete_response.status_code, 403)
        self.assertEqual(delete_selected_response.status_code, 403)
        self.assertEqual(delete_all_response.status_code, 403)
        self.assertEqual(len(get_all_budget_entries()), 1)

    def test_reports_hub_only_shows_cards_for_granted_report_sections(self):
        budget_user_id = self._create_managed_user("budget_report_only", {"budget"})
        car_user_id = self._create_managed_user("car_report_only", {"car"})

        with self.app.test_client() as client:
            self._login(client, budget_user_id)
            budget_response = client.get("/reports")
            budget_html = budget_response.get_data(as_text=True)

        self.assertEqual(budget_response.status_code, 200)
        self.assertIn('href="/budget"', budget_html)
        self.assertIn("Бюджет", budget_html)
        self.assertNotIn('href="/car"', budget_html)
        self.assertNotIn("Машина", budget_html)

        with self.app.test_client() as client:
            self._login(client, car_user_id)
            car_response = client.get("/reports")
            car_html = car_response.get_data(as_text=True)

        self.assertEqual(car_response.status_code, 200)
        self.assertIn('href="/car"', car_html)
        self.assertIn("Машина", car_html)
        self.assertNotIn('href="/budget"', car_html)
        self.assertNotIn("Бюджет", car_html)

    def test_schedule_bulk_delete_endpoints_require_schedule_permission(self):
        user_id = self._create_managed_user("budget_only", {"budget"})
        create_task("Personal protected", "2026-07-21", calendar_type=CALENDAR_PERSONAL)
        create_task("Work protected", "2026-07-21", calendar_type=CALENDAR_WORK)
        personal_id = get_tasks_for_day("2026-07-21", CALENDAR_PERSONAL)[0]["id"]

        with self.app.test_client() as client:
            self._login(client, user_id)
            selected_response = client.post(
                "/planner.schedule/task/delete-selected",
                data={
                    "_csrf_token": "test-token",
                    "task_date": "2026-07-21",
                    "calendar_type": CALENDAR_PERSONAL,
                    "selected_ids": str(personal_id),
                },
            )
            all_response = client.post(
                "/planner.schedule/task/delete-all",
                data={
                    "_csrf_token": "test-token",
                    "task_date": "2026-07-21",
                    "calendar_type": CALENDAR_WORK,
                },
            )

        self.assertEqual(selected_response.status_code, 403)
        self.assertEqual(all_response.status_code, 403)
        self.assertEqual(len(get_tasks_for_day("2026-07-21", CALENDAR_PERSONAL)), 1)
        self.assertEqual(len(get_tasks_for_day("2026-07-21", CALENDAR_WORK)), 1)

    def test_photo_project_bulk_endpoints_require_photo_projects_permission(self):
        user_id = self._create_managed_user("shootings_only", {"shootings"})
        project_id = create_project(
            "Mini sessions",
            "City",
            "Studio",
            "2026-08-10",
            "10:00",
            "12:00",
        )
        booking_id = create_booking(
            project_id,
            "Client",
            "+70000000000",
            "2026-08-10",
            "10:00",
            15,
            "",
            1000,
            300,
        )

        with self.app.test_client() as client:
            self._login(client, user_id)
            project_selected_response = client.post(
                "/photo-projects/delete-selected",
                data={"_csrf_token": "test-token", "selected_ids": str(project_id)},
            )
            project_all_response = client.post(
                "/photo-projects/delete-all",
                data={"_csrf_token": "test-token"},
            )
            booking_selected_response = client.post(
                f"/photo-projects/{project_id}/bookings/delete-selected",
                data={"_csrf_token": "test-token", "selected_ids": str(booking_id)},
            )
            booking_all_response = client.post(
                f"/photo-projects/{project_id}/bookings/delete-all",
                data={"_csrf_token": "test-token"},
            )

        self.assertEqual(project_selected_response.status_code, 403)
        self.assertEqual(project_all_response.status_code, 403)
        self.assertEqual(booking_selected_response.status_code, 403)
        self.assertEqual(booking_all_response.status_code, 403)
        conn = get_connection()
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS total FROM photo_projects").fetchone()["total"],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS total FROM photo_project_bookings").fetchone()["total"],
                1,
            )
        finally:
            conn.close()

    def test_shooting_bulk_and_export_endpoints_require_shootings_permission(self):
        user_id = self._create_managed_user("photo_only", {"photo_projects"})
        future_id = create_shooting(
            "Future shoot",
            "Client",
            "2099-08-10",
            "10:00",
            1,
            "+70000000000",
            1000,
            100,
            "",
        )
        archived_id = create_shooting(
            "Archived shoot",
            "Client",
            "2000-01-10",
            "10:00",
            1,
            "+70000000000",
            1000,
            100,
            "",
        )

        with self.app.test_client() as client:
            self._login(client, user_id)
            export_response = client.get("/shootings/export/upcoming")
            future_selected_response = client.post(
                "/shootings/upcoming/delete-selected",
                data={"_csrf_token": "test-token", "selected_ids": str(future_id)},
            )
            future_all_response = client.post(
                "/shootings/upcoming/delete-all",
                data={"_csrf_token": "test-token"},
            )
            archive_selected_response = client.post(
                "/shootings/archive/delete-selected",
                data={"_csrf_token": "test-token", "selected_ids": str(archived_id)},
            )
            archive_all_response = client.post(
                "/shootings/archive/delete-all",
                data={"_csrf_token": "test-token"},
            )

        self.assertEqual(export_response.status_code, 302)
        self.assertEqual(export_response.headers["Location"], "/")
        self.assertEqual(future_selected_response.status_code, 403)
        self.assertEqual(future_all_response.status_code, 403)
        self.assertEqual(archive_selected_response.status_code, 403)
        self.assertEqual(archive_all_response.status_code, 403)
        conn = get_connection()
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS total FROM shootings").fetchone()["total"],
                2,
            )
        finally:
            conn.close()

    def test_scenario_bulk_and_export_endpoints_require_scenarios_permission(self):
        user_id = self._create_managed_user("photo_without_scenarios", {"photo_projects"})
        future_id = create_scenario("Future scenario", "2099-08-10", "Plan")
        archived_id = create_scenario("Archived scenario", "2000-01-10", "Old plan")

        with self.app.test_client() as client:
            self._login(client, user_id)
            export_response = client.get("/scenarios/export/upcoming")
            future_selected_response = client.post(
                "/scenarios/upcoming/delete-selected",
                data={"_csrf_token": "test-token", "selected_ids": str(future_id)},
            )
            future_all_response = client.post(
                "/scenarios/upcoming/delete-all",
                data={"_csrf_token": "test-token"},
            )
            archive_selected_response = client.post(
                "/scenarios/archive/delete-selected",
                data={"_csrf_token": "test-token", "selected_ids": str(archived_id)},
            )
            archive_all_response = client.post(
                "/scenarios/archive/delete-all",
                data={"_csrf_token": "test-token"},
            )

        self.assertEqual(export_response.status_code, 302)
        self.assertEqual(export_response.headers["Location"], "/")
        self.assertEqual(future_selected_response.status_code, 403)
        self.assertEqual(future_all_response.status_code, 403)
        self.assertEqual(archive_selected_response.status_code, 403)
        self.assertEqual(archive_all_response.status_code, 403)
        conn = get_connection()
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS total FROM scenarios").fetchone()["total"],
                2,
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
