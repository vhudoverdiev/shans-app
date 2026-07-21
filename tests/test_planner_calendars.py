import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask
from flask_login import LoginManager

from config import Config
from app.planner import (
    CALENDAR_PERSONAL,
    CALENDAR_WORK,
    create_booking,
    create_project,
    create_task,
    get_tasks_for_day,
    init_planner_db,
    planner_bp,
    replace_manual_schedule_tasks,
    upsert_task_for_booking,
    upsert_task_for_scenario,
    upsert_task_for_shooting,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATE = "2026-07-21"


class PlannerCalendarTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database_name = Config.DATABASE_NAME
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "planner-test.db")

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_dir.cleanup()

    def _create_test_app(self):
        app = Flask(
            "planner-calendar-tests",
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

    def test_migration_keeps_existing_tasks_in_personal_calendar(self):
        conn = sqlite3.connect(Config.DATABASE_NAME)
        conn.execute(
            """
            CREATE TABLE schedule_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                task_date TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                is_important INTEGER NOT NULL DEFAULT 0,
                range_end_date TEXT,
                task_type TEXT NOT NULL DEFAULT 'Личное',
                status TEXT NOT NULL DEFAULT 'planned',
                project_id INTEGER,
                booking_id INTEGER,
                shooting_id INTEGER,
                scenario_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO schedule_tasks (title, task_date) VALUES (?, ?)",
            ("Старая задача", TEST_DATE),
        )
        conn.commit()
        conn.close()

        init_planner_db()

        personal_tasks = get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)
        work_tasks = get_tasks_for_day(TEST_DATE, CALENDAR_WORK)
        self.assertEqual([task["title"] for task in personal_tasks], ["Старая задача"])
        self.assertEqual(work_tasks, [])

    def test_calendars_are_isolated_and_synced_tasks_stay_personal(self):
        init_planner_db()
        create_task("Личная запись", TEST_DATE)
        create_task("Рабочая запись", TEST_DATE, calendar_type=CALENDAR_WORK)
        upsert_task_for_shooting(
            shooting_id=42,
            project_name="Автоматическая съёмка",
            client_name="Клиент",
            shooting_date=TEST_DATE,
        )
        upsert_task_for_scenario(
            scenario_id=43,
            title="Автоматический сценарий",
            shooting_date=TEST_DATE,
        )
        project_id = create_project(
            "Автоматический фотопроект",
            "Архангельск",
            "Студия",
            TEST_DATE,
            "10:00",
            "18:00",
        )
        booking_id = create_booking(
            project_id,
            "Клиент",
            "+70000000000",
            TEST_DATE,
            "12:00",
            15,
            "",
            1000,
            500,
        )
        upsert_task_for_booking(booking_id)

        personal_titles = {
            task["title"] for task in get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)
        }
        work_titles = {
            task["title"] for task in get_tasks_for_day(TEST_DATE, CALENDAR_WORK)
        }

        self.assertEqual(
            personal_titles,
            {
                "Личная запись",
                "Автоматическая съёмка",
                "Автоматический сценарий",
                "Автоматический фотопроект",
            },
        )
        self.assertEqual(work_titles, {"Рабочая запись"})

    def test_personal_import_replacement_does_not_remove_work_tasks(self):
        init_planner_db()
        create_task("Старая личная", TEST_DATE)
        create_task("Рабочая остаётся", TEST_DATE, calendar_type=CALENDAR_WORK)

        replace_manual_schedule_tasks(
            [
                {
                    "title": "Новая личная",
                    "task_date": TEST_DATE,
                    "status": "planned",
                    "task_type": "Личное",
                }
            ]
        )

        self.assertEqual(
            [task["title"] for task in get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)],
            ["Новая личная"],
        )
        self.assertEqual(
            [task["title"] for task in get_tasks_for_day(TEST_DATE, CALENDAR_WORK)],
            ["Рабочая остаётся"],
        )

    def test_schedule_switch_renders_only_selected_calendar(self):
        init_planner_db()
        create_task("Только в личном", TEST_DATE)
        create_task("Только в рабочем", TEST_DATE, calendar_type=CALENDAR_WORK)
        client = self._create_test_app().test_client()

        personal_page = client.get(
            f"/planner.schedule?calendar=personal&view=day&date={TEST_DATE}"
        )
        work_page = client.get(
            f"/planner.schedule?calendar=work&view=day&date={TEST_DATE}"
        )

        self.assertEqual(personal_page.status_code, 200)
        self.assertIn("Выбор графика", personal_page.get_data(as_text=True))
        self.assertIn("Только в личном", personal_page.get_data(as_text=True))
        self.assertNotIn("Только в рабочем", personal_page.get_data(as_text=True))
        self.assertIn("Только в рабочем", work_page.get_data(as_text=True))
        self.assertNotIn("Только в личном", work_page.get_data(as_text=True))

    def test_work_task_creation_persists_calendar_and_redirects_back_to_it(self):
        init_planner_db()
        client = self._create_test_app().test_client()

        response = client.post(
            "/planner.schedule/task/create",
            data={
                "title": "Новая рабочая задача",
                "task_date": TEST_DATE,
                "task_form_mode": "single",
                "is_important": "no",
                "calendar_type": CALENDAR_WORK,
                "return_view": "day",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("calendar=work", response.headers["Location"])
        self.assertEqual(
            [task["title"] for task in get_tasks_for_day(TEST_DATE, CALENDAR_WORK)],
            ["Новая рабочая задача"],
        )
        self.assertEqual(get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL), [])

    def test_bulk_delete_cannot_cross_calendar_boundary(self):
        init_planner_db()
        create_task("Личная защищена", TEST_DATE)
        create_task("Рабочая удаляется", TEST_DATE, calendar_type=CALENDAR_WORK)
        personal_task = get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)[0]
        work_task = get_tasks_for_day(TEST_DATE, CALENDAR_WORK)[0]
        client = self._create_test_app().test_client()

        response = client.post(
            "/planner.schedule/task/delete-selected",
            data={
                "task_date": TEST_DATE,
                "calendar_type": CALENDAR_WORK,
                "selected_ids": f"{personal_task['id']},{work_task['id']}",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            [task["title"] for task in get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)],
            ["Личная защищена"],
        )
        self.assertEqual(get_tasks_for_day(TEST_DATE, CALENDAR_WORK), [])


if __name__ == "__main__":
    unittest.main()
