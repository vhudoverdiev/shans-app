from __future__ import annotations

import base64
import hmac
import json
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from flask import current_app, has_app_context, jsonify, request
from flask_login import current_user, login_required
from pywebpush import WebPushException, webpush

from app.database import get_connection
from app.schedule_notifications import build_personal_tasks_text, build_work_tasks_text


_TIMEZONE_NAME = "Europe/Moscow"
_SUMMARY_WINDOW = timedelta(minutes=5)
_WORK_SUMMARY_HOUR = 9
_LEARNING_REMINDER_HOUR = 19
_DAILY_HEALTH_REMINDER_HOUR = 21
_SCHEDULER_INTERVAL_SECONDS = 30
_MAX_PUSH_PAYLOAD_BYTES = 3500
_INBOX_HISTORY_DAYS = 3
_scheduler_lock = threading.Lock()
_scheduler_started = False


@dataclass(frozen=True)
class PushCandidate:
    key: str
    title: str
    body: str
    navigate_path: str
    tag: str
    user_id: int | None = None


def _base64url(raw_value: bytes) -> str:
    return base64.urlsafe_b64encode(raw_value).rstrip(b"=").decode("ascii")


def _generate_vapid_key_pair() -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_number = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_point = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return _base64url(private_number), _base64url(public_point)


def init_web_push_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS web_push_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                private_key TEXT NOT NULL,
                public_key TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS web_push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                app_origin TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_web_push_subscriptions_user
            ON web_push_subscriptions (user_id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS web_push_deliveries (
                notification_key TEXT NOT NULL,
                subscription_id INTEGER NOT NULL,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (notification_key, subscription_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS web_push_user_deliveries (
                notification_key TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (notification_key, user_id)
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO web_push_user_deliveries (
                notification_key,
                user_id,
                sent_at
            )
            SELECT
                deliveries.notification_key,
                subscriptions.user_id,
                MIN(deliveries.sent_at)
            FROM web_push_deliveries AS deliveries
            JOIN web_push_subscriptions AS subscriptions
                ON subscriptions.id = deliveries.subscription_id
            GROUP BY deliveries.notification_key, subscriptions.user_id
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS web_push_inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                notification_key TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                navigate_path TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                read_at TEXT,
                UNIQUE (user_id, notification_key)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_web_push_inbox_user_unread
            ON web_push_inbox (user_id, read_at, id DESC)
            """
        )

        config_row = conn.execute("SELECT id FROM web_push_config WHERE id = 1").fetchone()
        if not config_row:
            private_key, public_key = _generate_vapid_key_pair()
            conn.execute(
                """
                INSERT OR IGNORE INTO web_push_config (id, private_key, public_key)
                VALUES (1, ?, ?)
                """,
                (private_key, public_key),
            )

        conn.execute(
            "DELETE FROM web_push_deliveries WHERE sent_at < datetime('now', '-90 days')"
        )
        conn.execute(
            "DELETE FROM web_push_user_deliveries WHERE sent_at < datetime('now', '-90 days')"
        )
        conn.execute(
            "DELETE FROM web_push_inbox WHERE created_at < datetime('now', '-90 days')"
        )
        conn.commit()
    finally:
        conn.close()


def get_vapid_public_key() -> str:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT public_key FROM web_push_config WHERE id = 1"
        ).fetchone()
        return (row["public_key"] if row else "") or ""
    finally:
        conn.close()


def _get_vapid_private_key() -> str:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT private_key FROM web_push_config WHERE id = 1"
        ).fetchone()
        return (row["private_key"] if row else "") or ""
    finally:
        conn.close()


def _normalize_origin(value: str) -> str:
    parsed = urlsplit((value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Некорректный адрес веб-приложения.")
    if parsed.username or parsed.password:
        raise ValueError("Некорректный адрес веб-приложения.")
    return f"{parsed.scheme}://{parsed.netloc}"


def _validated_subscription(payload: dict) -> tuple[str, str, str]:
    endpoint = str(payload.get("endpoint") or "").strip()
    keys = payload.get("keys") if isinstance(payload.get("keys"), dict) else {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()

    if not endpoint.startswith("https://") or len(endpoint) > 4096:
        raise ValueError("Некорректный адрес push-подписки.")
    if not 40 <= len(p256dh) <= 512 or not 8 <= len(auth) <= 256:
        raise ValueError("Некорректные ключи push-подписки.")
    return endpoint, p256dh, auth


def save_subscription(user_id: int, payload: dict, app_origin: str) -> None:
    endpoint, p256dh, auth = _validated_subscription(payload)
    origin = _normalize_origin(app_origin)
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO web_push_subscriptions (
                user_id, endpoint, p256dh, auth, app_origin
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET
                user_id = excluded.user_id,
                p256dh = excluded.p256dh,
                auth = excluded.auth,
                app_origin = excluded.app_origin,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, endpoint, p256dh, auth, origin),
        )
        conn.commit()
    finally:
        conn.close()


def delete_subscription(user_id: int, endpoint: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM web_push_subscriptions WHERE user_id = ? AND endpoint = ?",
            (user_id, endpoint),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "DELETE FROM web_push_deliveries WHERE subscription_id = ?",
            (row["id"],),
        )
        conn.execute(
            "DELETE FROM web_push_subscriptions WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def has_subscription(user_id: int, endpoint: str) -> bool:
    if not endpoint:
        return False
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM web_push_subscriptions
            WHERE user_id = ? AND endpoint = ?
            LIMIT 1
            """,
            (user_id, endpoint),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _get_subscriptions(user_id: int | None = None, endpoint: str | None = None):
    clauses = []
    params: list[object] = []
    if user_id is not None:
        clauses.append("user_id = ?")
        params.append(user_id)
    if endpoint is not None:
        clauses.append("endpoint = ?")
        params.append(endpoint)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = get_connection()
    try:
        return conn.execute(
            f"""
            SELECT id, user_id, endpoint, p256dh, auth, app_origin, updated_at
            FROM web_push_subscriptions
            {where_sql}
            ORDER BY user_id ASC, updated_at DESC, id DESC
            """,
            tuple(params),
        ).fetchall()
    finally:
        conn.close()


def _get_timezone():
    try:
        return ZoneInfo(_TIMEZONE_NAME)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=3), name=_TIMEZONE_NAME)


def _summary_is_due(now_local: datetime, hour: int) -> bool:
    scheduled = datetime.combine(
        now_local.date(),
        datetime_time(hour=hour),
        tzinfo=now_local.tzinfo,
    )
    return scheduled <= now_local < scheduled + _SUMMARY_WINDOW


def _schedule_url(target_date: date, calendar_type: str = "personal") -> str:
    return (
        f"/planner.schedule?calendar={calendar_type}&view=day&date="
        f"{target_date.isoformat()}"
    )


def _is_workday(target_date: date) -> bool:
    return target_date.weekday() < 5


def _table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            (table_name,),
        ).fetchone()
    )


