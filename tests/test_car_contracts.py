import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.database import get_connection, get_master_connection, init_db
from app.models import (
    archive_car_notification,
    create_car_done_service,
    create_car_planned_service,
    create_car_planned_service_from_notification,
    delete_archived_car_notification,
    get_archived_car_notifications,
    get_car_done_service_by_id,
    get_car_done_services,
    get_car_last_mileage,
    get_car_planned_service_by_id,
    get_car_planned_services,
    get_car_total_spent,
    get_hidden_notification_keys,
    get_periodic_services_for_notifications,
    hide_car_notification,
    init_car_hidden_notifications_table,
    init_car_notification_archive,
    is_car_notification_hidden,
    move_planned_to_done,
    update_car_done_service,
    update_car_planned_service,
)
from config import Config


DONE_STATUS = "Выполнено"
SIX_MONTHS = "6 мес"
TWELVE_MONTHS = "12 мес"
IN_WORK = "В работе"
ONE_OFF = "Разовая"


class CarModelContractTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temp_dir = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "car.db")
        init_db()
        init_car_notification_archive()
        init_car_hidden_notifications_table()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_dir.cleanup()

    def test_done_services_are_sorted_by_mileage_and_totals_ignore_planned_work(self):
        create_car_done_service("Oil", 2500, 10000, "2026-01", "Engine oil", "", SIX_MONTHS)
        create_car_done_service("Tires", 9000, 35000, "2026-02", "Winter tires", "", "")
        create_car_planned_service("Future brake check", "Pads", "", TWELVE_MONTHS)

        done_services = get_car_done_services()

        self.assertEqual([row["service_name"] for row in done_services], ["Tires", "Oil"])
        self.assertEqual(get_car_total_spent(), 11500)
        self.assertEqual(get_car_last_mileage(), 35000)

    def test_update_services_preserves_status_and_changes_business_fields(self):
        create_car_done_service("Oil", 2500, 10000, "2026-01", "Old", "", SIX_MONTHS)
        create_car_planned_service("Brake check", "Old planned", "", TWELVE_MONTHS)

        update_car_done_service(
            1,
            service_name="Oil updated",
            service_cost=3000,
            mileage=12000,
            service_date="2026-03",
            detail_description="New",
            work_kind="",
            period_type=TWELVE_MONTHS,
            status=DONE_STATUS,
        )
        update_car_planned_service(
            1,
            service_name="Brake check updated",
            planned_cost=0,
            mileage=0,
            detail_description="New planned",
            work_kind="",
            period_type=SIX_MONTHS,
            status="planned",
        )

        done = get_car_done_service_by_id(1)
        planned = get_car_planned_service_by_id(1)
        self.assertEqual(done["service_name"], "Oil updated")
        self.assertEqual(done["service_cost"], 3000)
        self.assertEqual(done["mileage"], 12000)
        self.assertEqual(done["period_type"], TWELVE_MONTHS)
        self.assertEqual(planned["service_name"], "Brake check updated")
        self.assertEqual(planned["detail_description"], "New planned")
        self.assertEqual(planned["period_type"], SIX_MONTHS)

    def test_move_planned_to_done_is_atomic_and_returns_new_done_id(self):
        create_car_planned_service("Brake fluid", "Replace", "", "12 РјРµСЃ")

        done_id = move_planned_to_done(1, "2026-04")

        self.assertEqual(done_id, 1)
        self.assertIsNone(get_car_planned_service_by_id(1))
        done = get_car_done_service_by_id(done_id)
        self.assertEqual(done["service_name"], "Brake fluid")
        self.assertEqual(done["service_date"], "2026-04")
        self.assertEqual(done["status"], DONE_STATUS)
        self.assertIsNone(move_planned_to_done(404, "2026-04"))

    def test_notification_to_work_is_idempotent_for_same_active_work(self):
        first = create_car_planned_service_from_notification(
            "Cabin filter",
            "Replace filter",
            ONE_OFF,
            SIX_MONTHS,
        )
        second = create_car_planned_service_from_notification(
            "Cabin filter",
            "Replace filter",
            ONE_OFF,
            SIX_MONTHS,
        )

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(get_car_planned_services()), 1)
        self.assertEqual(get_car_planned_services()[0]["status"], IN_WORK)

    def test_notification_archive_and_hidden_keys_are_idempotent(self):
        archive_car_notification(
            "done:1:2026-01",
            title="Oil",
            status="need",
            period_type=SIX_MONTHS,
            detail_description="Old",
            last_service_date_text="January 2026",
            work_kind="",
        )
        archive_car_notification(
            "done:1:2026-01",
            title="Oil updated",
            status="need",
            period_type=TWELVE_MONTHS,
            detail_description="New",
            last_service_date_text="January 2026",
            work_kind="",
        )
        hide_car_notification("done:1:2026-01")
        hide_car_notification("done:1:2026-01")

        archived = get_archived_car_notifications()
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["title"], "Oil updated")
        self.assertEqual(archived[0]["period_type"], TWELVE_MONTHS)
        self.assertTrue(is_car_notification_hidden("done:1:2026-01"))
        self.assertEqual(get_hidden_notification_keys(), ["done:1:2026-01"])

        delete_archived_car_notification("done:1:2026-01")
        self.assertEqual(get_archived_car_notifications(), [])

    def test_periodic_notification_query_returns_only_supported_periods(self):
        create_car_done_service("Oil", 2500, 10000, "2026-01", "Engine oil", "", SIX_MONTHS)
        create_car_done_service("One-off wash", 500, 11000, "2026-02", "Wash", "", "")
        create_car_planned_service("Inspection", "Annual", "", TWELVE_MONTHS)
        create_car_planned_service("One-off detail", "Detail", "", "")

        planned, done = get_periodic_services_for_notifications()

        self.assertEqual([row["service_name"] for row in planned], ["Inspection"])
        self.assertEqual([row["service_name"] for row in done], ["Oil"])


class CarRouteContractTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.original_admin_username = os.environ.get("ADMIN_USERNAME")
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "car-routes.db")
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

    def test_car_manage_rejects_negative_done_values_without_writing(self):
        with self.app.test_client() as client:
            self._login(client)
            response = client.post(
                "/car/manage",
                data={
                    "_csrf_token": "test-token",
                    "service_name": "Oil",
                    "status": DONE_STATUS,
                    "service_date": "2026-01",
                    "mileage": "-1",
                    "cost": "2500",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._count_rows("car_done_services"), 0)
        self.assertEqual(self._count_rows("car_planned_services"), 0)

    def test_car_manage_creates_done_and_planned_records(self):
        with self.app.test_client() as client:
            self._login(client)
            done_response = client.post(
                "/car/manage",
                data={
                    "_csrf_token": "test-token",
                    "service_name": "Oil",
                    "status": DONE_STATUS,
                    "service_date": "2026-01",
                    "mileage": "10000",
                    "cost": "2500",
                    "detail_description": "Engine oil",
                    "period_type": SIX_MONTHS,
                },
            )
            planned_response = client.post(
                "/car/manage",
                data={
                    "_csrf_token": "test-token",
                    "service_name": "Inspection",
                    "status": "planned",
                    "detail_description": "Annual check",
                    "period_type": TWELVE_MONTHS,
                },
            )

        self.assertEqual(done_response.status_code, 302)
        self.assertEqual(planned_response.status_code, 302)
        self.assertEqual(get_car_done_services()[0]["service_name"], "Oil")
        self.assertEqual(get_car_planned_services()[0]["service_name"], "Inspection")

    def test_planned_complete_requires_date_and_then_moves_record_to_done(self):
        create_car_planned_service("Brake fluid", "Replace", "", TWELVE_MONTHS)

        with self.app.test_client() as client:
            self._login(client)
            missing_date = client.post(
                "/car/planned/complete/1",
                data={
                    "_csrf_token": "test-token",
                    "service_name": "Brake fluid",
                    "service_date": "",
                    "mileage": "12000",
                    "cost": "3000",
                    "period_type": TWELVE_MONTHS,
                },
            )
            completed = client.post(
                "/car/planned/complete/1",
                data={
                    "_csrf_token": "test-token",
                    "service_name": "Brake fluid",
                    "service_date": "2026-04",
                    "mileage": "12000",
                    "cost": "3000",
                    "period_type": TWELVE_MONTHS,
                },
            )

        self.assertEqual(missing_date.status_code, 302)
        self.assertEqual(completed.status_code, 302)
        self.assertEqual(self._count_rows("car_planned_services"), 0)
        done = get_car_done_services()[0]
        self.assertEqual(done["service_name"], "Brake fluid")
        self.assertEqual(done["service_date"], "2026-04")
        self.assertEqual(done["mileage"], 12000)

    def test_bulk_delete_selected_ignores_malformed_ids_and_deletes_valid_rows(self):
        create_car_done_service("Oil", 2500, 10000, "2026-01", "Engine oil", "", "")
        create_car_done_service("Tires", 9000, 35000, "2026-02", "Tires", "", "")
        create_car_planned_service("Inspection", "Annual", "", "")
        create_car_planned_service("Detail", "Detail", "", "")

        with self.app.test_client() as client:
            self._login(client)
            done_response = client.post(
                "/car/done/delete-selected",
                data={"_csrf_token": "test-token", "selected_ids": "bad,1,999"},
            )
            planned_response = client.post(
                "/car/planned/delete-selected",
                data={"_csrf_token": "test-token", "selected_ids": "bad,1,999"},
            )

        self.assertEqual(done_response.status_code, 302)
        self.assertEqual(planned_response.status_code, 302)
        self.assertEqual([row["service_name"] for row in get_car_done_services()], ["Tires"])
        self.assertEqual([row["service_name"] for row in get_car_planned_services()], ["Detail"])


if __name__ == "__main__":
    unittest.main()
