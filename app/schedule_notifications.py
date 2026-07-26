from __future__ import annotations

from datetime import date

from app.database import get_connection


def get_personal_tasks_for_date(target_date: date, user_id: int | None = None):
    conn = get_connection()
    try:
        workout_owner_clause = ""
        parameters: list[object] = [target_date.isoformat()]
        if user_id is not None:
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
              AND calendar_type = 'personal'
              {workout_owner_clause}
            ORDER BY COALESCE(start_time, '99:99') ASC, id ASC
            """,
            tuple(parameters),
        ).fetchall()
    finally:
        conn.close()


def build_personal_tasks_text(
    target_date: date,
    period_label: str,
    user_id: int | None = None,
) -> str:
    tasks = get_personal_tasks_for_date(target_date, user_id)
    header = f"Задачи на {period_label} ({target_date.strftime('%d.%m.%Y')}):"
    if not tasks:
        return f"{header}\nЗадач нет."

    lines = [header, ""]
    for index, task in enumerate(tasks, start=1):
        title = (task["title"] or "Без названия").strip()
        start_time = (task["start_time"] or "").strip()
        lines.append(f"{index}. {start_time or '—'} — {title}")

    lines.extend(["", f"Всего задач: {len(tasks)}"])
    return "\n".join(lines)
