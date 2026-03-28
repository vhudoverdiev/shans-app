from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.database import get_connection

planner_bp = Blueprint("planner", __name__)

TASK_TYPES = ["Личное", "Съёмка", "Фотопроект", "Встреча", "Другое"]
TASK_STATUSES = ["planned", "done", "cancelled"]
PROJECT_CITIES = ["Архангельск", "Северодвинск"]


def init_planner_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schedule_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            task_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            task_type TEXT NOT NULL DEFAULT 'Личное',
            status TEXT NOT NULL DEFAULT 'planned',
            project_id INTEGER,
            booking_id INTEGER,
            shooting_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(schedule_tasks)").fetchall()}
    if "shooting_id" not in existing_columns:
        cursor.execute("ALTER TABLE schedule_tasks ADD COLUMN shooting_id INTEGER")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS photo_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            idea TEXT NOT NULL,
            description TEXT,
            project_date TEXT,
            city TEXT,
            address TEXT,
            start_time TEXT,
            end_time TEXT,
            project_status TEXT NOT NULL DEFAULT 'Идея',
            accent_class TEXT NOT NULL DEFAULT 'accent-violet',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    project_columns = {row[1] for row in cursor.execute("PRAGMA table_info(photo_projects)").fetchall()}
    if "project_date" not in project_columns:
        cursor.execute("ALTER TABLE photo_projects ADD COLUMN project_date TEXT")
    if "city" not in project_columns:
        cursor.execute("ALTER TABLE photo_projects ADD COLUMN city TEXT")
    if "address" not in project_columns:
        cursor.execute("ALTER TABLE photo_projects ADD COLUMN address TEXT")
    if "start_time" not in project_columns:
        cursor.execute("ALTER TABLE photo_projects ADD COLUMN start_time TEXT")
    if "end_time" not in project_columns:
        cursor.execute("ALTER TABLE photo_projects ADD COLUMN end_time TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS photo_project_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            client_contact TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT,
            duration_minutes INTEGER DEFAULT 15,
            makeup_start_time TEXT,
            price REAL DEFAULT 0,
            prepayment REAL DEFAULT 0,
            comment TEXT,
            status TEXT NOT NULL DEFAULT 'Новая',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    booking_columns = {row[1] for row in cursor.execute("PRAGMA table_info(photo_project_bookings)").fetchall()}
    if "duration_minutes" not in booking_columns:
        cursor.execute("ALTER TABLE photo_project_bookings ADD COLUMN duration_minutes INTEGER DEFAULT 15")
    if "makeup_start_time" not in booking_columns:
        cursor.execute("ALTER TABLE photo_project_bookings ADD COLUMN makeup_start_time TEXT")
    if "price" not in booking_columns:
        cursor.execute("ALTER TABLE photo_project_bookings ADD COLUMN price REAL DEFAULT 0")
    if "prepayment" not in booking_columns:
        cursor.execute("ALTER TABLE photo_project_bookings ADD COLUMN prepayment REAL DEFAULT 0")

    conn.commit()
    conn.close()


def _parse_date(value: Optional[str], default: Optional[date] = None) -> date:
    if not value:
        return default or date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return default or date.today()


def _month_name_ru(month_number: int) -> str:
    months = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]
    return months[month_number - 1]


def _status_label(status: str) -> str:
    mapping = {"planned": "Запланировано", "done": "Выполнено", "cancelled": "Отменено"}
    return mapping.get(status, status)


def _status_badge_class(status: str) -> str:
    mapping = {"planned": "badge-neutral", "done": "badge-success", "cancelled": "badge-danger"}
    return mapping.get(status, "badge-neutral")


def _accent_options() -> List[Dict[str, str]]:
    return [
        {"value": "accent-violet", "label": "Фиолетовый"},
        {"value": "accent-blue", "label": "Синий"},
        {"value": "accent-emerald", "label": "Изумрудный"},
        {"value": "accent-rose", "label": "Розовый"},
        {"value": "accent-gold", "label": "Золотой"},
    ]


def _project_status_class(project_status: str) -> str:
    mapping = {
        "Идея": "badge-neutral",
        "Подготовка": "badge-warning",
        "Набор": "badge-blue",
        "В работе": "badge-violet",
        "Завершён": "badge-success",
        "В архиве": "badge-neutral",
    }
    return mapping.get(project_status, "badge-neutral")


