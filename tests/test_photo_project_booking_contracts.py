import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from flask import Flask
from flask_login import LoginManager

from app.database import get_connection
from app.planner import (
    create_booking,
    create_project,
    get_bookings_for_project,
    get_tasks_for_day,
    init_planner_db,
    planner_bp,
)
from config import Config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DATE = (date.today() + timedelta(days=7)).isoformat()


class PhotoProjectBookingContractTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temp_dir = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "photo-projects.db")
        init_planner_db()
        self.app = self._create_test_app()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_dir.cleanup()

    def _create_test_app(self):
        app = Flask(
            "photo-project-contract-tests",
            template_folder=str(PROJECT_ROOT / "app" / "templates"),
            static_folder=str(PROJECT_ROOT / "app" / "static"),
        )
        app.config.update(SECRET_KEY="test", TESTING=True, LOGIN_DISABLED=True)
        login_manager = LoginManager(app)

        @login_manager.user_loader
        def load_user(_user_id):
            return None
        app.register_blueprint(planner_bp)

        @app.context_processor
        def inject_csrf_token():
            return {"csrf_token": "test-token"}

        return app

    def _create_project(self, **overrides):
        values = {
            "title": "Studio mini day",
            "city": "City",
            "address": "Studio",
            "project_date": PROJECT_DATE,
            "start_time": "10:00",
            "end_time": "12:00",
        }
        values.update(overrides)
        return create_project(
            values["title"],
            values["city"],
            values["address"],
            values["project_date"],
            values["start_time"],
            values["end_time"],
        )

    def _post_booking(self, client, project_id, **overrides):
        data = {
            "client_name": "Client",
            "client_contact": "+70000000000",
            "booking_time": "10:00",
            "duration_minutes": "15",
            "makeup_start_time": "",
            "price": "1000",
            "prepayment": "300",
        }
        data.update(overrides)
        return client.post(f"/photo-projects/{project_id}/bookings/create", data=data)

    def test_booking_creates_calendar_task_with_payment_context(self):
        project_id = self._create_project(title="Portrait day")

        response = self._post_booking(
            self.app.test_client(),
            project_id,
            client_name="Anna",
            booking_time="10:15",
            price="5000",
            prepayment="1500",
        )

        self.assertEqual(response.status_code, 302)
        bookings = get_bookings_for_project(project_id)
        self.assertEqual(len(bookings), 1)
        self.assertEqual(bookings[0]["client_name"], "Anna")
        tasks = get_tasks_for_day(PROJECT_DATE, "personal")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], "Portrait day")
        self.assertEqual(tasks[0]["start_time"], "10:15")
        self.assertIn("Anna", tasks[0]["description"])

    def test_booking_rejects_overlapping_slot_and_keeps_existing_booking(self):
        project_id = self._create_project(start_time="10:00", end_time="11:00")
        create_booking(project_id, "First", "+70000000000", PROJECT_DATE, "10:15", 30, "", 1000, 0)

        response = self._post_booking(
            self.app.test_client(),
            project_id,
            client_name="Overlap",
            booking_time="10:30",
            duration_minutes="15",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(get_bookings_for_project(project_id)), 1)
        self.assertEqual(get_bookings_for_project(project_id)[0]["client_name"], "First")

    def test_booking_rejects_time_outside_project_window(self):
        project_id = self._create_project(start_time="10:00", end_time="11:00")

        response = self._post_booking(
            self.app.test_client(),
            project_id,
            booking_time="10:45",
            duration_minutes="30",
            makeup_start_time="10:30",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_bookings_for_project(project_id), [])

    def test_booking_requires_valid_contact_and_makeup_for_30_minutes(self):
        project_id = self._create_project()
        client = self.app.test_client()

        bad_contact_response = self._post_booking(
            client,
            project_id,
            client_contact="not a contact",
        )
        missing_makeup_response = self._post_booking(
            client,
            project_id,
            booking_time="10:30",
            duration_minutes="30",
            makeup_start_time="",
        )

        self.assertEqual(bad_contact_response.status_code, 302)
        self.assertEqual(missing_makeup_response.status_code, 302)
        self.assertEqual(get_bookings_for_project(project_id), [])

    def test_edit_booking_excludes_itself_from_overlap_check(self):
        project_id = self._create_project()
        booking_id = create_booking(
            project_id,
            "Client",
            "+70000000000",
            PROJECT_DATE,
            "10:00",
            15,
            "",
            1000,
            0,
        )

        response = self.app.test_client().post(
            f"/photo-projects/bookings/{booking_id}/edit",
            data={
                "client_name": "Client updated",
                "client_contact": "+70000000000",
                "booking_time": "10:00",
                "duration_minutes": "15",
                "makeup_start_time": "",
                "price": "1200",
                "prepayment": "200",
            },
        )

        self.assertEqual(response.status_code, 302)
        booking = get_bookings_for_project(project_id)[0]
        self.assertEqual(booking["client_name"], "Client updated")
        self.assertEqual(booking["price"], 1200)

    def test_deleting_project_removes_bookings_and_linked_tasks(self):
        project_id = self._create_project(title="Cleanup project")
        response = self._post_booking(
            self.app.test_client(),
            project_id,
            client_name="Cleanup client",
            booking_time="10:00",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(get_tasks_for_day(PROJECT_DATE, "personal")), 1)

        delete_response = self.app.test_client().post(f"/photo-projects/{project_id}/delete")

        self.assertEqual(delete_response.status_code, 302)
        conn = get_connection()
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS total FROM photo_projects").fetchone()["total"],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS total FROM photo_project_bookings").fetchone()["total"],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS total FROM schedule_tasks").fetchone()["total"],
                0,
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
