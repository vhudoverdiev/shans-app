import base64
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from flask import Flask
from py_vapid import Vapid
from pywebpush import WebPushException

from config import Config
from app import create_app
from app.database import _dict_row_factory
from app.schedule_notifications import build_personal_tasks_text, build_work_tasks_text
from app.learning import init_learning_db
from app.web_push import (
    PushCandidate,
    _build_declarative_payload,
    _generate_vapid_key_pair,
    _get_subscriptions,
    _send_to_subscription,
    collect_due_candidates,
    deliver_candidate,
    get_recent_push_notifications,
    get_unread_push_notifications,
    init_web_push_db,
    mark_all_push_notifications_read,
    save_subscription,
    send_external_telegram_notification,
    send_test_notification,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WebPushSchedulingTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.original_telegram_push_secret = Config.TELEGRAM_PUSH_SECRET
        self.temp_directory = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_directory.name) / "test.db")
        Config.TELEGRAM_PUSH_SECRET = ""
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE schedule_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                task_date TEXT NOT NULL,
                start_time TEXT,
                task_type TEXT NOT NULL DEFAULT 'Личное',
                calendar_type TEXT NOT NULL DEFAULT 'personal',
                status TEXT NOT NULL DEFAULT 'planned',
                workout_plan_id INTEGER,
                workout_user_id INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                is_system_admin INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.executemany(
            "INSERT INTO users (id, username, is_system_admin, is_active) VALUES (?, ?, ?, ?)",
            (
                (1, "admin", 1, 1),
                (2, "vhudoverdiev", 0, 1),
            ),
        )
        conn.commit()
        conn.close()
        init_learning_db()
        init_web_push_db()
        self.moscow_timezone = timezone(timedelta(hours=3), name="Europe/Moscow")

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        Config.TELEGRAM_PUSH_SECRET = self.original_telegram_push_secret
        self.temp_directory.cleanup()

    def _connect(self):
        conn = sqlite3.connect(Config.DATABASE_NAME)
        conn.row_factory = _dict_row_factory
        return conn

    def _add_task(
        self,
        title,
        task_date,
        start_time=None,
        calendar_type="personal",
        status="planned",
        workout_user_id=None,
    ):
        conn = self._connect()
        cursor = conn.execute(
            """
            INSERT INTO schedule_tasks (
                title, task_date, start_time, calendar_type, status, workout_user_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                task_date,
                start_time,
                calendar_type,
                status,
                workout_user_id,
            ),
        )
        conn.commit()
        task_id = cursor.lastrowid
        conn.close()
        return task_id

    def _subscription_payload(self, endpoint="https://push.example.test/subscription/1"):
        return {
            "endpoint": endpoint,
            "keys": {
                "p256dh": "A" * 65,
                "auth": "B" * 16,
            },
        }

    def test_daily_message_and_candidates_only_include_personal_schedule(self):
        target_date = "2026-07-21"
        personal_task_id = self._add_task("Личная встреча", target_date, "12:00")
        self._add_task("Рабочая задача", target_date, "11:00", calendar_type="work")
        self._add_task("Завершённая задача", target_date, "10:30", status="done")
        self._add_task("Поздняя задача", target_date, "13:00")

        now_local = datetime(2026, 7, 21, 10, 0, tzinfo=self.moscow_timezone)
        candidates = collect_due_candidates(now_local)
        keys = {candidate.key for candidate in candidates}
        summary = next(candidate for candidate in candidates if candidate.key.startswith("summary:today:"))

        self.assertIn("Личная встреча", summary.body)
        self.assertIn("Поздняя задача", summary.body)
        self.assertNotIn("Рабочая задача", summary.body)
        self.assertNotIn("Завершённая задача", summary.body)
        self.assertIn(f"task:{personal_task_id}:2026-07-21:12:00", keys)
        self.assertFalse(any("11:00" in key for key in keys))
        self.assertFalse(any("13:00" in key for key in keys))

    def test_summary_windows_are_10_and_20_hours_only(self):
        morning = collect_due_candidates(
            datetime(2026, 7, 21, 10, 0, tzinfo=self.moscow_timezone)
        )
        after_morning_window = collect_due_candidates(
            datetime(2026, 7, 21, 10, 5, tzinfo=self.moscow_timezone)
        )
        evening = collect_due_candidates(
            datetime(2026, 7, 21, 20, 0, tzinfo=self.moscow_timezone)
        )

        self.assertTrue(any(item.key == "summary:today:2026-07-21" for item in morning))
        self.assertFalse(any(item.key.startswith("summary:") for item in after_morning_window))
        self.assertTrue(any(item.key == "summary:tomorrow:2026-07-22" for item in evening))

    def test_work_schedule_summary_is_sent_on_weekdays_at_9_moscow_time(self):
        target_date = "2026-07-21"
        self._add_task("Личная встреча", target_date, "08:30")
        self._add_task("Рабочий созвон", target_date, "09:30", calendar_type="work")
        self._add_task("Рабочий отчёт", target_date, "11:00", calendar_type="work")
        self._add_task(
            "Закрытая рабочая задача",
            target_date,
            "12:00",
            calendar_type="work",
            status="done",
        )

        summary_text = build_work_tasks_text(datetime(2026, 7, 21).date(), "сегодня")
        self.assertIn("Рабочий созвон", summary_text)
        self.assertIn("Рабочий отчёт", summary_text)
        self.assertNotIn("Личная встреча", summary_text)
        self.assertNotIn("Закрытая рабочая задача", summary_text)

        candidates = collect_due_candidates(
            datetime(2026, 7, 21, 9, 0, tzinfo=self.moscow_timezone),
            user_ids={1, 2},
        )
        work_summaries = [
            candidate
            for candidate in candidates
            if candidate.key == "work-summary:today:2026-07-21"
        ]

        self.assertEqual(len(work_summaries), 2)
        self.assertEqual({candidate.user_id for candidate in work_summaries}, {1, 2})
        self.assertTrue(all(candidate.title == "Шанс — рабочий график" for candidate in work_summaries))
        self.assertTrue(
            all(
                candidate.navigate_path
                == "/planner.schedule?calendar=work&view=day&date=2026-07-21"
                for candidate in work_summaries
            )
        )
        self.assertTrue(all("Рабочий созвон" in candidate.body for candidate in work_summaries))
        self.assertTrue(all("Личная встреча" not in candidate.body for candidate in work_summaries))

        after_window = collect_due_candidates(
            datetime(2026, 7, 21, 9, 5, tzinfo=self.moscow_timezone),
            user_ids={1},
        )
        weekend = collect_due_candidates(
            datetime(2026, 7, 25, 9, 0, tzinfo=self.moscow_timezone),
            user_ids={1},
        )
        self.assertFalse(any(item.key.startswith("work-summary:") for item in after_window))
        self.assertFalse(any(item.key.startswith("work-summary:") for item in weekend))

    def test_workout_tasks_in_summary_are_isolated_by_user(self):
        target_date = "2026-07-21"
        self._add_task("Общая личная задача", target_date)
        self._add_task(
            "Тренировка первого",
            target_date,
            workout_user_id=1,
        )
        self._add_task(
            "Тренировка второго",
            target_date,
            workout_user_id=2,
        )

        candidates = collect_due_candidates(
            datetime(2026, 7, 21, 10, 0, tzinfo=self.moscow_timezone),
            user_ids={1, 2},
        )
        summaries = {
            candidate.user_id: candidate.body
            for candidate in candidates
            if candidate.key == "summary:today:2026-07-21"
        }

        self.assertEqual(set(summaries), {1, 2})
        self.assertIn("Общая личная задача", summaries[1])
        self.assertIn("Общая личная задача", summaries[2])
        self.assertIn("Тренировка первого", summaries[1])
        self.assertNotIn("Тренировка второго", summaries[1])
        self.assertIn("Тренировка второго", summaries[2])
        self.assertNotIn("Тренировка первого", summaries[2])

    def test_learning_reminder_is_daily_and_targets_only_the_user(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )
        save_subscription(
            2,
            self._subscription_payload("https://push.example.test/subscription/2"),
            "https://shans.example.test",
        )
        now_local = datetime(2026, 7, 21, 19, 0, tzinfo=self.moscow_timezone)
        candidates = collect_due_candidates(now_local, user_ids={1, 2})
        learning_candidates = [
            item for item in candidates if item.key == "learning:daily:2026-07-21"
        ]

        self.assertEqual(len(learning_candidates), 2)
        self.assertEqual({item.user_id for item in learning_candidates}, {1, 2})
        self.assertTrue(all("English — день 1" in item.body for item in learning_candidates))
        self.assertTrue(all("IT — день 1" in item.body for item in learning_candidates))
        self.assertFalse(
            any(
                item.key.startswith("learning:")
                for item in collect_due_candidates(
                    datetime(2026, 7, 21, 19, 5, tzinfo=self.moscow_timezone),
                    user_ids={1, 2},
                )
            )
        )

        candidate_for_user_1 = next(item for item in learning_candidates if item.user_id == 1)
        with patch("app.web_push._send_to_subscription") as send_mock:
            result = deliver_candidate(candidate_for_user_1)

        self.assertEqual(result, (1, 0))
        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.args[0]["user_id"], 1)
        self.assertEqual(get_unread_push_notifications(1)[1], 1)
        self.assertEqual(get_unread_push_notifications(2)[1], 0)

    def test_learning_reminder_skips_course_test_attempted_today(self):
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO english_course_progress (
                user_id, day_number, best_score, attempts, passed, updated_at
            ) VALUES (1, 1, 5, 1, 1, '2026-07-21 12:00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO it_course_progress (
                user_id, day_number, best_score, attempts, passed, updated_at
            ) VALUES (1, 1, 2, 1, 0, '2026-07-21 12:00:00')
            """
        )
        conn.commit()
        conn.close()

        candidates = collect_due_candidates(
            datetime(2026, 7, 21, 19, 0, tzinfo=self.moscow_timezone),
            user_ids={1},
        )

        self.assertFalse(any(item.key.startswith("learning:") for item in candidates))

    def test_learning_reminder_only_lists_courses_not_attempted_today(self):
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO english_course_progress (
                user_id, day_number, best_score, attempts, passed, updated_at
            ) VALUES (1, 1, 5, 1, 1, '2026-07-21 12:00:00')
            """
        )
        conn.commit()
        conn.close()

        candidates = collect_due_candidates(
            datetime(2026, 7, 21, 19, 0, tzinfo=self.moscow_timezone),
            user_ids={1},
        )
        learning_candidate = next(
            item for item in candidates if item.key.startswith("learning:")
        )

        self.assertNotIn("English", learning_candidate.body)
        self.assertIn("IT — день 1", learning_candidate.body)
        self.assertEqual(learning_candidate.navigate_path, "/study/it/day/1")

    def test_task_after_midnight_is_reminded_two_hours_before(self):
        task_id = self._add_task("Ночная поездка", "2026-07-22", "01:00")
        candidates = collect_due_candidates(
            datetime(2026, 7, 21, 23, 0, tzinfo=self.moscow_timezone)
        )

        self.assertIn(
            f"task:{task_id}:2026-07-22:01:00",
            {candidate.key for candidate in candidates},
        )

    def test_task_reminder_is_not_sent_after_five_minute_window(self):
        self._add_task("Точная встреча", "2026-07-21", "12:00")

        candidates = collect_due_candidates(
            datetime(2026, 7, 21, 10, 5, tzinfo=self.moscow_timezone)
        )

        self.assertFalse(any(candidate.key.startswith("task:") for candidate in candidates))

    def test_successful_delivery_is_reserved_once_per_user(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )
        save_subscription(
            1,
            self._subscription_payload("https://push.example.test/subscription/2"),
            "https://shans.example.test",
        )
        candidate = PushCandidate(
            key="summary:today:2026-07-21",
            title="Шанс — личный график",
            body="Задачи на сегодня",
            navigate_path="/planner.schedule?calendar=personal",
            tag="summary-today",
        )

        with patch("app.web_push._send_to_subscription") as send_mock:
            first_result = deliver_candidate(candidate)
            second_result = deliver_candidate(candidate)

        self.assertEqual(first_result, (1, 0))
        self.assertEqual(second_result, (0, 0))
        send_mock.assert_called_once()
        self.assertEqual(
            send_mock.call_args.args[0]["endpoint"],
            "https://push.example.test/subscription/2",
        )
        notifications, unread_count = get_unread_push_notifications(1)
        self.assertEqual(unread_count, 1)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["title"], candidate.title)
        self.assertEqual(notifications[0]["body"], candidate.body)

        self.assertEqual(mark_all_push_notifications_read(1), 1)
        self.assertEqual(get_unread_push_notifications(1), ([], 0))

    def test_recent_inbox_returns_last_three_days_and_recent_unread_count(self):
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO web_push_inbox (
                    user_id, notification_key, title, body, navigate_path,
                    created_at, read_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now', '-4 days'), NULL)
                """,
                (1, "old", "Old", "Too old", "/"),
            )
            conn.execute(
                """
                INSERT INTO web_push_inbox (
                    user_id, notification_key, title, body, navigate_path,
                    created_at, read_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now', '-2 days'), datetime('now'))
                """,
                (1, "recent-read", "Recent read", "Seen", "/"),
            )
            conn.execute(
                """
                INSERT INTO web_push_inbox (
                    user_id, notification_key, title, body, navigate_path,
                    created_at, read_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now', '-1 day'), NULL)
                """,
                (1, "recent-unread", "Recent unread", "New", "/"),
            )
            conn.commit()
        finally:
            conn.close()

        notifications, unread_count = get_recent_push_notifications(1)

        self.assertEqual(unread_count, 1)
        self.assertEqual(
            [notification["title"] for notification in notifications],
            ["Recent unread", "Recent read"],
        )
        self.assertIsNone(notifications[0]["read_at"])
        self.assertIsNotNone(notifications[1]["read_at"])

    def test_existing_device_delivery_is_migrated_to_user_deduplication(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )
        subscription = _get_subscriptions(user_id=1)[0]
        notification_key = "summary:tomorrow:2026-07-22"
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO web_push_deliveries (notification_key, subscription_id)
            VALUES (?, ?)
            """,
            (notification_key, subscription["id"]),
        )
        conn.execute(
            "DELETE FROM web_push_user_deliveries WHERE notification_key = ?",
            (notification_key,),
        )
        conn.commit()
        conn.close()

        init_web_push_db()
        candidate = PushCandidate(
            key=notification_key,
            title="Шанс — личный график",
            body="Задачи на завтра",
            navigate_path="/planner.schedule?calendar=personal",
            tag="summary-tomorrow",
        )
        with patch("app.web_push._send_to_subscription") as send_mock:
            result = deliver_candidate(candidate)

        self.assertEqual(result, (0, 0))
        send_mock.assert_not_called()

    def test_same_candidate_is_delivered_once_to_each_different_user(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )
        save_subscription(
            2,
            self._subscription_payload("https://push.example.test/subscription/2"),
            "https://shans.example.test",
        )
        candidate = PushCandidate(
            key="summary:today:2026-07-21",
            title="Шанс — личный график",
            body="Задачи на сегодня",
            navigate_path="/planner.schedule?calendar=personal",
            tag="summary-today",
        )

        with patch("app.web_push._send_to_subscription") as send_mock:
            result = deliver_candidate(candidate)

        self.assertEqual(result, (2, 0))
        self.assertEqual(send_mock.call_count, 2)
        self.assertEqual(get_unread_push_notifications(1)[1], 1)
        self.assertEqual(get_unread_push_notifications(2)[1], 1)

    def test_failed_delivery_is_released_for_retry(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )
        candidate = PushCandidate(
            key="task:1:2026-07-21:12:00",
            title="Задача через 2 часа",
            body="12:00 — Проверка",
            navigate_path="/planner.schedule?calendar=personal",
            tag="task-1",
        )

        with patch("app.web_push._send_to_subscription", side_effect=RuntimeError("offline")):
            failed_result = deliver_candidate(candidate)
        self.assertEqual(get_unread_push_notifications(1), ([], 0))
        with patch("app.web_push._send_to_subscription") as retry_mock:
            retry_result = deliver_candidate(candidate)

        self.assertEqual(failed_result, (0, 1))
        self.assertEqual(retry_result, (1, 0))
        self.assertEqual(get_unread_push_notifications(1)[1], 1)
        retry_mock.assert_called_once()

    def test_test_notification_is_not_added_to_inbox(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )

        with patch("app.web_push._send_to_subscription"):
            ok, _message = send_test_notification(
                1,
                self._subscription_payload()["endpoint"],
            )

        self.assertTrue(ok)
        self.assertEqual(get_unread_push_notifications(1), ([], 0))

    def test_external_telegram_notification_targets_main_admin_only(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )
        save_subscription(
            2,
            self._subscription_payload("https://push.example.test/subscription/2"),
            "https://shans.example.test",
        )

        with patch("app.web_push._send_to_subscription") as send_mock:
            result = send_external_telegram_notification(
                {
                    "title": "Render finished",
                    "body": "The local script completed successfully.",
                    "navigate_path": "/",
                }
            )

        self.assertEqual(result, (1, 0))
        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.args[0]["user_id"], 1)
        notifications, unread_count = get_unread_push_notifications(1)
        self.assertEqual(unread_count, 1)
        self.assertEqual(notifications[0]["title"], "Render finished")
        self.assertEqual(
            notifications[0]["body"],
            "The local script completed successfully.",
        )
        self.assertEqual(get_unread_push_notifications(2), ([], 0))

    def test_external_telegram_notification_uses_vk_accounts_fallback_title(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )

        with patch("app.web_push._send_to_subscription"):
            result = send_external_telegram_notification(
                {
                    "body": "The local script completed successfully.",
                    "navigate_path": "/",
                }
            )

        self.assertEqual(result, (1, 0))
        notifications, unread_count = get_unread_push_notifications(1)
        self.assertEqual(unread_count, 1)
        self.assertEqual(notifications[0]["title"], "Вк аккануты")

    def test_external_telegram_notification_ignores_recipient_override(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )
        save_subscription(
            2,
            self._subscription_payload("https://push.example.test/subscription/2"),
            "https://shans.example.test",
        )

        with patch("app.web_push._send_to_subscription") as send_mock:
            result = send_external_telegram_notification(
                {
                    "title": "Render finished",
                    "body": "The local script completed successfully.",
                    "username": "vhudoverdiev",
                    "user_id": 2,
                }
            )

        self.assertEqual(result, (1, 0))
        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.args[0]["user_id"], 1)
        self.assertEqual(get_unread_push_notifications(1)[1], 1)
        self.assertEqual(get_unread_push_notifications(2), ([], 0))

    def test_external_telegram_push_route_uses_secret_without_csrf(self):
        Config.TELEGRAM_PUSH_SECRET = "test-secret"
        with patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": "false"}):
            app = create_app()
        app.config["TESTING"] = True
        app.config["TELEGRAM_PUSH_SECRET"] = "test-secret"

        with (
            app.test_client() as client,
            patch("app.web_push.send_external_telegram_notification", return_value=(1, 0)) as send_mock,
        ):
            forbidden_response = client.post(
                "/api/push/external/telegram",
                json={"body": "done"},
            )
            ok_response = client.post(
                "/api/push/external/telegram",
                json={"body": "done"},
                headers={"X-Shans-Push-Secret": "test-secret"},
            )

        self.assertEqual(forbidden_response.status_code, 403)
        self.assertEqual(ok_response.status_code, 200)
        self.assertEqual(ok_response.get_json()["sent"], 1)
        send_mock.assert_called_once_with({"body": "done"})

    def test_payload_is_declarative_and_has_absolute_navigation_url(self):
        candidate = PushCandidate(
            key="task:1:2026-07-21:12:00",
            title="Задача через 2 часа",
            body="12:00 — Проверка",
            navigate_path="/planner.schedule?calendar=personal&date=2026-07-21",
            tag="task-1",
        )

        payload = json.loads(
            _build_declarative_payload(candidate, "https://shans.example.test")
        )

        self.assertEqual(payload["web_push"], 8030)
        self.assertEqual(payload["notification"]["title"], "Задача через 2 часа")
        self.assertEqual(
            payload["notification"]["navigate"],
            "https://shans.example.test/planner.schedule?calendar=personal&date=2026-07-21",
        )

    def test_generated_vapid_private_key_matches_public_key(self):
        private_key, public_key = _generate_vapid_key_pair()
        vapid = Vapid.from_string(private_key)
        derived_public_key = base64.urlsafe_b64encode(
            vapid._public_key.public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        ).rstrip(b"=").decode("ascii")

        self.assertEqual(derived_public_key, public_key)

    def test_apple_push_uses_app_origin_instead_of_local_vapid_subject(self):
        candidate = PushCandidate(
            key="test:1",
            title="Шанс — тест",
            body="Проверка",
            navigate_path="/planner.schedule",
            tag="test-1",
        )
        subscription = {
            "endpoint": "https://web.push.apple.com/subscription/1",
            "p256dh": "A" * 65,
            "auth": "B" * 16,
            "app_origin": "https://shans.example.test",
        }
        app = Flask(__name__)
        app.config["WEB_PUSH_VAPID_SUBJECT"] = "mailto:notifications@shans.local"

        with (
            app.app_context(),
            patch("app.web_push._get_vapid_private_key", return_value="private-key"),
            patch("app.web_push.webpush") as webpush_mock,
        ):
            _send_to_subscription(subscription, candidate)

        kwargs = webpush_mock.call_args.kwargs
        self.assertEqual(
            kwargs["vapid_claims"]["sub"],
            "https://shans.example.test",
        )
        self.assertEqual(kwargs["headers"], {"Urgency": "high"})

    def test_bad_vapid_token_removes_subscription_for_clean_resubscribe(self):
        save_subscription(
            1,
            self._subscription_payload(),
            "https://shans.example.test",
        )
        response = SimpleNamespace(
            status_code=403,
            text='{"reason":"BadJwtToken"}',
            json=lambda: {"reason": "BadJwtToken"},
        )
        app = Flask(__name__)

        with (
            app.app_context(),
            patch(
                "app.web_push._send_to_subscription",
                side_effect=WebPushException("rejected", response=response),
            ),
        ):
            ok, message = send_test_notification(
                1,
                self._subscription_payload()["endpoint"],
            )

        self.assertFalse(ok)
        self.assertIn("Включить уведомления", message)
        self.assertEqual(
            _get_subscriptions(
                user_id=1,
                endpoint=self._subscription_payload()["endpoint"],
            ),
            [],
        )

    def test_summary_message_builder_format(self):
        self._add_task("Проверка формата", "2026-07-22", "09:30")
        self._add_task("Без времени", "2026-07-22")

        message = build_personal_tasks_text(
            datetime(2026, 7, 22).date(),
            "завтра",
        )

        self.assertEqual(
            message,
            "Задачи на завтра (22.07.2026):\n\n"
            "1. 09:30 — Проверка формата\n"
            "2. Без времени\n\n"
            "Всего задач: 2",
        )


class WebPushAssetsTests(unittest.TestCase):
    def test_vk_delivery_code_and_legacy_planner_controls_are_removed(self):
        app_package = PROJECT_ROOT / "app"
        app_factory = (app_package / "__init__.py").read_text(encoding="utf-8")
        planner = (app_package / "planner.py").read_text(encoding="utf-8")
        planner_styles = (
            app_package / "static" / "css" / "planner.css"
        ).read_text(encoding="utf-8")
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        application_sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in app_package.rglob("*.py")
        )

        self.assertFalse((app_package / "vk_notifications.py").exists())
        self.assertFalse((app_package / "services" / "vk_notifier.py").exists())
        self.assertIn("init_web_push_db", app_factory)
        self.assertNotIn("vk_notifications", app_factory)
        self.assertNotIn("start_vk_scheduler", app_factory)
        self.assertNotIn("api.vk.com", application_sources)
        self.assertNotIn("messages.send", application_sources)
        self.assertNotIn("VK_ACCESS_TOKEN", readme)
        self.assertNotIn("vk-send-test", readme)
        self.assertNotIn("vk_notifications", planner)
        self.assertNotIn("/planner.schedule/vk-test-send", planner)
        self.assertNotIn(".planner-vk-", planner_styles)

    def test_account_settings_contains_compact_mobile_notification_toggle(self):
        template = (
            PROJECT_ROOT / "app" / "templates" / "account_settings.html"
        ).read_text(encoding="utf-8")
        push_client = (
            PROJECT_ROOT / "app" / "static" / "js" / "push-notifications.js"
        ).read_text(encoding="utf-8")
        mobile_styles = (
            PROJECT_ROOT / "app" / "static" / "css" / "mobile.css"
        ).read_text(encoding="utf-8")

        self.assertIn('<span class="account-push-mobile-only">Уведомления</span>', template)
        self.assertIn('id="push-notifications-toggle"', template)
        self.assertIn("data-push-toggle-mobile-label>Включить</span>", template)
        self.assertIn('id="push-notifications-status"', template)
        self.assertIn('id="account-push-inbox-trigger"', template)
        self.assertIn('data-push-inbox-trigger', template)
        self.assertIn("push-notifications.js", template)
        self.assertIn('id="push-notifications-test"', template)
        self.assertIn("account-push-desktop-only", template)
        self.assertIn(".account-push-desktop-only", mobile_styles)
        self.assertIn(
            '.account-push-status:not([data-state="error"]):not([data-state="info"])',
            mobile_styles,
        )
        self.assertIn('enabled ? "Выключить" : "Включить"', push_client)

    def test_service_worker_handles_push_and_notification_click(self):
        service_worker = (
            PROJECT_ROOT / "app" / "static" / "service-worker.js"
        ).read_text(encoding="utf-8")

        self.assertIn('addEventListener("push"', service_worker)
        self.assertIn("showNotification", service_worker)
        self.assertIn("shans-push-received", service_worker)
        self.assertIn('addEventListener("notificationclick"', service_worker)

    def test_push_inbox_uses_recent_history_and_cross_tab_sync(self):
        base_template = (
            PROJECT_ROOT / "app" / "templates" / "base.html"
        ).read_text(encoding="utf-8")
        push_client = (
            PROJECT_ROOT / "app" / "static" / "js" / "push-inbox.js"
        ).read_text(encoding="utf-8")
        push_module = (
            PROJECT_ROOT / "app" / "web_push.py"
        ).read_text(encoding="utf-8")

        self.assertIn('id="mobile-push-inbox-trigger"', base_template)
        self.assertIn('id="mobile-push-inbox-sheet"', base_template)
        self.assertIn("js/push-inbox.js", base_template)
        self.assertIn("data-inbox-url", base_template)
        self.assertIn("data-read-url", base_template)
        self.assertIn("За последние 3 дня", base_template)
        self.assertIn("shans-push-received", push_client)
        self.assertIn('window.fetch(apiTrigger.dataset.inboxUrl', push_client)
        self.assertIn('window.fetch(apiTrigger.dataset.readUrl', push_client)
        self.assertIn("BroadcastChannel", push_client)
        self.assertIn("localStorage.setItem", push_client)
        self.assertIn("За последние 3 дня уведомлений нет.", push_client)
        self.assertIn('CREATE TABLE IF NOT EXISTS web_push_inbox', push_module)
        self.assertIn("def get_recent_push_notifications", push_module)
        self.assertIn('@app.get("/api/push/inbox")', push_module)
        self.assertIn('@app.post("/api/push/inbox/read")', push_module)

    def test_client_recovers_from_changed_vapid_key_and_rejected_subscription(self):
        push_client = (
            PROJECT_ROOT / "app" / "static" / "js" / "push-notifications.js"
        ).read_text(encoding="utf-8")

        self.assertIn("subscriptionUsesPublicKey", push_client)
        self.assertIn("payload.resetSubscription", push_client)
        self.assertIn("discardLocalSubscription", push_client)

    def test_push_toggle_refreshes_ui_from_browser_subscription_state(self):
        push_client = (
            PROJECT_ROOT / "app" / "static" / "js" / "push-notifications.js"
        ).read_text(encoding="utf-8")

        self.assertIn("async function refreshSubscriptionState()", push_client)
        self.assertIn("registration.pushManager.getSubscription()", push_client)
        self.assertIn("await refreshSubscriptionState();", push_client)
        self.assertIn('toggleButton.dataset.enabled = enabled ? "true" : "false";', push_client)
        self.assertIn('toggleButton.setAttribute("aria-pressed", enabled ? "true" : "false");', push_client)
        self.assertLess(
            push_client.index("subscription = newSubscription;"),
            push_client.index("await refreshSubscriptionState();", push_client.index("subscription = newSubscription;")),
        )

    def test_push_toggle_does_not_require_home_screen_installation(self):
        push_client = (
            PROJECT_ROOT / "app" / "static" / "js" / "push-notifications.js"
        ).read_text(encoding="utf-8")

        self.assertNotIn("isStandaloneApp()", push_client)
        self.assertNotIn("window.navigator.standalone", push_client)
        self.assertNotIn("display-mode: standalone", push_client)
        self.assertNotIn("экран домой", push_client)


if __name__ == "__main__":
    unittest.main()
