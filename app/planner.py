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
PROJECT_STATUSES = ["Идея", "Подготовка", "Набор", "В работе", "Завершён", "В архиве"]
BOOKING_STATUSES = ["Новая", "Подтверждена", "Перенос", "Завершена", "Отмена"]


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
            project_status TEXT NOT NULL DEFAULT 'Идея',
            accent_class TEXT NOT NULL DEFAULT 'accent-violet',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    project_columns = {row[1] for row in cursor.execute("PRAGMA table_info(photo_projects)").fetchall()}
    if "project_date" not in project_columns:
        cursor.execute("ALTER TABLE photo_projects ADD COLUMN project_date TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS photo_project_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            client_contact TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT,
            comment TEXT,
            status TEXT NOT NULL DEFAULT 'Новая',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

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
    return project_data


def _serialize_booking_row(booking):
    booking_data = dict(booking)
    booking_data["booking_date_display"] = _format_full_date_ru(booking_data.get("booking_date"))
    return booking_data


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


def create_project(title: str, idea: str, description: str, project_date: str, project_status: str, accent_class: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO photo_projects (title, idea, description, project_date, project_status, accent_class)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (title.strip(), idea.strip(), description.strip(), project_date or None, project_status, accent_class),
    )
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()
    return project_id


def update_project(project_id: int, title: str, idea: str, description: str, project_date: str, project_status: str, accent_class: str):
    conn = get_connection()
    conn.execute(
        """
        UPDATE photo_projects
        SET title = ?, idea = ?, description = ?, project_date = ?, project_status = ?, accent_class = ?
        WHERE id = ?
        """,
        (title.strip(), idea.strip(), description.strip(), project_date or None, project_status, accent_class, project_id),
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


def create_booking(project_id: int, client_name: str, client_contact: str, booking_date: str, booking_time: str, comment: str, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO photo_project_bookings (
            project_id, client_name, client_contact, booking_date, booking_time, comment, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, client_name.strip(), client_contact.strip(), booking_date, booking_time or None, comment.strip(), status),
    )
    conn.commit()
    booking_id = cursor.lastrowid
    conn.close()
    return booking_id


def update_booking(booking_id: int, client_name: str, client_contact: str, booking_date: str, booking_time: str, comment: str, status: str):
    conn = get_connection()
    conn.execute(
        """
        UPDATE photo_project_bookings
        SET client_name = ?, client_contact = ?, booking_date = ?, booking_time = ?, comment = ?, status = ?
        WHERE id = ?
        """,
        (client_name.strip(), client_contact.strip(), booking_date, booking_time or None, comment.strip(), status, booking_id),
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
        idea = request.form.get("idea", "").strip()
        description = request.form.get("description", "")
        project_date = request.form.get("project_date", "").strip()
        project_status = request.form.get("project_status", "Идея")
        accent_class = request.form.get("accent_class", "accent-violet")

        if not title or not idea:
            flash("Для фотопроекта нужны название и идея.", "error")
            return redirect(url_for("planner.create_photo_project"))

        project_id = create_project(title, idea, description, project_date, project_status, accent_class)
        flash("Фотопроект создан.", "success")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id))

    return render_template("photo_project_form.html", project=None, project_statuses=PROJECT_STATUSES, accent_options=_accent_options())


@planner_bp.route("/photo-projects/<int:project_id>")
@login_required
def photo_project_detail(project_id: int):
    project = get_project(project_id)
    if not project:
        flash("Фотопроект не найден.", "error")
        return redirect(url_for("planner.photo_projects"))
    bookings = [_serialize_booking_row(booking) for booking in get_bookings_for_project(project_id)]
    return render_template(
        "photo_project_detail.html",
        project=_serialize_project_row(project),
        bookings=bookings,
        booking_statuses=BOOKING_STATUSES,
        project_status_class=_project_status_class,
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
        idea = request.form.get("idea", "").strip()
        description = request.form.get("description", "")
        project_date = request.form.get("project_date", "").strip()
        project_status = request.form.get("project_status", "Идея")
        accent_class = request.form.get("accent_class", "accent-violet")

        if not title or not idea:
            flash("Для фотопроекта нужны название и идея.", "error")
            return redirect(url_for("planner.edit_photo_project", project_id=project_id))

        update_project(project_id, title, idea, description, project_date, project_status, accent_class)
        flash("Фотопроект обновлён.", "success")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id))

    return render_template(
        "photo_project_form.html",
        project=_serialize_project_row(project),
        project_statuses=PROJECT_STATUSES,
        accent_options=_accent_options(),
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
    booking_date = request.form.get("booking_date", "").strip()
    booking_time = request.form.get("booking_time", "")
    comment = request.form.get("comment", "")
    status = request.form.get("status", "Новая")

    if not client_name or not client_contact or not booking_date:
        flash("Для записи нужны клиент, контакт и дата.", "error")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id))
    if not _is_valid_phone_number(client_contact):
        flash("Контакт должен содержать только номер телефона.", "error")
        return redirect(url_for("planner.photo_project_detail", project_id=project_id))

    booking_id = create_booking(project_id, client_name, client_contact, booking_date, booking_time, comment, status)
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
        booking_date = request.form.get("booking_date", "").strip()
        booking_time = request.form.get("booking_time", "")
        comment = request.form.get("comment", "")
        status = request.form.get("status", "Новая")

        if not client_name or not client_contact or not booking_date:
            flash("Для записи нужны клиент, контакт и дата.", "error")
            return redirect(url_for("planner.edit_photo_project_booking", booking_id=booking_id))
        if not _is_valid_phone_number(client_contact):
            flash("Контакт должен содержать только номер телефона.", "error")
            return redirect(url_for("planner.edit_photo_project_booking", booking_id=booking_id))

        update_booking(booking_id, client_name, client_contact, booking_date, booking_time, comment, status)
        upsert_task_for_booking(booking_id)
        flash("Запись обновлена.", "success")
        return redirect(url_for("planner.photo_project_detail", project_id=booking["project_id"]))

    return render_template("booking_form.html", booking=booking, booking_statuses=BOOKING_STATUSES)


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
