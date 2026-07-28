from __future__ import annotations

from datetime import date

from app.database import get_connection


def get_tasks_for_date(
    target_date: date,
    calendar_type: str,
    user_id: int | None = None,
):
    conn = get_connection()
    try:
        workout_owner_clause = ""
        parameters: list[object] = [target_date.isoformat(), calendar_type]
        if calendar_type == "personal" and user_id is not None:
            workout_owner_clause = (
                "AND (workout_user_id IS NULL OR workout_user_id = ?)"
            )
            parameters.append(int(user_id))
        return conn.execute(
            f"""
            SELECT id, title, start_time, description, task_type, task_date
            FROM schedule_tasks
            WHERE task_date = ?
              AND status = 'planned'
              AND calendar_type = ?
              {workout_owner_clause}
            ORDER BY COALESCE(start_time, '99:99') ASC, id ASC
            """,
            tuple(parameters),
        ).fetchall()
    finally:
        conn.close()


def get_personal_tasks_for_date(target_date: date, user_id: int | None = None):
    return get_tasks_for_date(target_date, "personal", user_id)


def build_tasks_text(
    target_date: date,
    period_label: str,
    calendar_type: str,
    user_id: int | None = None,
) -> str:
    tasks = get_tasks_for_date(target_date, calendar_type, user_id)
    header = f"Задачи на {period_label} ({target_date.strftime('%d.%m.%Y')}):"
    if not tasks:
        return f"{header}\nЗадач нет."

    lines = [header, ""]
    for index, task in enumerate(tasks, start=1):
        title = (task["title"] or "Без названия").strip()
        start_time = (task["start_time"] or "").strip()
        if start_time:
            lines.append(f"{index}. {start_time} — {title}")
        else:
            lines.append(f"{index}. {title}")

    lines.extend(["", f"Всего задач: {len(tasks)}"])
    return "\n".join(lines)


def build_personal_tasks_text(
    target_date: date,
    period_label: str,
    user_id: int | None = None,
) -> str:
    return build_tasks_text(target_date, period_label, "personal", user_id)


def build_work_tasks_text(target_date: date, period_label: str) -> str:
    return build_tasks_text(target_date, period_label, "work")
