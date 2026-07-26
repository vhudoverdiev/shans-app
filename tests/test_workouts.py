import tempfile
import unittest
from datetime import date, timedelta
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
    get_workout_plan,
    get_weight_entries,
    get_workout_plans,
    get_workout_results,
    init_workouts_db,
    next_workout_date,
    sync_workout_plan_schedule,
    update_workout_plan,
    upsert_weight_entry,
    workouts_bp,
)
from app.database import get_connection
from app.planner import (
    CALENDAR_PERSONAL,
    get_tasks_for_range,
    init_planner_db,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKOUTS_STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "workouts.css"


class TestUser(UserMixin):
    def __init__(self, user_id):
        self.id = user_id


class WorkoutsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database_name = Config.DATABASE_NAME
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "workouts-test.db")
        init_planner_db()
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
                "workout_plan_detail.html": (
                    "{{ plan.name }}|{{ plan.weekday_label }}|"
                    "{{ workout_results|length }}"
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

    def test_weekly_plan_syncs_to_personal_schedule_without_duplicates(self):
        ensure_default_workout_plans(1)
        plan = get_workout_plans(1)[0]
        today = date.today()

        self.assertTrue(
            update_workout_plan(
                1,
                plan["id"],
                "Силовая пятница",
                "Разминка 10 минут\nЖим лёжа — 4 × 8\nЗаминка 5 минут",
                4,
            )
        )
        first_sync_count = sync_workout_plan_schedule(
            1,
            today,
            today + timedelta(days=70),
        )
        second_sync_count = sync_workout_plan_schedule(
            1,
            today,
            today + timedelta(days=70),
        )
        tasks = get_tasks_for_range(
            today.isoformat(),
            (today + timedelta(days=70)).isoformat(),
            CALENDAR_PERSONAL,
            user_id=1,
        )
        workout_tasks = [
            task for task in tasks if task["workout_plan_id"] == plan["id"]
        ]

        self.assertEqual(first_sync_count, 0)
        self.assertEqual(second_sync_count, 0)
        self.assertGreaterEqual(len(workout_tasks), 10)
        self.assertTrue(
            all(date.fromisoformat(task["task_date"]).weekday() == 4 for task in workout_tasks)
        )
        self.assertTrue(all(task["calendar_type"] == CALENDAR_PERSONAL for task in workout_tasks))
        self.assertTrue(all(task["task_type"] == "Тренировка" for task in workout_tasks))
        self.assertTrue(all(task["title"] == "Силовая пятница" for task in workout_tasks))

        conn = get_connection()
        try:
            duplicate_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM schedule_tasks
                WHERE workout_plan_id = ?
                GROUP BY workout_plan_id, task_date
                HAVING COUNT(*) > 1
                """,
                (plan["id"],),
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(duplicate_count, [])

    def test_changing_weekday_rebuilds_future_occurrences_and_keeps_status_on_text_edit(self):
        ensure_default_workout_plans(1)
        plan = get_workout_plans(1)[1]
        today = date.today()
        end_date = today + timedelta(days=70)

        update_workout_plan(1, plan["id"], "Тренировка среды", "Первый текст", 2)
        tasks = [
            task
            for task in get_tasks_for_range(
                today.isoformat(),
                end_date.isoformat(),
                CALENDAR_PERSONAL,
                user_id=1,
            )
            if task["workout_plan_id"] == plan["id"]
        ]
        self.assertTrue(all(date.fromisoformat(task["task_date"]).weekday() == 2 for task in tasks))

        first_task = tasks[0]
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE schedule_tasks SET status = 'done' WHERE id = ?",
                (first_task["id"],),
            )
            conn.commit()
        finally:
            conn.close()

        update_workout_plan(1, plan["id"], "Среда — спина", "Обновлённый текст", 2)
        preserved = get_tasks_for_range(
            first_task["task_date"],
            first_task["task_date"],
            CALENDAR_PERSONAL,
            user_id=1,
        )[0]
        self.assertEqual(preserved["status"], "done")
        self.assertEqual(preserved["title"], "Среда — спина")
        self.assertEqual(preserved["description"], "Обновлённый текст")

        update_workout_plan(1, plan["id"], "Пятница — спина", "Новый день", 4)
        moved_tasks = [
            task
            for task in get_tasks_for_range(
                today.isoformat(),
                end_date.isoformat(),
                CALENDAR_PERSONAL,
                user_id=1,
            )
            if task["workout_plan_id"] == plan["id"]
        ]
        self.assertTrue(moved_tasks)
        self.assertTrue(
            all(date.fromisoformat(task["task_date"]).weekday() == 4 for task in moved_tasks)
        )

    def test_new_schedule_does_not_backfill_history_and_can_be_disabled(self):
        ensure_default_workout_plans(1)
        plan = get_workout_plans(1)[0]
        today = date.today()

        update_workout_plan(
            1,
            plan["id"],
            "Weekly strength",
            "Detailed workout plan",
            today.weekday(),
        )
        sync_workout_plan_schedule(
            1,
            today - timedelta(days=30),
            today - timedelta(days=1),
        )

        conn = get_connection()
        try:
            historical_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM schedule_tasks
                WHERE workout_plan_id = ? AND task_date < ?
                """,
                (plan["id"], today.isoformat()),
            ).fetchone()["count"]
        finally:
            conn.close()
        self.assertEqual(historical_count, 0)

        update_workout_plan(
            1,
            plan["id"],
            "Weekly strength",
            "Detailed workout plan",
            None,
        )
        future_tasks = [
            task
            for task in get_tasks_for_range(
                today.isoformat(),
                (today + timedelta(days=70)).isoformat(),
                CALENDAR_PERSONAL,
                user_id=1,
            )
            if task["workout_plan_id"] == plan["id"]
        ]
        self.assertEqual(future_tasks, [])

    def test_workout_tasks_are_isolated_by_owner(self):
        ensure_default_workout_plans(1)
        ensure_default_workout_plans(2)
        first_plan = get_workout_plans(1)[0]
        second_plan = get_workout_plans(2)[0]
        target_weekday = date.today().weekday()

        update_workout_plan(1, first_plan["id"], "План первого", "Первый", target_weekday)
        update_workout_plan(2, second_plan["id"], "План второго", "Второй", target_weekday)
        target_date = date.today().isoformat()

        first_user_titles = {
            task["title"]
            for task in get_tasks_for_range(
                target_date,
                target_date,
                CALENDAR_PERSONAL,
                user_id=1,
            )
        }
        second_user_titles = {
            task["title"]
            for task in get_tasks_for_range(
                target_date,
                target_date,
                CALENDAR_PERSONAL,
                user_id=2,
            )
        }

        self.assertIn("План первого", first_user_titles)
        self.assertNotIn("План второго", first_user_titles)
        self.assertIn("План второго", second_user_titles)
        self.assertNotIn("План первого", second_user_titles)

    def test_plan_detail_route_edits_name_description_and_weekday(self):
        app = self._create_app()
        client = app.test_client()
        self._login(client)
        ensure_default_workout_plans(1)
        plan = get_workout_plans(1)[0]

        detail_response = client.get(f"/workouts/plans/{plan['id']}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("Тренировка 1|Не запланирована", detail_response.get_data(as_text=True))

        response = client.post(
            f"/workouts/plans/{plan['id']}",
            data={
                "name": "Ноги и корпус",
                "weekday": "3",
                "description": "Разминка\nПриседания — 4 × 10\nПланка — 3 подхода",
            },
        )
        updated = get_workout_plan(1, plan["id"])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(updated["name"], "Ноги и корпус")
        self.assertEqual(updated["weekday"], 3)
        self.assertIn("Планка", updated["description"])
        self.assertEqual(next_workout_date(3).weekday(), 3)

    def test_workout_templates_expose_clickable_details_and_schedule_controls(self):
        overview = (
            PROJECT_ROOT / "app" / "templates" / "workouts.html"
        ).read_text(encoding="utf-8")
        detail = (
            PROJECT_ROOT / "app" / "templates" / "workout_plan_detail.html"
        ).read_text(encoding="utf-8")
        schedule = (
            PROJECT_ROOT / "app" / "templates" / "schedule.html"
        ).read_text(encoding="utf-8")

        self.assertIn("url_for('workouts.plan_detail'", overview)
        self.assertIn('name="name"', detail)
        self.assertIn('name="weekday"', detail)
        self.assertIn('maxlength="5000"', detail)
        self.assertIn("Сохранить и обновить график", detail)
        self.assertIn("Открыть тренировку", schedule)
        self.assertNotIn("autofocus", detail)

    def test_training_is_reached_through_development_on_mobile_and_desktop(self):
        base = (PROJECT_ROOT / "app" / "templates" / "base.html").read_text(
            encoding="utf-8"
        )
        index = (PROJECT_ROOT / "app" / "templates" / "index.html").read_text(
            encoding="utf-8"
        )
        development_hub = (
            PROJECT_ROOT / "app" / "templates" / "study_hub.html"
        ).read_text(encoding="utf-8")
        sport_hub = (
            PROJECT_ROOT / "app" / "templates" / "sport_hub.html"
        ).read_text(encoding="utf-8")
        desktop_grid, mobile_grid = index.split(
            '<div class="dashboard-grid dashboard-grid-mobile dashboard-primary-grid">',
            1,
        )
        top_nav, bottom_nav = base.split(
            '<nav class="app-bottom-nav" aria-label="Основная навигация">',
            1,
        )

        self.assertIn("url_for('learning.study_hub')", desktop_grid)
        self.assertIn("url_for('learning.study_hub')", mobile_grid)
        self.assertIn("url_for('learning.study_hub')", top_nav)
        self.assertIn("url_for('sport_hub')", top_nav)
        self.assertIn("url_for('learning.study_hub')", bottom_nav)
        self.assertIn("<span>Развитие</span>", bottom_nav)
        self.assertNotIn("<span>Спорт</span>", bottom_nav)
        self.assertNotIn("url_for('workouts.index')", development_hub)
        self.assertIn("url_for('workouts.index')", sport_hub)
        self.assertIn("is_development_section", base)
        self.assertIn("is_sport_section", base)

    def test_workouts_desktop_theme_uses_blue_accents(self):
        styles = WORKOUTS_STYLE_FILE.read_text(encoding="utf-8")

        self.assertIn("--workout-blue: #2563eb;", styles)
        self.assertIn("--workout-purple: #1d4ed8;", styles)
        self.assertIn("linear-gradient(135deg, var(--workout-blue), var(--workout-purple))", styles)
        self.assertIn("background: #eff6ff;", styles)
        self.assertIn("border: 1px solid #bfdbfe;", styles)
        for purple_value in (
            "#7c3aed",
            "#9333ea",
            "#6d28d9",
            "#5b21b6",
            "#8b5cf6",
            "rgba(124, 58, 237",
            "rgba(91, 33, 182",
        ):
            self.assertNotIn(purple_value, styles)


if __name__ == "__main__":
    unittest.main()