def _project_effective_status(project) -> str:
    project_date = project["project_date"] if "project_date" in project.keys() else None
    if project_date:
        try:
            if datetime.strptime(project_date, "%Y-%m-%d").date() < date.today():
                return "В архиве"
        except ValueError:
            pass
    return project["project_status"]


def _format_full_date_ru(date_value: str) -> str:
    if not date_value:
        return "—"
    try:
        parsed = datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError:
        return date_value
    month_names = {
        1: "января",
        2: "февраля",
        3: "марта",
        4: "апреля",
        5: "мая",
        6: "июня",
        7: "июля",
        8: "августа",
        9: "сентября",
        10: "октября",
        11: "ноября",
        12: "декабря",
    }
    return f"{parsed.day} {month_names[parsed.month]} {parsed.year}"


def _is_valid_phone_number(phone_value: str) -> bool:
    if not phone_value:
        return False
    normalized = re.sub(r"[\s\-\(\)]", "", phone_value)
    return bool(re.fullmatch(r"\+?\d{7,15}", normalized))


def _serialize_project_row(project):
    project_data = dict(project)
    project_data["effective_status"] = _project_effective_status(project)
    project_data["is_archived"] = project_data["effective_status"] == "В архиве"
    project_data["project_date_display"] = _format_full_date_ru(project_data.get("project_date"))
    project_data["city"] = project_data.get("city") or project_data.get("idea") or "—"
    project_data["address"] = project_data.get("address") or project_data.get("description") or "—"
    start_time = project_data.get("start_time") or ""
    end_time = project_data.get("end_time") or ""
    project_data["time_range_display"] = f"{start_time} — {end_time}" if start_time and end_time else "—"
    return project_data


def _serialize_booking_row(booking):
    booking_data = dict(booking)
    booking_data["booking_date_display"] = _format_full_date_ru(booking_data.get("booking_date"))
    duration = int(booking_data.get("duration_minutes") or 15)
    price = float(booking_data.get("price") or 0)
    prepayment = float(booking_data.get("prepayment") or 0)
    booking_data["duration_minutes"] = duration
    booking_data["price"] = int(price) if price.is_integer() else price
    booking_data["prepayment"] = int(prepayment) if prepayment.is_integer() else prepayment
    remaining = max(price - prepayment, 0)
    booking_data["remaining_payment"] = int(remaining) if remaining.is_integer() else remaining
    return booking_data


def _time_to_minutes(value: str) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError:
        return None
    return parsed.hour * 60 + parsed.minute


def _minutes_to_time(total_minutes: int) -> str:
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _build_available_slots(project, bookings):
    start_minutes = _time_to_minutes(project.get("start_time"))
    end_minutes = _time_to_minutes(project.get("end_time"))
    if start_minutes is None or end_minutes is None or end_minutes <= start_minutes:
        return {"15": [], "30": []}

    intervals = []
    for booking in bookings:
        booking_start = _time_to_minutes(booking.get("booking_time"))
        duration = int(booking.get("duration_minutes") or 15)
        if booking_start is None:
            continue
        intervals.append((booking_start, booking_start + duration))

    def has_overlap(start, end):
        for interval_start, interval_end in intervals:
            if start < interval_end and end > interval_start:
                return True
        return False

    slots_15 = []
    slots_30 = []
    current = start_minutes
    while current < end_minutes:
        end_15 = current + 15
        end_30 = current + 30
        time_label = _minutes_to_time(current)
        if end_15 <= end_minutes and not has_overlap(current, end_15):
            slots_15.append(time_label)
        if end_30 <= end_minutes and not has_overlap(current, end_30):
            slots_30.append(time_label)
        current += 15

    return {"15": slots_15, "30": slots_30}


def create_task(
    title: str,
    task_date: str,
    description: str = "",
    start_time: str = "",
    end_time: str = "",
    task_type: str = "Личное",
    status: str = "planned",
    project_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    shooting_id: Optional[int] = None,
):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO schedule_tasks (
            title, description, task_date, start_time, end_time,
            task_type, status, project_id, booking_id, shooting_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title.strip(),
            description.strip(),
            task_date,
            start_time or None,
            end_time or None,
            task_type,
            status,
            project_id,
            booking_id,
            shooting_id,
        ),
    )
    conn.commit()
    conn.close()