def _get_due_task_candidates(
    now_local: datetime,
    user_ids=None,
) -> list[PushCandidate]:
    today = now_local.date()
    tomorrow = today + timedelta(days=1)
    conn = get_connection()
    try:
        schedule_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(schedule_tasks)").fetchall()
        }
        workout_owner_select = (
            "workout_user_id"
            if "workout_user_id" in schedule_columns
            else "NULL AS workout_user_id"
        )
        tasks = conn.execute(
            f"""
            SELECT id, title, task_date, start_time, {workout_owner_select}
            FROM schedule_tasks
            WHERE task_date BETWEEN ? AND ?
              AND status = 'planned'
              AND calendar_type = 'personal'
              AND start_time IS NOT NULL
              AND TRIM(start_time) <> ''
            ORDER BY task_date ASC, start_time ASC, id ASC
            """,
            (today.isoformat(), tomorrow.isoformat()),
        ).fetchall()
    finally:
        conn.close()

    candidates = []
    for task in tasks:
        try:
            task_date = date.fromisoformat(task["task_date"])
            task_time = datetime.strptime(task["start_time"].strip(), "%H:%M").time()
        except (TypeError, ValueError):
            continue

        starts_at = datetime.combine(task_date, task_time, tzinfo=now_local.tzinfo)
        reminder_at = starts_at - timedelta(hours=2)
        if not reminder_at <= now_local < reminder_at + _SUMMARY_WINDOW:
            continue

        title = (task["title"] or "Без названия").strip()
        event_key = f"task:{task['id']}:{task_date.isoformat()}:{task_time.strftime('%H:%M')}"
        candidates.append(
            PushCandidate(
                key=event_key,
                title="Задача через 2 часа",
                body=f"{task_time.strftime('%H:%M')} — {title}",
                navigate_path=_schedule_url(task_date),
                tag=event_key,
                user_id=(
                    int(task["workout_user_id"])
                    if task["workout_user_id"] is not None
                    else None
                ),
            )
        )
    return candidates


