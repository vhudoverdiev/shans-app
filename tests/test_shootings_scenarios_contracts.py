import tempfile
import unittest
from pathlib import Path

from app.database import get_connection, init_db
from app.models import (
    create_scenario,
    create_shooting,
    delete_scenario,
    delete_shooting,
    get_archived_scenarios,
    get_archived_shootings,
    get_nearest_scenario,
    get_nearest_shooting,
    get_scenario_by_id,
    get_scenarios_count,
    get_shooting_by_id,
    get_shootings_count,
    get_upcoming_scenarios,
    get_upcoming_shootings,
    toggle_scenario_status,
    update_scenario,
    update_shooting,
)
from config import Config


class ShootingsAndScenariosContractTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temp_dir = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "shootings-scenarios.db")
        init_db()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_dir.cleanup()

    def test_shootings_are_split_by_date_and_upcoming_are_sorted_by_time(self):
        late_id = create_shooting(
            "Late project",
            "Client B",
            "2099-08-10",
            "16:00",
            2,
            "+70000000001",
            1000,
            100,
            "",
        )
        early_id = create_shooting(
            "Early project",
            "Client A",
            "2099-08-10",
            "09:00",
            1.5,
            "+70000000002",
            2000,
            500,
            "",
        )
        archive_id = create_shooting(
            "Old project",
            "Client C",
            "2000-01-10",
            "11:00",
            1,
            "+70000000003",
            1000,
            1500,
            "",
        )

        upcoming = get_upcoming_shootings()
        archived = get_archived_shootings()

        self.assertEqual([item["id"] for item in upcoming], [early_id, late_id])
        self.assertEqual([item["id"] for item in archived], [archive_id])
        self.assertEqual(get_nearest_shooting()["id"], early_id)
        self.assertEqual(get_shootings_count(), 2)
        self.assertFalse(upcoming[0]["is_archive"])
        self.assertTrue(archived[0]["is_archive"])
        self.assertEqual(archived[0]["remaining_payment"], 0)

    def test_shooting_money_and_duration_are_normalized_for_display_contract(self):
        shooting_id = create_shooting(
            "Package project",
            "Client",
            "2099-08-10",
            "10:00",
            2.0,
            "+70000000000",
            5000.5,
            1500,
            "Bring props",
        )

        shooting = get_shooting_by_id(shooting_id)

        self.assertEqual(shooting["duration_hours"], 2)
        self.assertEqual(shooting["price_display"], 5000.5)
        self.assertEqual(shooting["prepayment_display"], 1500)
        self.assertEqual(shooting["remaining_display"], 3500.5)
        self.assertEqual(shooting["remaining_payment"], 3500.5)

    def test_update_and_delete_shooting_change_persisted_contract(self):
        shooting_id = create_shooting(
            "Initial",
            "Client",
            "2099-08-10",
            "10:00",
            1,
            "+70000000000",
            1000,
            100,
            "",
        )

        update_shooting(
            shooting_id,
            "Updated",
            "New Client",
            "2099-09-11",
            "12:30",
            3,
            "@client",
            3000,
            750,
            "Updated notes",
        )
        updated = get_shooting_by_id(shooting_id)
        delete_shooting(shooting_id)

        self.assertEqual(updated["project_name"], "Updated")
        self.assertEqual(updated["client_name"], "New Client")
        self.assertEqual(updated["shooting_time"], "12:30")
        self.assertEqual(updated["remaining_payment"], 2250)
        self.assertIsNone(get_shooting_by_id(shooting_id))

    def test_scenarios_sync_expired_items_to_archive_and_keep_future_work_active(self):
        past_id = create_scenario("Past scenario", "2000-01-10", "Old", "in_progress")
        future_id = create_scenario("Future scenario", "2099-08-10", "Plan", "in_progress")
        done_future_id = create_scenario("Done future", "2099-08-11", "Done", "done")

        upcoming = get_upcoming_scenarios()
        archived = get_archived_scenarios()
        past = get_scenario_by_id(past_id)

        self.assertEqual([item["id"] for item in upcoming], [future_id])
        self.assertEqual({item["id"] for item in archived}, {past_id, done_future_id})
        self.assertEqual(past["scenario_status"], "done")
        self.assertEqual(past["effective_status"], "done")
        self.assertTrue(past["is_archive"])
        self.assertEqual(get_nearest_scenario()["id"], future_id)
        self.assertEqual(get_scenarios_count(), 1)

    def test_scenario_status_toggle_moves_future_item_between_active_and_archive(self):
        scenario_id = create_scenario("Toggle scenario", "2099-08-10", "Plan", "in_progress")

        toggle_scenario_status(scenario_id)
        after_done = get_scenario_by_id(scenario_id)
        toggle_scenario_status(scenario_id)
        after_reopen = get_scenario_by_id(scenario_id)

        self.assertEqual(after_done["scenario_status"], "done")
        self.assertTrue(after_done["is_archive"])
        self.assertEqual(after_reopen["scenario_status"], "in_progress")
        self.assertFalse(after_reopen["is_archive"])

    def test_update_and_delete_scenario_change_persisted_contract(self):
        scenario_id = create_scenario("Initial", "2099-08-10", "Draft", "in_progress")

        update_scenario(scenario_id, "Updated", "2099-09-12", "Final text", "done")
        updated = get_scenario_by_id(scenario_id)
        delete_scenario(scenario_id)

        self.assertEqual(updated["title"], "Updated")
        self.assertEqual(updated["shooting_date"], "2099-09-12")
        self.assertEqual(updated["scenario_text"], "Final text")
        self.assertEqual(updated["scenario_status"], "done")
        self.assertIsNone(get_scenario_by_id(scenario_id))

    def test_missing_records_return_empty_contracts_without_crashing(self):
        self.assertIsNone(get_shooting_by_id(404))
        self.assertIsNone(get_scenario_by_id(404))
        self.assertIsNone(get_nearest_shooting())
        self.assertIsNone(get_nearest_scenario())

        conn = get_connection()
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS total FROM shootings").fetchone()["total"],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS total FROM scenarios").fetchone()["total"],
                0,
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
