import tempfile
import unittest
from pathlib import Path

from flask import Flask
from flask_login import LoginManager, UserMixin
from jinja2 import DictLoader

from config import Config
from app.workouts import (
    add_workout_result,
    build_workout_summary,
    delete_weight_entry,
    ensure_default_workout_plans,
    get_weight_entries,
    get_workout_plans,
    get_workout_results,
    init_workouts_db,
    upsert_weight_entry,
    workouts_bp,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestUser(UserMixin):
    def __init__(self, user_id):
        self.id = user_id


class WorkoutsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database_name = Config.DATABASE_NAME
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "workouts-test.db")
        init_workouts_db()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_dir.cleanup()

    def _create_app(self):
        app = Flask("workouts-tests")
        app.config.update(SECRET_KEY="test", TESTING=True)
        app.jinja_loader = DictLoader(
            {
                "workouts.html": (
                    "{{ plans|length }}|{{ workout_results|length }}|"
                    "{{ weight_entries|length }}|{{ summary.result_count }}"
                ),
            }
        )
        login_manager = LoginManager(app)

        @login_manager.user_loader
        def load_user(user_id):
            return TestUser(int(user_id))

        app.register_blueprint(workouts_bp)
        return app

    def _login(self, client, user_id=1):
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def test_default_plans_are_created_once_and_isolated_by_user(self):
        ensure_default_workout_plans(1)
        ensure_default_workout_plans(1)
        ensure_default_workout_plans(2)

        first_user_plans = get_workout_plans(1)
        second_user_plans = get_workout_plans(2)

        self.assertEqual(
            [plan["name"] for plan in first_user_plans],
            ["Тренировка 1", "Тренировка 2", "Тренировка 3"],
        )
        self.assertEqual(len(second_user_plans), 3)
        self.assertNotEqual(
            {plan["id"] for plan in first_user_plans},
            {plan["id"] for plan in second_user_plans},
        )

    def test_results_are_stored_with_plan_and_protected_by_owner(self):
        ensure_default_workout_plans(1)
        plan_id = get_workout_plans(1)[0]["id"]

        result_id = add_workout_result(
            1,
            plan_id,
            "Жим лёжа",
            "80 кг × 8",
            "2026-07-20",
            "Хорошая техника",
        )
        results = get_workout_results(1)

        self.assertGreater(result_id, 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["workout_name"], "Тренировка 1")
        self.assertEqual(results[0]["exercise"], "Жим лёжа")
        self.assertEqual(get_workout_results(2), [])
        with self.assertRaisesRegex(ValueError, "не найдена"):
            add_workout_result(2, plan_id, "Тяга", "50 кг × 10", "2026-07-20")

    def test_weight_entry_for_same_date_is_updated_and_summary_is_correct(self):
        upsert_weight_entry(1, "2026-07-01", 80.0, "Старт")
        upsert_weight_entry(1, "2026-07-10", 78.5, "")
        upsert_weight_entry(1, "2026-07-10", 78.2, "Уточнённое измерение")

        entries = get_weight_entries(1)
        summary = build_workout_summary([], entries)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[-1]["weight_kg"], 78.2)
        self.assertEqual(entries[-1]["notes"], "Уточнённое измерение")
        self.assertAlmostEqual(summary["total_change"], -1.8)
        self.assertEqual(summary["minimum_weight"], 78.2)
        self.assertTrue(delete_weight_entry(1, entries[-1]["id"]))
        self.assertFalse(delete_weight_entry(2, entries[0]["id"]))

    def test_route_seeds_plans_and_accepts_valid_result(self):
        app = self._create_app()
        client = app.test_client()
        self._login(client)

        response = client.get("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_data(as_text=True).startswith("3|0|0|0"))

        plan_id = get_workout_plans(1)[0]["id"]
        response = client.post(
            "/workouts/results",
            data={
                "workout_plan_id": str(plan_id),
                "exercise": "Приседания",
                "result": "3 × 12",
                "performed_on": "2026-07-20",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(get_workout_results(1)), 1)

    def test_invalid_weight_is_rejected_without_database_write(self):
        app = self._create_app()
        client = app.test_client()
        self._login(client)

        response = client.post(
            "/workouts/weight",
            data={
                "weight_kg": "not-a-number",
                "measured_on": "2026-07-20",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_weight_entries(1), [])

    def test_training_navigation_remains_mobile_only(self):
        base = (PROJECT_ROOT / "app" / "templates" / "base.html").read_text(
            encoding="utf-8"
        )
        index = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(
            encoding="utf-8"
        )
        desktop_grid, mobile_grid = index.split(
            '<div class="dashboard-grid dashboard-grid-mobile dashboard-primary-grid">',
            1,
        )
        top_nav, bottom_nav = base.split(
            '<nav class="app-bottom-nav" aria-label="Основная навигация">',
            1,
        )

        self.assertNotIn("url_for('workouts.index')", desktop_grid)
        self.assertIn("url_for('workouts.index')", mobile_grid)
        self.assertNotIn("url_for('workouts.index')", top_nav)
        self.assertIn("url_for('workouts.index')", bottom_nav)
        self.assertIn("<span>Спорт</span>", bottom_nav)


if __name__ == "__main__":
    unittest.main()