def _learning_course_reminder(
    conn,
    user_id: int,
    course_key: str,
    course_title: str,
    now_local: datetime,
) -> dict | None:
    progress_table = f"{course_key}_course_progress"
    final_table = f"{course_key}_final_results"
    existing_tables = {
        row["name"]
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name IN (?, ?)
            """,
            (progress_table, final_table),
        ).fetchall()
    }
    if {progress_table, final_table} - existing_tables:
        return None

    local_day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    utc_day_start = local_day_start.astimezone(timezone.utc).replace(tzinfo=None)
    utc_day_end = (local_day_start + timedelta(days=1)).astimezone(timezone.utc).replace(
        tzinfo=None
    )
    timestamp_params = (
        utc_day_start.strftime("%Y-%m-%d %H:%M:%S"),
        utc_day_end.strftime("%Y-%m-%d %H:%M:%S"),
    )

    final_result = conn.execute(
        f"""
        SELECT passed, updated_at
        FROM {final_table}
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if final_result and bool(final_result["passed"]):
        return None

    attempted_today = bool(
        conn.execute(
            f"""
            SELECT 1
            FROM {progress_table}
            WHERE user_id = ?
              AND updated_at >= ?
              AND updated_at < ?
            LIMIT 1
            """,
            (user_id, *timestamp_params),
        ).fetchone()
    )
    if (
        final_result
        and final_result["updated_at"]
        and timestamp_params[0] <= final_result["updated_at"] < timestamp_params[1]
    ):
        attempted_today = True
    if attempted_today:
        return None

    passed_rows = conn.execute(
        f"""
        SELECT day_number
        FROM {progress_table}
        WHERE user_id = ? AND passed = 1
        """,
        (user_id,),
    ).fetchall()
    passed_days = {int(row["day_number"]) for row in passed_rows}
    if len(passed_days) >= 30:
        return {
            "label": f"{course_title} — итоговый тест",
            "navigate_path": f"/study/{course_key}/final",
        }

    next_day = next(day for day in range(1, 31) if day not in passed_days)
    return {
        "label": f"{course_title} — день {next_day}",
        "navigate_path": f"/study/{course_key}/day/{next_day}",
    }


def _get_due_learning_candidates(
    now_local: datetime,
    user_ids,
) -> list[PushCandidate]:
    if not _summary_is_due(now_local, _LEARNING_REMINDER_HOUR):
        return []

    safe_user_ids = sorted({int(user_id) for user_id in user_ids})
    if not safe_user_ids:
        return []

    candidates: list[PushCandidate] = []
    conn = get_connection()
    try:
        for user_id in safe_user_ids:
            reminders = [
                reminder
                for reminder in (
                    _learning_course_reminder(
                        conn,
                        user_id,
                        "english",
                        "English",
                        now_local,
                    ),
                    _learning_course_reminder(
                        conn,
                        user_id,
                        "it",
                        "IT",
                        now_local,
                    ),
                )
                if reminder
            ]
            if not reminders:
                continue

            labels = [reminder["label"] for reminder in reminders]
            if len(labels) == 1:
                body = f"Сегодня ещё не пройден тест: {labels[0]}."
                navigate_path = reminders[0]["navigate_path"]
            else:
                body = "Сегодня ещё не пройдены тесты: " + " и ".join(labels) + "."
                navigate_path = "/study"

            notification_date = now_local.date().isoformat()
            candidates.append(
                PushCandidate(
                    key=f"learning:daily:{notification_date}",
                    title="Шанс — время учиться",
                    body=body,
                    navigate_path=navigate_path,
                    tag=f"learning-daily-{notification_date}",
                    user_id=user_id,
                )
            )
    finally:
        conn.close()
    return candidates


def _get_due_nutrition_candidates(
    now_local: datetime,
    user_ids,
) -> list[PushCandidate]:
    if not _summary_is_due(now_local, _DAILY_HEALTH_REMINDER_HOUR):
        return []

    safe_user_ids = sorted({int(user_id) for user_id in user_ids})
    if not safe_user_ids:
        return []

    target_date = now_local.date()
    candidates: list[PushCandidate] = []
    conn = get_connection()
    try:
        if not _table_exists(conn, "nutrition_entries"):
            return []

        for user_id in safe_user_ids:
            entry_exists = conn.execute(
                """
                SELECT 1
                FROM nutrition_entries
                WHERE user_id = ? AND eaten_on = ?
                LIMIT 1
                """,
                (user_id, target_date.isoformat()),
            ).fetchone()
            if entry_exists:
                continue

            candidates.append(
                PushCandidate(
                    key=f"nutrition:missing:{target_date.isoformat()}",
                    title="Шанс — питание за сегодня",
                    body="За сегодня в разделе питания ещё нет ни одной записи.",
                    navigate_path=f"/nutrition?date={target_date.isoformat()}#add-food-entry",
                    tag=f"nutrition-missing-{target_date.isoformat()}",
                    user_id=user_id,
                )
            )
    finally:
        conn.close()
    return candidates


def _get_due_workout_result_candidates(
    now_local: datetime,
    user_ids,
) -> list[PushCandidate]:
    if not _summary_is_due(now_local, _DAILY_HEALTH_REMINDER_HOUR):
        return []

    safe_user_ids = sorted({int(user_id) for user_id in user_ids})
    if not safe_user_ids:
        return []

    target_date = now_local.date()
    placeholders = ", ".join("?" for _user_id in safe_user_ids)
    candidates: list[PushCandidate] = []
    conn = get_connection()
    try:
        if not (
            _table_exists(conn, "schedule_tasks")
            and _table_exists(conn, "workout_results")
        ):
            return []

        schedule_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(schedule_tasks)").fetchall()
        }
        if not {"workout_plan_id", "workout_user_id"}.issubset(schedule_columns):
            return []

        rows = conn.execute(
            f"""
            SELECT DISTINCT
                tasks.workout_user_id AS user_id,
                tasks.workout_plan_id AS plan_id,
                tasks.title AS workout_name
            FROM schedule_tasks AS tasks
            WHERE tasks.task_date = ?
              AND tasks.calendar_type = 'personal'
              AND tasks.workout_plan_id IS NOT NULL
              AND tasks.workout_user_id IN ({placeholders})
              AND NOT EXISTS (
                  SELECT 1
                  FROM workout_results AS results
                  WHERE results.user_id = tasks.workout_user_id
                    AND results.workout_plan_id = tasks.workout_plan_id
                    AND results.performed_on = tasks.task_date
                  LIMIT 1
              )
            ORDER BY tasks.workout_user_id ASC, tasks.id ASC
            """,
            (target_date.isoformat(), *safe_user_ids),
        ).fetchall()

        missed_by_user: dict[int, list[str]] = {}
        for row in rows:
            user_id = int(row["user_id"])
            workout_name = (row["workout_name"] or "тренировка").strip()
            if workout_name not in missed_by_user.setdefault(user_id, []):
                missed_by_user[user_id].append(workout_name)

        for user_id, workout_names in missed_by_user.items():
            if len(workout_names) == 1:
                body = (
                    f"Сегодня была тренировка «{workout_names[0]}», "
                    "но данные по упражнениям ещё не внесены."
                )
            else:
                body = (
                    "Сегодня были тренировки без данных по упражнениям: "
                    + ", ".join(workout_names)
                    + "."
                )

            candidates.append(
                PushCandidate(
                    key=f"workout-results:missing:{target_date.isoformat()}",
                    title="Шанс — отчёт по тренировке",
                    body=body,
                    navigate_path="/workouts",
                    tag=f"workout-results-missing-{target_date.isoformat()}",
                    user_id=user_id,
                )
            )
    finally:
        conn.close()
    return candidates


