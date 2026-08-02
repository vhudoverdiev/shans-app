import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.database import get_connection, get_master_connection
from app.models import create_scenario, create_shooting, get_scenario_by_id, get_shooting_by_id
from app.planner import get_tasks_for_day, upsert_task_for_scenario, upsert_task_for_shooting
from config import Config


class ShootingScenarioRouteTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.original_admin_username = os.environ.get("ADMIN_USERNAME")
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "routes.db")
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "AdminPass-2026"
        with patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": "false"}):
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

    def _admin_id(self):
        conn = get_master_connection()
        try:
            row = conn.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
            return int(row["id"])
        finally:
            conn.close()

    def _login(self, client):
        with client.session_transaction() as session:
            session["_user_id"] = str(self._admin_id())
            session["_fresh"] = True
            session["_csrf_token"] = "test-token"

    def _count_rows(self, table_name):
        conn = get_connection()
        try:
            return conn.execute(f"SELECT COUNT(*) AS total FROM {table_name}").fetchone()["total"]
        finally:
            conn.close()

    def test_shooting_create_route_validates_required_fields_without_writing(self):
        with self.app.test_client() as client:
            self._login(client)
            response = client.post(
                "/shootings/add",
                data={
                    "_csrf_token": "test-token",
                    "project_name": "",
                    "client_name": "Client",
                    "shooting_date": "2099-08-10",
                    "phone": "+70000000000",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count_rows("shootings"), 0)
        self.assertEqual(self._count_rows("schedule_tasks"), 0)

    def test_shooting_create_route_rejects_malformed_numbers_and_contact(self):
        with self.app.test_client() as client:
            self._login(client)
            bad_numbers = client.post(
                "/shootings/add",
                data={
                    "_csrf_token": "test-token",
                    "project_name": "Shoot",
                    "client_name": "Client",
                    "shooting_date": "2099-08-10",
                    "duration_hours": "two",
                    "phone": "+70000000000",
                    "price": "1000",
                    "prepayment": "100",
                },
            )
            bad_contact = client.post(
                "/shootings/add",
                data={
                    "_csrf_token": "test-token",
                    "project_name": "Shoot",
                    "client_name": "Client",
                    "shooting_date": "2099-08-10",
                    "duration_hours": "2",
                    "phone": "bad contact",
                    "price": "1000",
                    "prepayment": "100",
                },
            )

        self.assertEqual(bad_numbers.status_code, 200)
        self.assertEqual(bad_contact.status_code, 200)
        self.assertEqual(self._count_rows("shootings"), 0)
        self.assertEqual(self._count_rows("schedule_tasks"), 0)

    def test_shooting_create_edit_and_delete_routes_keep_schedule_in_sync(self):
        with self.app.test_client() as client:
            self._login(client)
            create_response = client.post(
                "/shootings/add",
                data={
                    "_csrf_token": "test-token",
                    "project_name": "Family shoot",
                    "client_name": "Anna",
                    "shooting_date": "2099-08-10",
                    "shooting_time": "10:30",
                    "duration_hours": "2",
                    "phone": "+70000000000",
                    "price": "5000",
                    "prepayment": "1500",
                    "notes": "Bring props",
                },
            )

        self.assertEqual(create_response.status_code, 302)
        shooting = get_shooting_by_id(1)
        task = get_tasks_for_day("2099-08-10")[0]
        self.assertEqual(shooting["project_name"], "Family shoot")
        self.assertEqual(task["title"], "Family shoot")
        self.assertEqual(task["start_time"], "10:30")
        self.assertIn("Anna", task["description"])
        self.assertIn("5000.0", task["description"])

        with self.app.test_client() as client:
            self._login(client)
            edit_response = client.post(
                "/shootings/1/edit",
                data={
                    "_csrf_token": "test-token",
                    "project_name": "Updated shoot",
                    "client_name": "Maria",
                    "shooting_date": "2099-09-11",
                    "shooting_time": "12:00",
                    "duration_hours": "3",
                    "phone": "@maria",
                    "price": "7000",
                    "prepayment": "2000",
                    "notes": "New notes",
                },
            )

        self.assertEqual(edit_response.status_code, 302)
        self.assertEqual(get_tasks_for_day("2099-08-10"), [])
        updated_task = get_tasks_for_day("2099-09-11")[0]
        self.assertEqual(updated_task["title"], "Updated shoot")
        self.assertEqual(updated_task["start_time"], "12:00")
        self.assertIn("Maria", updated_task["description"])

        with self.app.test_client() as client:
            self._login(client)
            delete_response = client.post(
                "/shootings/1/delete",
                data={"_csrf_token": "test-token"},
            )

        self.assertEqual(delete_response.status_code, 302)
        self.assertIsNone(get_shooting_by_id(1))
        self.assertEqual(self._count_rows("schedule_tasks"), 0)

    def test_scenario_create_route_validates_date_and_text_length_without_writing(self):
        with self.app.test_client() as client:
            self._login(client)
            bad_date = client.post(
                "/scenarios/add",
                data={
                    "_csrf_token": "test-token",
                    "title": "Scenario",
                    "shooting_date": "bad-date",
                    "scenario_text": "Plan",
                    "scenario_status": "in_progress",
                },
            )
            too_long = client.post(
                "/scenarios/add",
                data={
                    "_csrf_token": "test-token",
                    "title": "Scenario",
                    "shooting_date": "2099-08-10",
                    "scenario_text": "x" * 2001,
                    "scenario_status": "in_progress",
                },
            )

        self.assertEqual(bad_date.status_code, 200)
        self.assertEqual(too_long.status_code, 200)
        self.assertEqual(self._count_rows("scenarios"), 0)
        self.assertEqual(self._count_rows("schedule_tasks"), 0)

    def test_scenario_create_edit_toggle_and_delete_keep_schedule_in_sync(self):
        with self.app.test_client() as client:
            self._login(client)
            create_response = client.post(
                "/scenarios/add",
                data={
                    "_csrf_token": "test-token",
                    "title": "Wedding script",
                    "shooting_date": "2099-08-10",
                    "scenario_text": "Opening scene",
                    "scenario_status": "not-real",
                },
            )

        self.assertEqual(create_response.status_code, 302)
        scenario = get_scenario_by_id(1)
        task = get_tasks_for_day("2099-08-10")[0]
        self.assertEqual(scenario["scenario_status"], "in_progress")
        self.assertEqual(task["title"], "Wedding script")
        self.assertEqual(task["status"], "planned")

        with self.app.test_client() as client:
            self._login(client)
            edit_response = client.post(
                "/scenarios/1/edit",
                data={
                    "_csrf_token": "test-token",
                    "title": "Updated script",
                    "shooting_date": "2099-09-11",
                    "scenario_text": "Final scene",
                    "scenario_status": "done",
                },
            )

        self.assertEqual(edit_response.status_code, 302)
        self.assertEqual(get_tasks_for_day("2099-08-10"), [])
        updated_task = get_tasks_for_day("2099-09-11")[0]
        self.assertEqual(updated_task["title"], "Updated script")
        self.assertEqual(updated_task["description"], "Final scene")
        self.assertEqual(updated_task["status"], "done")

        with self.app.test_client() as client:
            self._login(client)
            toggle_response = client.post(
                "/scenarios/1/toggle-status",
                data={"_csrf_token": "test-token"},
            )

        self.assertEqual(toggle_response.status_code, 302)
        reopened_task = get_tasks_for_day("2099-09-11")[0]
        self.assertEqual(get_scenario_by_id(1)["scenario_status"], "in_progress")
        self.assertEqual(reopened_task["status"], "planned")

        with self.app.test_client() as client:
            self._login(client)
            delete_response = client.post(
                "/scenarios/1/delete",
                data={"_csrf_token": "test-token"},
            )

        self.assertEqual(delete_response.status_code, 302)
        self.assertIsNone(get_scenario_by_id(1))
        self.assertEqual(self._count_rows("schedule_tasks"), 0)

    def test_delete_missing_shooting_and_scenario_redirect_without_side_effects(self):
        create_shooting("Existing shoot", "Client", "2099-08-10", "10:00", 1, "+70000000000", 1, 0, "")
        upsert_task_for_shooting(1, "Existing shoot", "Client", "2099-08-10")
        create_scenario("Existing scenario", "2099-08-11", "Plan")
        upsert_task_for_scenario(1, "Existing scenario", "2099-08-11", "Plan")

        with self.app.test_client() as client:
            self._login(client)
            missing_shooting = client.post(
                "/shootings/404/delete",
                data={"_csrf_token": "test-token"},
            )
            missing_scenario = client.post(
                "/scenarios/404/delete",
                data={"_csrf_token": "test-token"},
            )

        self.assertEqual(missing_shooting.status_code, 302)
        self.assertEqual(missing_scenario.status_code, 302)
        self.assertEqual(self._count_rows("shootings"), 1)
        self.assertEqual(self._count_rows("scenarios"), 1)
        self.assertEqual(self._count_rows("schedule_tasks"), 2)


if __name__ == "__main__":
    unittest.main()
