from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from flask import current_app, jsonify, request
from flask_login import current_user, login_required
from pywebpush import WebPushException, webpush

from app.database import get_connection
from app.schedule_notifications import build_personal_tasks_text


_TIMEZONE_NAME = "Europe/Moscow"
_SUMMARY_WINDOW = timedelta(minutes=5)
_SCHEDULER_INTERVAL_SECONDS = 30
_MAX_PUSH_PAYLOAD_BYTES = 3500
_scheduler_lock = threading.Lock()
_scheduler_started = False


@dataclass(frozen=True)
class PushCandidate:
    key: str
    title: str
    body: str
    navigate_path: str
    tag: str


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
            SELECT id, user_id, endpoint, p256dh, auth, app_origin
            FROM web_push_subscriptions
            {where_sql}
            ORDER BY id ASC
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


def _schedule_url(target_date: date) -> str:
    return (
        "/planner.schedule?calendar=personal&view=day&date="
        f"{target_date.isoformat()}"
    )


def _get_due_task_candidates(now_local: datetime) -> list[PushCandidate]:
    today = now_local.date()
    tomorrow = today + timedelta(days=1)
    conn = get_connection()
    try:
        tasks = conn.execute(
            """
            SELECT id, title, task_date, start_time
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
            )
        )
    return candidates


def collect_due_candidates(now_local: datetime | None = None) -> list[PushCandidate]:
    now_local = now_local or datetime.now(_get_timezone())
    if now_local.tzinfo is None:
        now_local = now_local.replace(tzinfo=_get_timezone())

    candidates: list[PushCandidate] = []
    if _summary_is_due(now_local, 10):
        target_date = now_local.date()
        candidates.append(
            PushCandidate(
                key=f"summary:today:{target_date.isoformat()}",
                title="Шанс — личный график",
                body=build_personal_tasks_text(target_date, "сегодня"),
                navigate_path=_schedule_url(target_date),
                tag=f"summary-today-{target_date.isoformat()}",
            )
        )

    if _summary_is_due(now_local, 20):
        target_date = now_local.date() + timedelta(days=1)
        candidates.append(
            PushCandidate(
                key=f"summary:tomorrow:{target_date.isoformat()}",
                title="Шанс — личный график",
                body=build_personal_tasks_text(target_date, "завтра"),
                navigate_path=_schedule_url(target_date),
                tag=f"summary-tomorrow-{target_date.isoformat()}",
            )
        )

    candidates.extend(_get_due_task_candidates(now_local))
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
        "icon": urljoin(f"{app_origin}/", "static/logo.png"),
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
            "sub": current_app.config["WEB_PUSH_VAPID_SUBJECT"],
        },
        ttl=3600,
        timeout=15,
    )


def _reserve_delivery(notification_key: str, subscription_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO web_push_deliveries (
                notification_key, subscription_id
            ) VALUES (?, ?)
            """,
            (notification_key, subscription_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def _release_delivery(notification_key: str, subscription_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            DELETE FROM web_push_deliveries
            WHERE notification_key = ? AND subscription_id = ?
            """,
            (notification_key, subscription_id),
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


def deliver_candidate(candidate: PushCandidate, subscriptions=None) -> tuple[int, int]:
    subscriptions = subscriptions if subscriptions is not None else _get_subscriptions()
    sent_count = 0
    failed_count = 0
    for subscription in subscriptions:
        subscription_id = subscription["id"]
        if not _reserve_delivery(candidate.key, subscription_id):
            continue
        try:
            _send_to_subscription(subscription, candidate)
            sent_count += 1
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            if response is not None and response.status_code in {404, 410}:
                _remove_expired_subscription(subscription_id)
            else:
                _release_delivery(candidate.key, subscription_id)
                failed_count += 1
        except Exception:
            _release_delivery(candidate.key, subscription_id)
            failed_count += 1
    return sent_count, failed_count


def run_web_push_notification_cycle(
    now_local: datetime | None = None,
) -> tuple[int, int, int]:
    subscriptions = _get_subscriptions()
    if not subscriptions:
        return 0, 0, 0

    candidates = collect_due_candidates(now_local)
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
        response = getattr(exc, "response", None)
        if response is not None and response.status_code in {404, 410}:
            _remove_expired_subscription(subscriptions[0]["id"])
            return False, "Подписка устройства устарела. Включите уведомления заново."
        return False, "Push-сервис временно недоступен. Попробуйте ещё раз."
    except Exception:
        return False, "Не удалось отправить тестовое уведомление."
    return True, "Тестовое уведомление отправлено."


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

    @app.post("/api/push/unsubscribe")
    @login_required
    def web_push_unsubscribe():
        payload = request.get_json(silent=True) or {}
        endpoint = str(payload.get("endpoint") or "").strip()
        if not endpoint:
            return jsonify({"ok": False, "message": "Подписка не передана."}), 400
        delete_subscription(int(current_user.id), endpoint)
        return jsonify({"ok": True, "message": "Уведомления отключены."})

    @app.post("/api/push/test")
    @login_required
    def web_push_test():
        payload = request.get_json(silent=True) or {}
        endpoint = str(payload.get("endpoint") or "").strip()
        if not endpoint:
            return jsonify({"ok": False, "message": "Сначала включите уведомления."}), 400
        ok, message = send_test_notification(int(current_user.id), endpoint)
        return jsonify({"ok": ok, "message": message}), 200 if ok else 502