def collect_due_candidates(
    now_local: datetime | None = None,
    user_ids=None,
) -> list[PushCandidate]:
    now_local = now_local or datetime.now(_get_timezone())
    if now_local.tzinfo is None:
        now_local = now_local.replace(tzinfo=_get_timezone())

    candidates: list[PushCandidate] = []
    safe_user_ids = (
        sorted({int(user_id) for user_id in user_ids})
        if user_ids is not None
        else []
    )

    if _summary_is_due(now_local, 10):
        target_date = now_local.date()
        summary_users = safe_user_ids or [None]
        for user_id in summary_users:
            candidates.append(
                PushCandidate(
                    key=f"summary:today:{target_date.isoformat()}",
                    title="Шанс — личный график",
                    body=build_personal_tasks_text(
                        target_date,
                        "сегодня",
                        user_id,
                    ),
                    navigate_path=_schedule_url(target_date),
                    tag=f"summary-today-{target_date.isoformat()}",
                    user_id=user_id,
                )
            )

    if _is_workday(now_local.date()) and _summary_is_due(now_local, _WORK_SUMMARY_HOUR):
        target_date = now_local.date()
        summary_users = safe_user_ids or [None]
        for user_id in summary_users:
            candidates.append(
                PushCandidate(
                    key=f"work-summary:today:{target_date.isoformat()}",
                    title="Шанс — рабочий график",
                    body=build_work_tasks_text(target_date, "сегодня"),
                    navigate_path=_schedule_url(target_date, "work"),
                    tag=f"work-summary-today-{target_date.isoformat()}",
                    user_id=user_id,
                )
            )

    if _summary_is_due(now_local, 20):
        target_date = now_local.date() + timedelta(days=1)
        summary_users = safe_user_ids or [None]
        for user_id in summary_users:
            candidates.append(
                PushCandidate(
                    key=f"summary:tomorrow:{target_date.isoformat()}",
                    title="Шанс — личный график",
                    body=build_personal_tasks_text(
                        target_date,
                        "завтра",
                        user_id,
                    ),
                    navigate_path=_schedule_url(target_date),
                    tag=f"summary-tomorrow-{target_date.isoformat()}",
                    user_id=user_id,
                )
            )

    candidates.extend(_get_due_task_candidates(now_local, user_ids=user_ids))
    if user_ids is not None:
        candidates.extend(_get_due_learning_candidates(now_local, user_ids))
        candidates.extend(_get_due_nutrition_candidates(now_local, user_ids))
        candidates.extend(_get_due_workout_result_candidates(now_local, user_ids))
    return candidates


