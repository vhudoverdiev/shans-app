from __future__ import annotations

import json
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
_HARDCODED_VK_ACCESS_TOKEN = "vk1.a.-MluYBU8Y_UJZ6NmdrIzLAvBMidKS1ru4Olm1WVGyVq0Yz-SNLBK1F9IOiCg4UJsLsc4gs0kj-EBCGM7tzZkWcStS1MavY31Q6zrfbtG2JY-m3yeicLMVhrwSdFHIfLKaq2PlsnwQuRNbAtRvbaOOna56cn86uXCcdCMCtvd1bQzeKnmxip1s3_vzBesIbsRUOYqf0XAfTtcsdeXYtPFAg"
_HARDCODED_VK_PROFILE_URL = "https://vk.com/hudoverdiev"
_HARDCODED_TIMEZONE = "Europe/Moscow"
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
            (_HARDCODED_VK_ACCESS_TOKEN, _HARDCODED_VK_PROFILE_URL, _HARDCODED_TIMEZONE),
        )
    else:
        cursor.execute(
            """
            UPDATE vk_notification_settings
            SET is_enabled = 1, access_token = ?, profile_url = ?, timezone_name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (_HARDCODED_VK_ACCESS_TOKEN, _HARDCODED_VK_PROFILE_URL, _HARDCODED_TIMEZONE),
        )

    conn.commit()
    conn.close()


def get_vk_settings():
    conn = get_connection()
    row = conn.execute(
        """
        SELECT
            id,
            1 AS is_enabled,
            ? AS access_token,
            ? AS profile_url,
            ? AS timezone_name,
            last_daily_sent_date,
            updated_at
        FROM vk_notification_settings
        WHERE id = 1
        """,
        (_HARDCODED_VK_ACCESS_TOKEN, _HARDCODED_VK_PROFILE_URL, _HARDCODED_TIMEZONE),
    ).fetchone()
    conn.close()
    return row


def update_vk_settings(is_enabled: bool, access_token: str, profile_url: str, timezone_name: str):
    # Настройки захардкожены, метод оставлен для обратной совместимости.
    return None


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


def _resolve_vk_user_id(access_token: str, profile_url: str) -> int:
    screen_name = _extract_screen_name(profile_url)
    if not screen_name:
        raise RuntimeError("Не указан адрес страницы VK.")

    response = _vk_api(
        "utils.resolveScreenName",
        {
            "screen_name": screen_name,
            "access_token": access_token,
            "v": _VK_API_VERSION,
        },
    )
    if response and response.get("type") == "user" and response.get("object_id"):
        return int(response["object_id"])

    users = _vk_api(
        "users.get",
        {
            "user_ids": screen_name,
            "access_token": access_token,
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
        SELECT title, start_time, description
        FROM schedule_tasks
        WHERE task_date = ? AND status = 'planned'
        ORDER BY COALESCE(start_time, '99:99') ASC, id ASC
        """,
        (tomorrow_key,),
    ).fetchall()
    conn.close()

    if not tasks:
        return f"График на завтра ({tomorrow.strftime('%d.%m.%Y')}): задач нет."

    lines = [f"График на завтра ({tomorrow.strftime('%d.%m.%Y')}):"]
    for idx, task in enumerate(tasks, start=1):
        title = (task["title"] or "Без названия").strip()
        start_time = (task["start_time"] or "").strip()
        description = (task["description"] or "").strip()
        time_part = f"[{start_time}] " if start_time else ""
        row = f"{idx}. {time_part}{title}"
        if description:
            short_description = description.replace("\n", " ")
            if len(short_description) > 120:
                short_description = short_description[:117] + "..."
            row += f" — {short_description}"
        lines.append(row)

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
        user_id = _resolve_vk_user_id(access_token, profile_url)
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
        return False, str(exc)

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

    if now_local.hour < 23 or (now_local.hour == 23 and now_local.minute < 59):
        return False, "Ещё не время отправки"

    if last_sent == today_key:
        return False, "Уже отправлено сегодня"

    return send_vk_tomorrow_tasks_message(force=False)


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