def update_task(
    task_id: int,
    title: str,
    task_date: str,
    description: str = "",
    start_time: str = "",
    end_time: str = "",
    task_type: str = "Личное",
    status: str = "planned",
    project_id: Optional[int] = None,
):
    conn = get_connection()
    conn.execute(
        """
        UPDATE schedule_tasks
        SET title = ?, description = ?, task_date = ?, start_time = ?,
            end_time = ?, task_type = ?, status = ?, project_id = ?
        WHERE id = ?
        """,
        (
            title.strip(),
            description.strip(),
            task_date,
            start_time or None,
            end_time or None,
            task_type,
            status,
            project_id,
            task_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_task(task_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM schedule_tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def get_task(task_id: int):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT t.*, p.title AS project_title
        FROM schedule_tasks t
        LEFT JOIN photo_projects p ON p.id = t.project_id
        WHERE t.id = ?
        """,
        (task_id,),
    ).fetchone()
    conn.close()
    return row


def get_tasks_for_range(date_from: str, date_to: str):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT t.*, p.title AS project_title
        FROM schedule_tasks t
        LEFT JOIN photo_projects p ON p.id = t.project_id
        WHERE t.task_date BETWEEN ? AND ?
        ORDER BY t.task_date ASC, COALESCE(t.start_time, '99:99') ASC, t.id DESC
        """,
        (date_from, date_to),
    ).fetchall()
    conn.close()
    return rows


def get_tasks_for_day(day_value: str):
    return get_tasks_for_range(day_value, day_value)


def upsert_task_for_shooting(
    shooting_id: int,
    project_name: str,
    client_name: str,
    shooting_date: str,
    shooting_time: str = "",
    duration_hours=None,
    phone: str = "",
    price=None,
    prepayment=None,
    notes: str = "",
):
    title = f"Съёмка: {project_name}"

    description_parts = [f"Клиент: {client_name}"]
    if phone:
        description_parts.append(f"Телефон: {phone}")
    if duration_hours not in (None, ""):
        description_parts.append(f"Длительность: {duration_hours} ч")
    if price not in (None, ""):
        description_parts.append(f"Стоимость: {price}")
    if prepayment not in (None, ""):
        description_parts.append(f"Предоплата: {prepayment}")
    if notes:
        description_parts.append(f"Комментарий: {notes}")

    description = "\n".join(description_parts)

    conn = get_connection()
    existing_task = conn.execute("SELECT id FROM schedule_tasks WHERE shooting_id = ?", (shooting_id,)).fetchone()

    if existing_task:
        conn.execute(
            """
            UPDATE schedule_tasks
            SET title = ?, description = ?, task_date = ?, start_time = ?,
                task_type = ?, project_id = NULL, booking_id = NULL
            WHERE shooting_id = ?
            """,
            (title, description, shooting_date, shooting_time or None, "Съёмка", shooting_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO schedule_tasks (
                title, description, task_date, start_time, task_type, status, shooting_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, description, shooting_date, shooting_time or None, "Съёмка", "planned", shooting_id),
        )

    conn.commit()
    conn.close()


def delete_task_for_shooting(shooting_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM schedule_tasks WHERE shooting_id = ?", (shooting_id,))
    conn.commit()
    conn.close()


def toggle_task_status(task_id: int):
    task = get_task(task_id)
    if not task:
        return
    new_status = "done" if task["status"] != "done" else "planned"
    conn = get_connection()
    conn.execute("UPDATE schedule_tasks SET status = ? WHERE id = ?", (new_status, task_id))
    conn.commit()
    conn.close()


def create_project(title: str, city: str, address: str, project_date: str, start_time: str, end_time: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO photo_projects (title, idea, description, project_date, city, address, start_time, end_time, project_status, accent_class)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Идея', 'accent-violet')
        """,
        (title.strip(), city.strip(), address.strip(), project_date or None, city.strip(), address.strip(), start_time or None, end_time or None),
    )
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()
    return project_id


def update_project(project_id: int, title: str, city: str, address: str, project_date: str, start_time: str, end_time: str):
    conn = get_connection()
    conn.execute(
        """
        UPDATE photo_projects
        SET title = ?, idea = ?, description = ?, project_date = ?, city = ?, address = ?, start_time = ?, end_time = ?
        WHERE id = ?
        """,
        (title.strip(), city.strip(), address.strip(), project_date or None, city.strip(), address.strip(), start_time or None, end_time or None, project_id),
    )
    conn.commit()
    conn.close()


def delete_project(project_id: int):
    conn = get_connection()
    booking_rows = conn.execute("SELECT id FROM photo_project_bookings WHERE project_id = ?", (project_id,)).fetchall()
    booking_ids = [row["id"] for row in booking_rows]

    if booking_ids:
        placeholders = ",".join(["?"] * len(booking_ids))
        conn.execute(f"DELETE FROM schedule_tasks WHERE booking_id IN ({placeholders})", booking_ids)

    conn.execute("DELETE FROM schedule_tasks WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM photo_project_bookings WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM photo_projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()


def get_all_projects():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT p.*, COUNT(b.id) AS bookings_count
        FROM photo_projects p
        LEFT JOIN photo_project_bookings b ON b.project_id = p.id
        GROUP BY p.id
        ORDER BY COALESCE(p.project_date, p.created_at) DESC, p.id DESC
        """
    ).fetchall()
    conn.close()
    return rows


def get_project(project_id: int):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT p.*, COUNT(b.id) AS bookings_count
        FROM photo_projects p
        LEFT JOIN photo_project_bookings b ON b.project_id = p.id
        WHERE p.id = ?
        GROUP BY p.id
        """,
        (project_id,),
    ).fetchone()
    conn.close()
    return row


def create_booking(
    project_id: int,
    client_name: str,
    client_contact: str,
    booking_date: str,
    booking_time: str,
    duration_minutes: int,
    makeup_start_time: str,
    price: float,
    prepayment: float,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO photo_project_bookings (
            project_id, client_name, client_contact, booking_date, booking_time, duration_minutes, makeup_start_time, price, prepayment, comment, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'Новая')
        """,
        (project_id, client_name.strip(), client_contact.strip(), booking_date, booking_time or None, duration_minutes, makeup_start_time or None, price, prepayment),
    )
    conn.commit()
    booking_id = cursor.lastrowid
    conn.close()
    return booking_id


def update_booking(
    booking_id: int,
    client_name: str,
    client_contact: str,
    booking_date: str,
    booking_time: str,
    duration_minutes: int,
    makeup_start_time: str,
    price: float,
    prepayment: float,
):
    conn = get_connection()
    conn.execute(
        """
        UPDATE photo_project_bookings
        SET client_name = ?, client_contact = ?, booking_date = ?, booking_time = ?, duration_minutes = ?, makeup_start_time = ?, price = ?, prepayment = ?
        WHERE id = ?
        """,
        (client_name.strip(), client_contact.strip(), booking_date, booking_time or None, duration_minutes, makeup_start_time or None, price, prepayment, booking_id),
    )
    conn.commit()
    conn.close()


def delete_booking(booking_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM schedule_tasks WHERE booking_id = ?", (booking_id,))
    conn.execute("DELETE FROM photo_project_bookings WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()


def get_booking(booking_id: int):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT b.*, p.title AS project_title
        FROM photo_project_bookings b
        JOIN photo_projects p ON p.id = b.project_id
        WHERE b.id = ?
        """,
        (booking_id,),
    ).fetchone()
    conn.close()
    return row


def get_bookings_for_project(project_id: int):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM photo_project_bookings
        WHERE project_id = ?
        ORDER BY booking_date ASC, COALESCE(booking_time, '99:99') ASC, id DESC
        """,
        (project_id,),
    ).fetchall()
    conn.close()
    return rows


def upsert_task_for_booking(booking_id: int):
    booking = get_booking(booking_id)
    if not booking:
        return

    title = booking["project_title"]
    description = ""

    conn = get_connection()
    existing_task = conn.execute("SELECT id FROM schedule_tasks WHERE booking_id = ?", (booking_id,)).fetchone()

    if existing_task:
        conn.execute(
            """
            UPDATE schedule_tasks
            SET title = ?, description = ?, task_date = ?, start_time = ?, task_type = ?, project_id = ?
            WHERE booking_id = ?
            """,
            (title, description, booking["booking_date"], booking["booking_time"], "Фотопроект", booking["project_id"], booking_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO schedule_tasks (
                title, description, task_date, start_time, task_type, status, project_id, booking_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, description, booking["booking_date"], booking["booking_time"], "Фотопроект", "planned", booking["project_id"], booking_id),
        )

    conn.commit()
    conn.close()


def _previous_date(selected_date: date, current_view: str) -> date:
    if current_view == "day":
        return selected_date - timedelta(days=1)
    first_day_current = selected_date.replace(day=1)
    prev_month_last = first_day_current - timedelta(days=1)
    return prev_month_last.replace(day=min(selected_date.day, monthrange(prev_month_last.year, prev_month_last.month)[1]))


def _next_date(selected_date: date, current_view: str) -> date:
    if current_view == "day":
        return selected_date + timedelta(days=1)
    current_last_day = monthrange(selected_date.year, selected_date.month)[1]
    first_next_month = selected_date.replace(day=current_last_day) + timedelta(days=1)
    return first_next_month.replace(day=min(selected_date.day, monthrange(first_next_month.year, first_next_month.month)[1]))


def build_schedule_context(selected_date: date, current_view: str):
    if current_view not in {"day", "month"}:
        current_view = "month"

    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_end = week_start + timedelta(days=6)

    month_start = selected_date.replace(day=1)
    month_last_day = monthrange(selected_date.year, selected_date.month)[1]
    month_end = selected_date.replace(day=month_last_day)

    calendar_start = month_start - timedelta(days=month_start.weekday())
    calendar_end = month_end + timedelta(days=(6 - month_end.weekday()))

    tasks_in_grid = get_tasks_for_range(calendar_start.isoformat(), calendar_end.isoformat())
    tasks_by_date = defaultdict(list)
    for task in tasks_in_grid:
        tasks_by_date[task["task_date"]].append(task)

    month_cells = []
    current_day = calendar_start
    while current_day <= calendar_end:
        day_key = current_day.isoformat()
        month_cells.append(
            {
                "date": current_day,
                "date_key": day_key,
                "is_current_month": current_day.month == selected_date.month,
                "is_today": current_day == date.today(),
                "is_selected": current_day == selected_date,
                "tasks": tasks_by_date.get(day_key, []),
            }
        )
        current_day += timedelta(days=1)

    day_tasks = get_tasks_for_day(selected_date.isoformat())
    total_tasks_month = sum(len(tasks) for tasks in tasks_by_date.values())
    done_tasks_month = sum(1 for tasks in tasks_by_date.values() for task in tasks if task["status"] == "done")
    cancelled_tasks_month = sum(1 for tasks in tasks_by_date.values() for task in tasks if task["status"] == "cancelled")

    return {
        "selected_date": selected_date,
        "selected_date_label": _format_full_date_ru(selected_date.isoformat()),
        "current_view": current_view,
        "month_title": f"{_month_name_ru(selected_date.month)} {selected_date.year}",
        "week_label": f"{week_start.strftime('%d.%m')} — {week_end.strftime('%d.%m')}",
        "month_cells": month_cells,
        "day_tasks": day_tasks,
        "month_stats": {
            "total": total_tasks_month,
            "done": done_tasks_month,
            "planned": total_tasks_month - done_tasks_month - cancelled_tasks_month,
            "cancelled": cancelled_tasks_month,
        },
        "task_types": TASK_TYPES,
        "task_statuses": TASK_STATUSES,
        "status_label": _status_label,
        "status_badge_class": _status_badge_class,
        "projects": [_serialize_project_row(project) for project in get_all_projects() if not _serialize_project_row(project)["is_archived"]],
        "prev_date": _previous_date(selected_date, current_view).isoformat(),
        "next_date": _next_date(selected_date, current_view).isoformat(),
    }


@planner_bp.route("/planner.schedule")
@login_required
def schedule():
    current_view = request.args.get("view", "month")
    selected_date = _parse_date(request.args.get("date"), default=date.today())
    context = build_schedule_context(selected_date, current_view)
    return render_template("schedule.html", **context)


@planner_bp.route("/planner.schedule/task/create", methods=["POST"])
@login_required
def create_schedule_task():
    title = request.form.get("title", "").strip()
    task_date = request.form.get("task_date", "").strip()
    description = request.form.get("description", "")
    start_time = request.form.get("start_time", "")
    end_time = request.form.get("end_time", "")
    task_type = request.form.get("task_type", "Личное")
    status = request.form.get("status", "planned")
    project_id_raw = request.form.get("project_id", "").strip()
    project_id = int(project_id_raw) if project_id_raw.isdigit() else None

    if not title or not task_date:
        flash("Для задачи нужны название и дата.", "error")
        return redirect(url_for("planner.schedule", date=task_date or date.today().isoformat()))

    create_task(title, task_date, description, start_time, end_time, task_type, status, project_id)
    flash("Задача добавлена в график.", "success")
    return redirect(url_for("planner.schedule", date=task_date, view=request.form.get("return_view", "month")))


@planner_bp.route("/planner.schedule/task/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_schedule_task(task_id: int):
    task = get_task(task_id)
    if not task:
        flash("Задача не найдена.", "error")
        return redirect(url_for("planner.schedule"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        task_date = request.form.get("task_date", "").strip()
        description = request.form.get("description", "")
        start_time = request.form.get("start_time", "")
        end_time = request.form.get("end_time", "")
        task_type = request.form.get("task_type", "Личное")
        status = request.form.get("status", "planned")
        project_id_raw = request.form.get("project_id", "").strip()
        project_id = int(project_id_raw) if project_id_raw.isdigit() else None

        if not title or not task_date:
            flash("Для задачи нужны название и дата.", "error")
            return redirect(url_for("planner.edit_schedule_task", task_id=task_id))

        update_task(task_id, title, task_date, description, start_time, end_time, task_type, status, project_id)
        flash("Задача обновлена.", "success")
        return redirect(url_for("planner.schedule", date=task_date, view="day"))

    return render_template(
        "schedule_task_form.html",
        task=task,
        task_types=TASK_TYPES,
        task_statuses=TASK_STATUSES,
        projects=[_serialize_project_row(project) for project in get_all_projects() if not _serialize_project_row(project)["is_archived"]],
    )


@planner_bp.route("/planner.schedule/task/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_schedule_task(task_id: int):
    task = get_task(task_id)
    if task:
        delete_task(task_id)
        flash("Задача удалена.", "success")
        return redirect(url_for("planner.schedule", date=task["task_date"], view="day"))
    flash("Задача не найдена.", "error")
    return redirect(url_for("planner.schedule"))


@planner_bp.route("/planner.schedule/task/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle_schedule_task(task_id: int):
    task = get_task(task_id)
    if not task:
        flash("Задача не найдена.", "error")
        return redirect(url_for("planner.schedule"))
    toggle_task_status(task_id)
    flash("Статус задачи обновлён.", "success")
    return redirect(url_for("planner.schedule", date=task["task_date"], view="day"))


@planner_bp.route("/photo-projects")
@login_required
def photo_projects():
    serialized_projects = [_serialize_project_row(project) for project in get_all_projects()]
    active_projects = [project for project in serialized_projects if not project["is_archived"]]
    archived_projects = [project for project in serialized_projects if project["is_archived"]]
    return render_template(
        "photo_projects.html",
        projects=active_projects,
        archived_projects=archived_projects,
        project_status_class=_project_status_class,
    )


@planner_bp.route("/photo-projects/create", methods=["GET", "POST"])
@login_required
def create_photo_project():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()
        project_date = request.form.get("project_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()

        if not title or not city or not address or not project_date or not start_time or not end_time:
            flash("Заполни название, город, адрес, дату и время фотопроекта.", "error")
            return redirect(url_for("planner.create_photo_project"))
        if city not in PROJECT_CITIES:
            flash("Выбери город из списка.", "error")
            return redirect(url_for("planner.create_photo_project"))
        if (_time_to_minutes(start_time) is None or _time_to_minutes(end_time) is None or _time_to_minutes(start_time) >= _time_to_minutes(end_time)):
            flash("Проверь время проекта: 'от' должно быть раньше 'до'.", "error")
            return redirect(url_for("planner.create_photo_project"))

        project_id = create_project(title, city, address, project_date, start_time, end_time)
        flash("Фотопроект создан.", "success")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id))

    return render_template("photo_project_form.html", project=None, cities=PROJECT_CITIES)


@planner_bp.route("/photo-projects/<int:project_id>")
@login_required
def photo_project_detail(project_id: int):
    project = get_project(project_id)
    if not project:
        flash("Фотопроект не найден.", "error")
        return redirect(url_for("planner.photo_projects"))
    bookings = [_serialize_booking_row(booking) for booking in get_bookings_for_project(project_id)]
    view_mode = request.args.get("view", "bookings")
    return render_template(
        "photo_project_detail.html",
        project=_serialize_project_row(project),
        bookings=bookings,
        view_mode=view_mode,
    )


@planner_bp.route("/photo-projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_photo_project(project_id: int):
    project = get_project(project_id)
    if not project:
        flash("Фотопроект не найден.", "error")
        return redirect(url_for("planner.photo_projects"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()
        project_date = request.form.get("project_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()

        if not title or not city or not address or not project_date or not start_time or not end_time:
            flash("Заполни название, город, адрес, дату и время фотопроекта.", "error")
            return redirect(url_for("planner.edit_photo_project", project_id=project_id))
        if city not in PROJECT_CITIES:
            flash("Выбери город из списка.", "error")
            return redirect(url_for("planner.edit_photo_project", project_id=project_id))
        if (_time_to_minutes(start_time) is None or _time_to_minutes(end_time) is None or _time_to_minutes(start_time) >= _time_to_minutes(end_time)):
            flash("Проверь время проекта: 'от' должно быть раньше 'до'.", "error")
            return redirect(url_for("planner.edit_photo_project", project_id=project_id))

        update_project(project_id, title, city, address, project_date, start_time, end_time)
        flash("Фотопроект обновлён.", "success")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id))

    return render_template(
        "photo_project_form.html",
        project=_serialize_project_row(project),
        cities=PROJECT_CITIES,
    )


@planner_bp.route("/photo-projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_photo_project(project_id: int):
    project = get_project(project_id)
    if not project:
        flash("Фотопроект не найден.", "error")
        return redirect(url_for("planner.photo_projects"))
    delete_project(project_id)
    flash("Фотопроект удалён вместе со связанными записями и задачами.", "success")
    return redirect(url_for("planner.photo_projects"))


@planner_bp.route("/photo-projects/<int:project_id>/bookings/create", methods=["POST"])
@login_required
def create_photo_project_booking(project_id: int):
    project = get_project(project_id)
    if not project:
        flash("Фотопроект не найден.", "error")
        return redirect(url_for("planner.photo_projects"))

    client_name = request.form.get("client_name", "").strip()
    client_contact = request.form.get("client_contact", "").strip()
    booking_time = request.form.get("booking_time", "").strip()
    duration_minutes_raw = request.form.get("duration_minutes", "15").strip()
    makeup_start_time = request.form.get("makeup_start_time", "").strip()
    price_raw = request.form.get("price", "0").strip()
    prepayment_raw = request.form.get("prepayment", "0").strip()
    booking_date = project["project_date"] or ""

    if not client_name or not client_contact or not booking_time or not booking_date:
        flash("Для записи нужны имя, контакт и время.", "error")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id, view="add"))
    if not _is_valid_phone_number(client_contact):
        flash("Контакт должен содержать только номер телефона.", "error")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id, view="add"))
    if duration_minutes_raw not in {"15", "30"}:
        flash("Выбери длительность 15 или 30 минут.", "error")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id, view="add"))
    duration_minutes = int(duration_minutes_raw)
    available_slots = _build_available_slots(dict(project), [_serialize_booking_row(item) for item in get_bookings_for_project(project_id)])
    if booking_time not in available_slots[duration_minutes_raw]:
        flash("Это время уже занято или вне диапазона фотопроекта.", "error")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id, view="add"))
    if duration_minutes == 30 and not makeup_start_time:
        flash("Для записи на 30 минут укажи время начала макияжа.", "error")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id, view="add"))
    try:
        price = float(price_raw or 0)
        prepayment = float(prepayment_raw or 0)
    except ValueError:
        flash("Стоимость и предоплата должны быть числами.", "error")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id, view="add"))

    booking_id = create_booking(
        project_id,
        client_name,
        client_contact,
        booking_date,
        booking_time,
        duration_minutes,
        makeup_start_time if duration_minutes == 30 else "",
        price,
        prepayment,
    )
    upsert_task_for_booking(booking_id)
    flash("Запись добавлена и автоматически попала в график.", "success")
    return redirect(url_for("planner.photo_project_detail", project_id=project_id))