def _build_declarative_payload(candidate: PushCandidate, app_origin: str) -> str:
    navigate_url = urljoin(f"{app_origin}/", candidate.navigate_path.lstrip("/"))
    notification = {
        "title": candidate.title,
        "lang": "ru",
        "dir": "auto",
        "body": candidate.body,
        "navigate": navigate_url,
        "silent": False,
        "tag": candidate.tag,
        "icon": urljoin(f"{app_origin}/", "static/pwa-icon-512-shans-v2.png"),
    }
    payload = {"web_push": 8030, "notification": notification}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) <= _MAX_PUSH_PAYLOAD_BYTES:
        return encoded

    original_body = candidate.body
    low, high = 0, len(original_body)
    while low < high:
        middle = (low + high + 1) // 2
        notification["body"] = f"{original_body[:middle].rstrip()}\n…"
        candidate_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(candidate_payload.encode("utf-8")) <= _MAX_PUSH_PAYLOAD_BYTES:
            low = middle
        else:
            high = middle - 1
    notification["body"] = f"{original_body[:low].rstrip()}\n…"
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _vapid_subject_for_subscription(subscription) -> str:
    configured_subject = str(
        current_app.config.get("WEB_PUSH_VAPID_SUBJECT") or ""
    ).strip()
    parsed_subject = urlsplit(configured_subject)
    mail_address = parsed_subject.path.lower()
    has_valid_configured_subject = (
        (
            parsed_subject.scheme == "https"
            and bool(parsed_subject.netloc)
            and not parsed_subject.username
            and not parsed_subject.password
        )
        or (
            parsed_subject.scheme == "mailto"
            and "@" in mail_address
            and not mail_address.endswith(".local")
        )
    )
    if has_valid_configured_subject:
        return configured_subject
    return _normalize_origin(subscription["app_origin"])


def _web_push_error_details(exc: WebPushException) -> tuple[int | None, str]:
    response = getattr(exc, "response", None)
    if response is None:
        return None, ""

    status_code = getattr(response, "status_code", None)
    reason = ""
    try:
        response_payload = response.json()
        if isinstance(response_payload, dict):
            reason = str(
                response_payload.get("reason")
                or response_payload.get("message")
                or ""
            )
    except (TypeError, ValueError):
        pass

    if not reason:
        reason = str(getattr(response, "text", "") or "")
    reason = " ".join(reason.split())[:160]
    return status_code if isinstance(status_code, int) else None, reason


def _log_web_push_error(exc: WebPushException, subscription) -> tuple[int | None, str]:
    status_code, reason = _web_push_error_details(exc)
    endpoint_host = urlsplit(subscription["endpoint"]).netloc
    if has_app_context():
        current_app.logger.warning(
            "Web Push request rejected: status=%s reason=%s endpoint_host=%s",
            status_code or "unknown",
            reason or "unknown",
            endpoint_host or "unknown",
        )
    return status_code, reason


def _subscription_must_be_reset(status_code: int | None) -> bool:
    return status_code in {401, 403, 404, 410}


def _send_to_subscription(subscription, candidate: PushCandidate) -> None:
    payload = _build_declarative_payload(candidate, subscription["app_origin"])
    webpush(
        subscription_info={
            "endpoint": subscription["endpoint"],
            "keys": {
                "p256dh": subscription["p256dh"],
                "auth": subscription["auth"],
            },
        },
        data=payload,
        vapid_private_key=_get_vapid_private_key(),
        vapid_claims={
            "sub": _vapid_subject_for_subscription(subscription),
        },
        headers={"Urgency": "high"},
        ttl=3600,
        timeout=15,
    )


