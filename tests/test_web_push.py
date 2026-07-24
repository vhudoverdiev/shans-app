import base64
import json
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
from app.database import _dict_row_factory
from app.schedule_notifications import build_personal_tasks_text
from app.web_push import (
    PushCandidate,
    _build_declarative_payload,
    _generate_vapid_key_pair,
    _get_subscriptions,
    _send_to_subscription,
    collect_due_candidates,
    deliver_candidate,
    init_web_push_db,
    save_subscription,
    send_test_notification,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WebPushSchedulingTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temp_directory = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_directory.name) / "test.db")
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
                status TEXT NOT NULL DEFAULT 'planned'
            )
            """
        )
        conn.commit()
        conn.close()
        init_web_push_db()
        self.moscow_timezone = timezone(timedelta(hours=3), name="Europe/Moscow")

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
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
    ):
        conn = self._connect()
        cursor = conn.execute(
            """
            INSERT INTO schedule_tasks (
                title, task_date, start_time, calendar_type, status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (title, task_date, start_time, calendar_type, status),
        )
        conn.commit()
        task_id = cursor.lastrowid
        conn.close()
        return task_id

    def _subscription_payload(self):
        return {
            "endpoint": "https://push.example.test/subscription/1",
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

    def test_successful_delivery_is_reserved_once_per_device(self):
        save_subscription(
            1,
            self._subscription_payload(),
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
        with patch("app.web_push._send_to_subscription") as retry_mock:
            retry_result = deliver_candidate(candidate)

        self.assertEqual(failed_result, (0, 1))
        self.assertEqual(retry_result, (1, 0))
        retry_mock.assert_called_once()

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

        message = build_personal_tasks_text(
            datetime(2026, 7, 22).date(),
            "завтра",
        )

        self.assertEqual(
            message,
            "Задачи на завтра (22.07.2026):\n\n"
            "1. 09:30 — Проверка формата\n\n"
            "Всего задач: 1",
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

    def test_account_settings_contains_toggle_and_test_controls(self):
        template = (
            PROJECT_ROOT / "app" / "templates" / "account_settings.html"
        ).read_text(encoding="utf-8")
        stylesheet = (
            PROJECT_ROOT / "app" / "static" / "css" / "style.css"
        ).read_text(encoding="utf-8")

        self.assertIn('id="push-notifications-toggle"', template)
        self.assertIn('id="push-notifications-test"', template)
        self.assertIn("push-notifications.js", template)
        self.assertIn('.account-push-actions .btn[hidden]', stylesheet)

    def test_service_worker_handles_push_and_notification_click(self):
        service_worker = (
            PROJECT_ROOT / "app" / "static" / "service-worker.js"
        ).read_text(encoding="utf-8")

        self.assertIn('addEventListener("push"', service_worker)
        self.assertIn("showNotification", service_worker)
        self.assertIn('addEventListener("notificationclick"', service_worker)

    def test_client_recovers_from_changed_vapid_key_and_rejected_subscription(self):
        push_client = (
            PROJECT_ROOT / "app" / "static" / "js" / "push-notifications.js"
        ).read_text(encoding="utf-8")

        self.assertIn("subscriptionUsesPublicKey", push_client)
        self.assertIn("payload.resetSubscription", push_client)
        self.assertIn("discardLocalSubscription", push_client)


if __name__ == "__main__":
    unittest.main()
