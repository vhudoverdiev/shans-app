from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.vk_notifier import send_vk_message

BASE_DIR = "/var/www/shans-app"
DB_PATH = os.path.join(BASE_DIR, "app.db")
LOG_PATH = os.path.join(BASE_DIR, "logs", "vk_daily.log")

VK_USER_ID = 193977785
TIMEZONE_NAME = "Europe/Moscow"


logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def get_tomorrow_date() -> str:
    now_local = datetime.now(ZoneInfo(TIMEZONE_NAME))
    tomorrow = now_local.date() + timedelta(days=1)
    return tomorrow.isoformat()


def get_tasks_for_tomorrow() -> list[sqlite3.Row]:
    tomorrow = get_tomorrow_date()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT title, start_time, description
        FROM schedule_tasks
        WHERE task_date = ?
          AND status = 'planned'
        ORDER BY COALESCE(start_time, '99:99') ASC, id ASC
        """,
        (tomorrow,),
    )

    rows = cursor.fetchall()
    conn.close()
    return rows


def build_message(tasks: list[sqlite3.Row]) -> str | None:
    if not tasks:
        return None

    now_local = datetime.now(ZoneInfo(TIMEZONE_NAME))
    tomorrow_display = (now_local.date() + timedelta(days=1)).strftime("%d.%m.%Y")

    lines = [f"Шанс — задачи на завтра ({tomorrow_display})", ""]

    for index, task in enumerate(tasks, start=1):
        title = (task["title"] or "Без названия").strip()
        start_time = (task["start_time"] or "").strip()
        description = (task["description"] or "").strip()

        if start_time:
            line = f"{index}. {start_time} — {title}"
        else:
            line = f"{index}. {title}"

        if description:
            short_description = description.replace("\n", " ")
            if len(short_description) > 120:
                short_description = short_description[:117] + "..."
            line += f" — {short_description}"

        lines.append(line)

    lines.append("")
    lines.append(f"Всего задач: {len(tasks)}")

    return "\n".join(lines)


def already_sent_today() -> bool:
    today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_type TEXT NOT NULL,
            notification_date TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        SELECT id
        FROM notification_log
        WHERE notification_type = 'vk_tomorrow_tasks'
          AND notification_date = ?
          AND status = 'success'
        LIMIT 1
        """,
        (today,),
    )

    row = cursor.fetchone()
    conn.close()
    return row is not None


def write_log(status: str, details: str) -> None:
    today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_type TEXT NOT NULL,
            notification_date TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        INSERT INTO notification_log (
            notification_type,
            notification_date,
            status,
            details
        ) VALUES (?, ?, ?, ?)
        """,
        ("vk_tomorrow_tasks", today, status, details),
    )

    conn.commit()
    conn.close()


def main() -> None:
    if VK_USER_ID == 0:
        message = "Не указан VK_USER_ID в send_vk_tomorrow_tasks.py"
        logging.error(message)
        write_log("error", message)
        print(message)
        return

    if already_sent_today():
        message = "Уведомление уже отправлялось сегодня."
        logging.info(message)
        print(message)
        return

    tasks = get_tasks_for_tomorrow()
    message_text = build_message(tasks)

    if not message_text:
        message = "На завтра задач нет."
        logging.info(message)
        write_log("skip", message)
        print(message)
        return

    success, result = send_vk_message(VK_USER_ID, message_text)

    if success:
        logging.info("VK уведомление отправлено успешно.")
        write_log("success", "Уведомление отправлено.")
        print("True ok")
    else:
        logging.error("Ошибка отправки VK: %s", result)
        write_log("error", str(result))
        print(f"False {result}")


if __name__ == "__main__":
    main()