def _reserve_user_delivery(notification_key: str, user_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO web_push_user_deliveries (
                notification_key, user_id
            ) VALUES (?, ?)
            """,
            (notification_key, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def _release_user_delivery(notification_key: str, user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            DELETE FROM web_push_user_deliveries
            WHERE notification_key = ? AND user_id = ?
            """,
            (notification_key, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def _remove_expired_subscription(subscription_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM web_push_deliveries WHERE subscription_id = ?",
            (subscription_id,),
        )
        conn.execute(
            "DELETE FROM web_push_subscriptions WHERE id = ?",
            (subscription_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _save_inbox_notification(user_id: int, candidate: PushCandidate) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO web_push_inbox (
                user_id,
                notification_key,
                title,
                body,
                navigate_path
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                candidate.key,
                candidate.title,
                candidate.body,
                candidate.navigate_path,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_unread_push_notifications(user_id: int, limit: int = 20) -> tuple[list[dict], int]:
    safe_limit = max(1, min(int(limit), 50))
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, title, body, navigate_path, created_at
            FROM web_push_inbox
            WHERE user_id = ? AND read_at IS NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, safe_limit),
        ).fetchall()
        count_row = conn.execute(
            """
            SELECT COUNT(*) AS unread_count
            FROM web_push_inbox
            WHERE user_id = ? AND read_at IS NULL
            """,
            (user_id,),
        ).fetchone()
        return [dict(row) for row in rows], int(count_row["unread_count"] if count_row else 0)
    finally:
        conn.close()


def get_recent_push_notifications(
    user_id: int,
    days: int = _INBOX_HISTORY_DAYS,
    limit: int = 50,
) -> tuple[list[dict], int]:
    safe_days = max(1, min(int(days), 30))
    safe_limit = max(1, min(int(limit), 100))
    history_window = f"-{safe_days} days"
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, title, body, navigate_path, created_at, read_at
            FROM web_push_inbox
            WHERE user_id = ?
              AND created_at >= datetime('now', ?)
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, history_window, safe_limit),
        ).fetchall()
        count_row = conn.execute(
            """
            SELECT COUNT(*) AS unread_count
            FROM web_push_inbox
            WHERE user_id = ?
              AND read_at IS NULL
              AND created_at >= datetime('now', ?)
            """,
            (user_id, history_window),
        ).fetchone()
        return [dict(row) for row in rows], int(count_row["unread_count"] if count_row else 0)
    finally:
        conn.close()


def mark_all_push_notifications_read(user_id: int) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE web_push_inbox
            SET read_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND read_at IS NULL
            """,
            (user_id,),
        )
        conn.commit()
        return max(cursor.rowcount, 0)
    finally:
        conn.close()


def delete_push_notification(user_id: int, notification_id: int) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            DELETE FROM web_push_inbox
            WHERE user_id = ? AND id = ?
            """,
            (user_id, notification_id),
        )
        conn.commit()
        return max(cursor.rowcount, 0)
    finally:
        conn.close()


def delete_all_push_notifications(user_id: int) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            DELETE FROM web_push_inbox
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()
        return max(cursor.rowcount, 0)
    finally:
        conn.close()


def deliver_candidate(candidate: PushCandidate, subscriptions=None) -> tuple[int, int]:
    subscriptions = subscriptions if subscriptions is not None else _get_subscriptions()
    sent_count = 0
    failed_count = 0
    subscriptions_by_user: dict[int, list] = {}
    for subscription in subscriptions:
        user_id = int(subscription["user_id"])
        subscriptions_by_user.setdefault(user_id, []).append(subscription)

    for user_id, user_subscriptions in subscriptions_by_user.items():
        if candidate.user_id is not None and user_id != candidate.user_id:
            continue
        if not _reserve_user_delivery(candidate.key, user_id):
            continue
        delivered = False
        for subscription in user_subscriptions:
            subscription_id = subscription["id"]
            try:
                _send_to_subscription(subscription, candidate)
                sent_count += 1
                delivered = True
                break
            except WebPushException as exc:
                status_code, _ = _log_web_push_error(exc, subscription)
                if _subscription_must_be_reset(status_code):
                    _remove_expired_subscription(subscription_id)
                    if status_code in {404, 410}:
                        continue
                break
            except Exception as exc:
                if has_app_context():
                    current_app.logger.exception(
                        "Web Push delivery failed before provider response: endpoint_host=%s error=%s",
                        urlsplit(subscription["endpoint"]).netloc or "unknown",
                        exc,
                    )
                break

        if not delivered:
            _release_user_delivery(candidate.key, user_id)
            failed_count += 1
            continue

        try:
            _save_inbox_notification(user_id, candidate)
        except Exception as exc:
            if has_app_context():
                current_app.logger.exception(
                    "Web Push inbox persistence failed: user_id=%s notification_key=%s error=%s",
                    user_id,
                    candidate.key,
                    exc,
                )
    return sent_count, failed_count


def run_web_push_notification_cycle(
    now_local: datetime | None = None,
) -> tuple[int, int, int]:
    subscriptions = _get_subscriptions()
    if not subscriptions:
        return 0, 0, 0

    user_ids = {int(subscription["user_id"]) for subscription in subscriptions}
    candidates = collect_due_candidates(now_local, user_ids=user_ids)
    sent_count = 0
    failed_count = 0
    for candidate in candidates:
        sent, failed = deliver_candidate(candidate, subscriptions=subscriptions)
        sent_count += sent
        failed_count += failed
    return len(candidates), sent_count, failed_count


