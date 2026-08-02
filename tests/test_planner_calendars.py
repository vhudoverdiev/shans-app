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
PLANNER_STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "style.css"


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
        self.assertIn("workout_plan_id", personal_tasks[0])
        self.assertIn("workout_user_id", personal_tasks[0])

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
        conn = sqlite3.connect(Config.DATABASE_NAME)
        conn.execute(
            """
            INSERT INTO schedule_tasks (
                title,
                task_date,
                calendar_type,
                status,
                workout_plan_id,
                workout_user_id
            ) VALUES ('Плановая тренировка', ?, 'personal', 'planned', 99, 1)
            """,
            (TEST_DATE,),
        )
        conn.commit()
        conn.close()

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
            {
                task["title"]
                for task in get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)
            },
            {"Новая личная", "Плановая тренировка"},
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

    def test_task_status_toggle_does_not_flash_service_notification(self):
        init_planner_db()
        create_task("Quiet task", TEST_DATE)
        task_id = get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)[0]["id"]
        client = self._create_test_app().test_client()

        response = client.post(f"/planner.schedule/task/{task_id}/toggle")

        self.assertEqual(response.status_code, 302)
        with client.session_transaction() as session:
            self.assertNotIn("_flashes", session)
        self.assertEqual(get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)[0]["status"], "done")

    def test_task_status_toggle_supports_ajax_without_page_reload(self):
        init_planner_db()
        create_task("Quiet ajax task", TEST_DATE)
        task_id = get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)[0]["id"]
        client = self._create_test_app().test_client()

        response = client.post(
            f"/planner.schedule/task/{task_id}/toggle",
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["taskId"], task_id)
        self.assertEqual(payload["previousStatus"], "planned")
        self.assertEqual(payload["status"], "done")
        self.assertEqual(payload["displayStatus"], "done")
        self.assertTrue(payload["displayStatusLabel"])
        self.assertEqual(get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)[0]["status"], "done")

    def test_schedule_template_intercepts_status_toggle_forms(self):
        template = (PROJECT_ROOT / "app" / "templates" / "schedule.html").read_text(encoding="utf-8")

        self.assertIn("planner-status-toggle-form", template)
        self.assertIn('fetch(form.action', template)
        self.assertIn('"X-Requested-With": "XMLHttpRequest"', template)
        self.assertIn('data-planner-stat="planned"', template)
        self.assertIn('data-planner-stat="done"', template)

    def test_task_move_next_day_does_not_flash_service_notification(self):
        init_planner_db()
        create_task("Quiet move", TEST_DATE)
        task_id = get_tasks_for_day(TEST_DATE, CALENDAR_PERSONAL)[0]["id"]
        client = self._create_test_app().test_client()

        response = client.post(f"/planner.schedule/task/{task_id}/move-next-day")

        self.assertEqual(response.status_code, 302)
        with client.session_transaction() as session:
            self.assertNotIn("_flashes", session)
        self.assertEqual(get_tasks_for_day("2026-07-22", CALENDAR_PERSONAL)[0]["title"], "Quiet move")

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

    def test_schedule_task_form_keeps_date_and_time_fields_inside_mobile_width(self):
        template = (PROJECT_ROOT / "app" / "templates" / "schedule_task_form.html").read_text(encoding="utf-8")
        styles = PLANNER_STYLE_FILE.read_text(encoding="utf-8")
        mobile_styles = (PROJECT_ROOT / "app" / "static" / "css" / "mobile.css").read_text(encoding="utf-8")

        self.assertIn("planner-task-form-grid", template)
        self.assertIn(".car-form-grid > .form-group", styles)
        self.assertIn(".car-form-grid .form-input", styles)
        self.assertIn(".planner-task-form-grid > .form-group", styles)
        self.assertIn(".planner-task-form-grid .form-input", styles)
        self.assertIn(".planner-task-form-grid", mobile_styles)
        self.assertIn("min-width: 0;", styles)
        self.assertIn("box-sizing: border-box;", styles)
        self.assertIn("@media (max-width: 1100px)", styles)
        self.assertIn(".car-page .planner-task-form-grid", styles)
        self.assertIn('.planner-task-form-grid .form-input:is(input[type="date"], input[type="time"])', mobile_styles)
        self.assertIn("inline-size: 100%;", mobile_styles)
        self.assertIn("max-inline-size: 100%;", mobile_styles)
        self.assertIn("-webkit-appearance: none;", mobile_styles)
        self.assertIn("padding-right: 46px;", mobile_styles)
        self.assertIn("overflow: hidden;", mobile_styles)
        self.assertIn("::-webkit-calendar-picker-indicator", mobile_styles)
        self.assertIn("margin-left: 0;", mobile_styles)

    def test_schedule_day_table_has_mobile_labels_for_all_cells(self):
        template = (PROJECT_ROOT / "app" / "templates" / "schedule.html").read_text(encoding="utf-8")

        for label in ("Выбор", "Название", "Время", "Статус", "Описание", "Действия"):
            self.assertIn(f'data-label="{label}"', template)


if __name__ == "__main__":
    unittest.main()