@planner_bp.route("/photo-projects/bookings/<int:booking_id>/edit", methods=["GET", "POST"])
@login_required
def edit_photo_project_booking(booking_id: int):
    booking = get_booking(booking_id)
    if not booking:
        flash("Запись не найдена.", "error")
        return redirect(url_for("planner.photo_projects"))

    if request.method == "POST":
        client_name = request.form.get("client_name", "").strip()
        client_contact = request.form.get("client_contact", "").strip()
        booking_date = booking["booking_date"]
        booking_time = request.form.get("booking_time", "").strip()
        duration_minutes_raw = request.form.get("duration_minutes", "15").strip()
        makeup_start_time = request.form.get("makeup_start_time", "").strip()
        price_raw = request.form.get("price", "0").strip()
        prepayment_raw = request.form.get("prepayment", "0").strip()

        if not client_name or not client_contact or not booking_date or not booking_time:
            flash("Для записи нужны имя, контакт и время.", "error")
            return redirect(url_for("planner.edit_photo_project_booking", booking_id=booking_id))
        if not _is_valid_phone_number(client_contact):
            flash("Контакт должен содержать только номер телефона.", "error")
            return redirect(url_for("planner.edit_photo_project_booking", booking_id=booking_id))
        if duration_minutes_raw not in {"15", "30"}:
            flash("Выбери длительность 15 или 30 минут.", "error")
            return redirect(url_for("planner.edit_photo_project_booking", booking_id=booking_id))
        duration_minutes = int(duration_minutes_raw)
        project = get_project(booking["project_id"])
        sibling_bookings = [_serialize_booking_row(item) for item in get_bookings_for_project(booking["project_id"]) if item["id"] != booking_id]
        available_slots = _build_available_slots(dict(project), sibling_bookings)
        if booking_time not in available_slots[duration_minutes_raw]:
            flash("Это время уже занято или вне диапазона фотопроекта.", "error")
            return redirect(url_for("planner.edit_photo_project_booking", booking_id=booking_id))
        if duration_minutes == 30 and not makeup_start_time:
            flash("Для записи на 30 минут укажи время начала макияжа.", "error")
            return redirect(url_for("planner.edit_photo_project_booking", booking_id=booking_id))
        try:
            price = float(price_raw or 0)
            prepayment = float(prepayment_raw or 0)
        except ValueError:
            flash("Стоимость и предоплата должны быть числами.", "error")
            return redirect(url_for("planner.edit_photo_project_booking", booking_id=booking_id))

        update_booking(
            booking_id,
            client_name,
            client_contact,
            booking_date,
            booking_time,
            duration_minutes,
            makeup_start_time if duration_minutes == 30 else "",
            price,
            prepayment,
        )
        upsert_task_for_booking(booking_id)
        flash("Запись обновлена.", "success")
        return redirect(url_for("planner.photo_project_detail", project_id=booking["project_id"]))

    return render_template("booking_form.html", booking=_serialize_booking_row(booking))


@planner_bp.route("/photo-projects/bookings/<int:booking_id>/delete", methods=["POST"])
@login_required
def delete_photo_project_booking(booking_id: int):
    booking = get_booking(booking_id)
    if not booking:
        flash("Запись не найдена.", "error")
        return redirect(url_for("planner.photo_projects"))
    project_id = booking["project_id"]
    delete_booking(booking_id)
    flash("Запись удалена.", "success")
    return redirect(url_for("planner.photo_project_detail", project_id=project_id))