def send_test_notification(user_id: int, endpoint: str) -> tuple[bool, str]:
    subscriptions = _get_subscriptions(user_id=user_id, endpoint=endpoint)
    if not subscriptions:
        return False, "Подписка этого устройства не найдена."
    timestamp = time.time_ns()
    candidate = PushCandidate(
        key=f"test:{timestamp}",
        title="Шанс — тестовое уведомление",
        body="Уведомления личного графика работают.",
        navigate_path="/planner.schedule?calendar=personal&view=day",
        tag=f"test-{timestamp}",
    )
    try:
        _send_to_subscription(subscriptions[0], candidate)
    except WebPushException as exc:
        status_code, _ = _log_web_push_error(exc, subscriptions[0])
        if _subscription_must_be_reset(status_code):
            _remove_expired_subscription(subscriptions[0]["id"])
            return (
                False,
                "Подписка iPhone устарела. Нажмите «Включить уведомления», чтобы создать её заново.",
            )
        return False, "Push-сервис временно недоступен. Попробуйте ещё раз."
    except Exception as exc:
        if has_app_context():
            current_app.logger.exception(
                "Web Push test failed before provider response: endpoint_host=%s error=%s",
                urlsplit(subscriptions[0]["endpoint"]).netloc or "unknown",
                exc,
            )
        return False, "Не удалось отправить тестовое уведомление."
    return True, "Тестовое уведомление отправлено."


def _clean_external_push_text(value: object, fallback: str, max_length: int) -> str:
    text = str(value or "").strip() or fallback
    return text[:max_length].strip()


def _resolve_system_admin_user_ids() -> list[int]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id
            FROM users
            WHERE COALESCE(is_system_admin, 0) = 1
              AND COALESCE(is_active, 1) = 1
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        conn.close()
    user_ids = [int(row["id"]) for row in rows]
    if not user_ids:
        raise LookupError("System administrator is not configured.")
    return user_ids


def _resolve_external_push_user_ids(_payload: dict) -> list[int]:
    return _resolve_system_admin_user_ids()


def send_external_telegram_notification(payload: dict) -> tuple[int, int]:
    timestamp = time.time_ns()
    user_ids = _resolve_external_push_user_ids(payload)
    title = _clean_external_push_text(
        payload.get("title"),
        "Вк аккануты",
        80,
    )
    body = _clean_external_push_text(
        payload.get("body") or payload.get("text") or payload.get("message"),
        "Script finished.",
        800,
    )
    navigate_path = _clean_external_push_text(payload.get("navigate_path"), "/", 300)

    sent_count = 0
    failed_count = 0
    for user_id in user_ids:
        candidate = PushCandidate(
            key=f"telegram:{timestamp}:{user_id}",
            title=title,
            body=body,
            navigate_path=navigate_path,
            tag=f"telegram-{timestamp}",
            user_id=user_id,
        )
        sent, failed = deliver_candidate(candidate)
        sent_count += sent
        failed_count += failed
    return sent_count, failed_count


def _scheduler_worker(app) -> None:
    while True:
        try:
            with app.app_context():
                candidate_count, sent_count, failed_count = run_web_push_notification_cycle()
                if sent_count:
                    app.logger.info(
                        "Web Push notifications sent: candidates=%s sent=%s failed=%s",
                        candidate_count,
                        sent_count,
                        failed_count,
                    )
                elif failed_count:
                    app.logger.warning(
                        "Web Push notification failures: candidates=%s failed=%s",
                        candidate_count,
                        failed_count,
                    )
        except Exception as exc:
            app.logger.exception("Web Push scheduler failed: %s", exc)
        time.sleep(_SCHEDULER_INTERVAL_SECONDS)


def start_web_push_scheduler(app) -> None:
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    thread = threading.Thread(
        target=_scheduler_worker,
        args=(app,),
        daemon=True,
        name="web-push-scheduler",
    )
    thread.start()
    app.logger.info("Web Push scheduler started")


