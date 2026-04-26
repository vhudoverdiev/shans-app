from __future__ import annotations

import json
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app

from app.database import get_connection

_VK_API_VERSION = "5.199"
_DEFAULT_VK_ACCESS_TOKEN = (os.getenv("VK_ACCESS_TOKEN") or "").strip()
_DEFAULT_VK_PROFILE_URL = (os.getenv("VK_PROFILE_URL") or "").strip()
_DEFAULT_TIMEZONE = (os.getenv("VK_TIMEZONE") or "Europe/Moscow").strip() or "Europe/Moscow"
_DAILY_NOTIFICATION_HOUR = 20
_DAILY_NOTIFICATION_MINUTE = 0
_scheduler_lock = threading.Lock()
_scheduler_started = False

def _table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}



def init_vk_notifications_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vk_notification_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            is_enabled INTEGER NOT NULL DEFAULT 1,
            access_token TEXT,
            profile_url TEXT,
            timezone_name TEXT NOT NULL DEFAULT 'Europe/Moscow',
            last_daily_sent_date TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vk_daily_send_locks (
            send_date TEXT PRIMARY KEY,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    existing_columns = _table_columns(conn, "vk_notification_settings")
    if "timezone_name" not in existing_columns:
        cursor.execute(
            "ALTER TABLE vk_notification_settings ADD COLUMN timezone_name TEXT NOT NULL DEFAULT 'Europe/Moscow'"
        )
    if "last_daily_sent_date" not in existing_columns:
        cursor.execute(
            "ALTER TABLE vk_notification_settings ADD COLUMN last_daily_sent_date TEXT"
        )
    if "updated_at" not in existing_columns:
        cursor.execute(
            "ALTER TABLE vk_notification_settings ADD COLUMN updated_at TEXT DEFAULT CURRENT_TIMESTAMP"
        )

    row = cursor.execute("SELECT id FROM vk_notification_settings WHERE id = 1").fetchone()
    if not row:
        cursor.execute(
            """
            INSERT INTO vk_notification_settings (
                id, is_enabled, access_token, profile_url, timezone_name, last_daily_sent_date
            ) VALUES (1, 1, ?, ?, ?, NULL)
            """
            ,
            (_DEFAULT_VK_ACCESS_TOKEN, _DEFAULT_VK_PROFILE_URL, _DEFAULT_TIMEZONE),
        )

    conn.commit()
    conn.close()


def get_vk_settings():
    conn = get_connection()
    row = conn.execute(
        """
        SELECT
            id,
            is_enabled,
            access_token,
            profile_url,
            timezone_name,
            last_daily_sent_date,
            updated_at
        FROM vk_notification_settings
        WHERE id = 1
        """
    ).fetchone()
    conn.close()
    return row


def update_vk_settings(is_enabled: bool, access_token: str, profile_url: str, timezone_name: str):
    conn = get_connection()
    conn.execute(
        """
        UPDATE vk_notification_settings
        SET is_enabled = ?, access_token = ?, profile_url = ?, timezone_name = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
        """,
        (1 if is_enabled else 0, (access_token or "").strip(), (profile_url or "").strip(), (timezone_name or "").strip() or "Europe/Moscow"),
    )
    conn.commit()
    conn.close()


def _get_target_timezone():
    settings = get_vk_settings()
    tz_name = settings["timezone_name"] if settings and settings["timezone_name"] else "Europe/Moscow"
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        # Fallback для окружений без tzdata (например, Python на Windows без пакета tzdata).
        # Для Москвы используется фиксированный UTC+3 (без сезонного перевода времени).
        return timezone(timedelta(hours=3), name="Europe/Moscow")


def _extract_screen_name(profile_url: str) -> str:
    cleaned = (profile_url or "").strip()
    if not cleaned:
        return ""
    if "vk.com/" in cleaned:
        cleaned = cleaned.split("vk.com/", 1)[1]
    return cleaned.strip("/ ")


def _vk_api(method: str, params: dict) -> dict:
    query = urlencode(params)
    url = f"https://api.vk.com/method/{method}?{query}"
    with urlopen(url, timeout=15) as response:
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    if "error" in payload:
        error = payload["error"]
        raise RuntimeError(f"VK API error {error.get('error_code')}: {error.get('error_msg')}")
    return payload.get("response", {})


def _resolve_vk_user_id(profile_url: str) -> int:
    screen_name = _extract_screen_name(profile_url)
    if not screen_name:
        raise RuntimeError("Не указан адрес страницы VK.")

    response = _vk_api(
        "utils.resolveScreenName",
        {
            "screen_name": screen_name,
            "v": _VK_API_VERSION,
        },
    )
    if response and response.get("type") == "user" and response.get("object_id"):
        return int(response["object_id"])

    users = _vk_api(
        "users.get",
        {
            "user_ids": screen_name,
            "v": _VK_API_VERSION,
        },
    )
    if isinstance(users, list) and users:
        return int(users[0]["id"])

    raise RuntimeError("Не удалось определить ID пользователя VK.")


def _build_tomorrow_tasks_text(now_local: datetime) -> str:
    tomorrow = now_local.date() + timedelta(days=1)
    tomorrow_key = tomorrow.isoformat()
    conn = get_connection()
    tasks = conn.execute(
        """
        SELECT title, start_time, description, task_type
        FROM schedule_tasks
        WHERE task_date = ? AND status = 'planned'
        ORDER BY COALESCE(start_time, '99:99') ASC, id ASC
        """,
        (tomorrow_key,),
    ).fetchall()
    conn.close()

    header = f"Задачи на завтра ({tomorrow.strftime('%d.%m.%Y')}):"
    if not tasks:
        return f"{header}\nЗадач нет."

    lines = [header, ""]
    for idx, task in enumerate(tasks, start=1):
        title = (task["title"] or "Без названия").strip()
        start_time = (task["start_time"] or "").strip()
        time_part = start_time if start_time else "—"
        lines.append(f"{idx}. {time_part} — {title}")

    lines.extend(["", f"Всего задач: {len(tasks)}"])
    return "\n".join(lines)


def send_vk_tomorrow_tasks_message(force: bool = False) -> tuple[bool, str]:
    settings = get_vk_settings()
    if not settings:
        return False, "Настройки VK не найдены."

    if not force and not settings["is_enabled"]:
        return False, "VK-уведомления отключены."

    access_token = (settings["access_token"] or "").strip()
    profile_url = (settings["profile_url"] or "").strip()
    if not access_token or not profile_url:
        return False, "Заполни токен и ссылку на страницу VK."

    tz = _get_target_timezone()
    now_local = datetime.now(tz)
    message_text = _build_tomorrow_tasks_text(now_local)

    try:
        user_id = _resolve_vk_user_id(profile_url)
        _vk_api(
            "messages.send",
            {
                "user_id": user_id,
                "message": message_text,
                "random_id": int(time.time() * 1000) % 2_000_000_000,
                "access_token": access_token,
                "v": _VK_API_VERSION,
            },
        )
    except Exception as exc:
        error_text = str(exc)
        if "VK API error 38" in error_text:
            return False, (
                "VK API error 38: токен привязан к несуществующему/недоступному приложению. "
                "Сгенерируй новый токен сообщества (group token) и обнови VK_ACCESS_TOKEN."
            )
        if "VK API error 5" in error_text:
            return False, "VK API error 5: ошибка авторизации. Проверь корректность VK_ACCESS_TOKEN."
        if "VK API error 901" in error_text:
            return False, (
                "VK API error 901: пользователь запретил сообщения от сообщества. "
                "Напиши сообществу в VK первым и разреши сообщения."
            )
        return False, error_text

    if not force:
        conn = get_connection()
        conn.execute(
            "UPDATE vk_notification_settings SET last_daily_sent_date = ? WHERE id = 1",
            (now_local.date().isoformat(),),
        )
        conn.commit()
        conn.close()
    return True, "Уведомление отправлено в VK."


def run_vk_daily_notification_cycle() -> tuple[bool, str]:
    settings = get_vk_settings()
    if not settings or not settings["is_enabled"]:
        return False, "VK-уведомления выключены"

    tz = _get_target_timezone()
    now_local = datetime.now(tz)
    today_key = now_local.date().isoformat()
    last_sent = (settings["last_daily_sent_date"] or "").strip()

    if (now_local.hour, now_local.minute) < (_DAILY_NOTIFICATION_HOUR, _DAILY_NOTIFICATION_MINUTE):
        return False, "Ещё не время отправки"

    if last_sent == today_key:
        return False, "Уже отправлено сегодня"

    if not _reserve_daily_send_slot(today_key):
        return False, "Уже отправляется или отправлено другим процессом"

    ok, reason = send_vk_tomorrow_tasks_message(force=False)
    if not ok:
        _release_daily_send_slot(today_key)
    return ok, reason


def _reserve_daily_send_slot(today_key: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO vk_daily_send_locks (send_date) VALUES (?)",
            (today_key,),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def _release_daily_send_slot(today_key: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM vk_daily_send_locks WHERE send_date = ?", (today_key,))
        conn.commit()
    finally:
        conn.close()


def _scheduler_worker(app):
    while True:
        try:
            with app.app_context():
                ok, reason = run_vk_daily_notification_cycle()
                if ok:
                    app.logger.info("VK daily notification sent successfully")
                else:
                    app.logger.debug("VK daily notification skipped: %s", reason)
        except Exception as exc:
            app.logger.exception("VK daily scheduler failed: %s", exc)
        time.sleep(30)


def start_vk_scheduler(app):
    global _scheduler_started

    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    thread = threading.Thread(target=_scheduler_worker, args=(app,), daemon=True, name="vk-daily-scheduler")
    thread.start()
    app.logger.info("VK daily scheduler started")


def diagnose_vk_notifications(check_remote: bool = False) -> dict:
    settings = get_vk_settings()
    tz = _get_target_timezone()
    now_local = datetime.now(tz)
    today_key = now_local.date().isoformat()

    diagnostics = {
        "settings_found": bool(settings),
        "enabled": bool(settings["is_enabled"]) if settings else False,
        "timezone": settings["timezone_name"] if settings and settings["timezone_name"] else "Europe/Moscow",
        "now_local": now_local.isoformat(),
        "send_time": f"{_DAILY_NOTIFICATION_HOUR:02d}:{_DAILY_NOTIFICATION_MINUTE:02d}",
        "time_gate_open": (now_local.hour, now_local.minute) >= (_DAILY_NOTIFICATION_HOUR, _DAILY_NOTIFICATION_MINUTE),
        "last_daily_sent_date": (settings["last_daily_sent_date"] if settings else None),
        "already_sent_today": ((settings["last_daily_sent_date"] or "") == today_key) if settings else False,
        "token_present": False,
        "token_masked": "",
        "profile_url": (settings["profile_url"] or "").strip() if settings else "",
        "lock_exists_today": False,
    }

    if settings:
        token = (settings["access_token"] or "").strip()
        diagnostics["token_present"] = bool(token)
        if token:
            diagnostics["token_masked"] = f"{token[:6]}...{token[-4:]}" if len(token) > 12 else "***"

    conn = get_connection()
    lock_row = conn.execute(
        "SELECT send_date FROM vk_daily_send_locks WHERE send_date = ?",
        (today_key,),
    ).fetchone()
    conn.close()
    diagnostics["lock_exists_today"] = bool(lock_row)

    if check_remote and settings and diagnostics["token_present"] and diagnostics["profile_url"]:
        try:
            user_id = _resolve_vk_user_id(diagnostics["profile_url"])
            diagnostics["remote_check_ok"] = True
            diagnostics["resolved_user_id"] = user_id
        except Exception as exc:
            diagnostics["remote_check_ok"] = False
            diagnostics["remote_error"] = str(exc)

    return diagnostics