def register_web_push_routes(app) -> None:
    @app.get("/service-worker.js")
    def web_push_service_worker():
        response = current_app.send_static_file("service-worker.js")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/api/push/config")
    @login_required
    def web_push_config():
        return jsonify(
            {
                "publicKey": get_vapid_public_key(),
                "serviceWorkerUrl": "/service-worker.js",
            }
        )

    @app.post("/api/push/subscribe")
    @login_required
    def web_push_subscribe():
        payload = request.get_json(silent=True) or {}
        subscription = payload.get("subscription")
        if not isinstance(subscription, dict):
            return jsonify({"ok": False, "message": "Подписка не передана."}), 400
        try:
            app_origin = _normalize_origin(
                str(payload.get("origin") or request.host_url)
            )
            if urlsplit(app_origin).netloc.lower() != request.host.lower():
                raise ValueError("Адрес веб-приложения не совпадает с текущим сайтом.")
            save_subscription(
                int(current_user.id),
                subscription,
                app_origin,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        return jsonify({"ok": True, "message": "Уведомления включены."})

    @app.post("/api/push/status")
    @login_required
    def web_push_status():
        payload = request.get_json(silent=True) or {}
        endpoint = str(payload.get("endpoint") or "").strip()
        if not endpoint:
            return jsonify({"ok": True, "serverSubscribed": False})
        return jsonify(
            {
                "ok": True,
                "serverSubscribed": has_subscription(int(current_user.id), endpoint),
            }
        )

    @app.post("/api/push/unsubscribe")
    @login_required
    def web_push_unsubscribe():
        payload = request.get_json(silent=True) or {}
        endpoint = str(payload.get("endpoint") or "").strip()
        if not endpoint:
            return jsonify({"ok": False, "message": "Подписка не передана."}), 400
        delete_subscription(int(current_user.id), endpoint)
        return jsonify({"ok": True, "message": "Уведомления отключены."})

    @app.get("/api/push/inbox")
    @login_required
    def web_push_inbox():
        notifications, unread_count = get_recent_push_notifications(
            int(current_user.id)
        )
        response = jsonify(
            {
                "ok": True,
                "unreadCount": unread_count,
                "notifications": [
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "body": item["body"],
                        "navigatePath": item["navigate_path"],
                        "createdAt": item["created_at"],
                        "readAt": item["read_at"],
                        "unread": item["read_at"] is None,
                    }
                    for item in notifications
                ],
                "historyDays": _INBOX_HISTORY_DAYS,
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/push/inbox/read")
    @login_required
    def web_push_inbox_read():
        marked_count = mark_all_push_notifications_read(int(current_user.id))
        return jsonify({"ok": True, "markedCount": marked_count, "unreadCount": 0})

    @app.post("/api/push/inbox/delete")
    @login_required
    def web_push_inbox_delete():
        payload = request.get_json(silent=True) or {}
        try:
            notification_id = int(payload.get("id") or 0)
        except (TypeError, ValueError):
            notification_id = 0
        if notification_id < 1:
            return jsonify({"ok": False, "message": "Notification id is required."}), 400

        deleted_count = delete_push_notification(int(current_user.id), notification_id)
        _notifications, unread_count = get_recent_push_notifications(int(current_user.id))
        return jsonify(
            {
                "ok": True,
                "deletedCount": deleted_count,
                "unreadCount": unread_count,
            }
        )

    @app.post("/api/push/inbox/clear")
    @login_required
    def web_push_inbox_clear():
        deleted_count = delete_all_push_notifications(int(current_user.id))
        return jsonify({"ok": True, "deletedCount": deleted_count, "unreadCount": 0})

    @app.post("/api/push/test")
    @login_required
    def web_push_test():
        payload = request.get_json(silent=True) or {}
        endpoint = str(payload.get("endpoint") or "").strip()
        if not endpoint:
            return jsonify({"ok": False, "message": "Сначала включите уведомления."}), 400
        ok, message = send_test_notification(int(current_user.id), endpoint)
        reset_subscription = (
            not ok
            and not _get_subscriptions(
                user_id=int(current_user.id),
                endpoint=endpoint,
            )
        )
        return (
            jsonify(
                {
                    "ok": ok,
                    "message": message,
                    "resetSubscription": reset_subscription,
                }
            ),
            200 if ok else 502,
        )

    @app.post("/api/push/external/telegram")
    def telegram_external_push():
        configured_secret = str(
            current_app.config.get("TELEGRAM_PUSH_SECRET") or ""
        ).strip()
        request_secret = str(request.headers.get("X-Shans-Push-Secret") or "").strip()
        if not configured_secret:
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": "Telegram push secret is not configured.",
                    }
                ),
                503,
            )
        if not request_secret or not hmac.compare_digest(request_secret, configured_secret):
            return jsonify({"ok": False, "message": "Forbidden."}), 403

        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "message": "Invalid JSON payload."}), 400

        try:
            sent_count, failed_count = send_external_telegram_notification(payload)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "message": "Invalid user_id."}), 400
        except LookupError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

        ok = sent_count > 0 and failed_count == 0
        response_payload = {"ok": ok, "sent": sent_count, "failed": failed_count}
        if not ok:
            response_payload["message"] = "No Web Push subscriptions received the notification."
        return jsonify(response_payload)
