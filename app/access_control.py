from __future__ import annotations

from dataclasses import dataclass
import os
import re
from pathlib import Path

from flask import abort, current_app, redirect, request, url_for
from flask_login import current_user
from werkzeug.security import generate_password_hash

from config import Config
from app.auth import generate_totp_secret
from app.database import get_master_connection, init_db, use_database


SECTION_LABELS = {
    "budget": "Бюджет",
    "car": "Машина",
    "schedule": "График",
    "shootings": "Съёмки",
    "photo_projects": "Фотопроекты",
    "scenarios": "Сценарии",
    "study": "Учёба",
    "workouts": "Тренировки",
    "nutrition": "Питание",
}

SECTION_ENDPOINTS = {
    "budget": {
        "budget",
        "budget_manage",
        "budget_edit",
        "budget_delete",
        "budget_delete_selected",
        "budget_delete_all",
        "budget_export",
        "budget_report",
        "budget_balance",
    },
    "car": {
        "car",
        "car_manage",
        "car_done_edit",
        "car_planned_edit",
        "car_planned_complete",
        "car_done_delete",
        "car_planned_delete",
        "car_done_delete_selected",
        "car_planned_delete_selected",
        "car_done_delete_all",
        "car_planned_delete_all",
        "car_notifications",
        "car_notification_to_work",
        "car_notification_hide",
        "car_notification_archive_delete",
        "car_notifications_delete_selected",
        "car_notifications_delete_all",
    },
    "schedule": {
        "planner.schedule",
        "planner.create_schedule_task",
        "planner.edit_schedule_task",
        "planner.delete_schedule_task",
        "planner.delete_schedule_tasks_selected",
        "planner.delete_schedule_tasks_all",
        "planner.complete_schedule_task",
        "planner.move_schedule_task",
        "planner.export_schedule",
    },
    "shootings": {
        "shootings_hub",
        "shootings",
        "shootings_upcoming",
        "shootings_archive",
        "shootings_add",
        "shootings_export",
        "shooting_detail",
        "shooting_edit",
        "shooting_delete",
        "shootings_upcoming_delete_selected",
        "shootings_upcoming_delete_all",
        "shootings_archive_delete_selected",
        "shootings_archive_delete_all",
    },
    "photo_projects": {
        "planner.photo_projects",
        "planner.photo_project_detail",
        "planner.create_photo_project",
        "planner.edit_photo_project",
        "planner.delete_photo_project",
        "planner.delete_photo_projects_selected",
        "planner.delete_photo_projects_all",
        "planner.create_photo_project_booking",
        "planner.edit_photo_project_booking",
        "planner.photo_project_booking_detail",
        "planner.delete_photo_project_booking",
        "planner.delete_photo_project_bookings_selected",
        "planner.delete_photo_project_bookings_all",
    },
    "scenarios": {
        "scenarios",
        "scenarios_upcoming",
        "scenarios_archive",
        "scenarios_add",
        "scenarios_export",
        "scenario_detail",
        "scenario_edit",
        "scenario_delete",
        "scenario_toggle_status",
        "scenarios_upcoming_delete_selected",
        "scenarios_upcoming_delete_all",
        "scenarios_archive_delete_selected",
        "scenarios_archive_delete_all",
    },
    "study": {
        "learning.study_hub",
        "learning.it_course",
        "learning.it_day",
        "learning.it_final",
        "learning.it_video_course",
        "learning.it_video_lesson",
        "learning.english_course",
        "learning.english_day",
        "learning.english_final",
        "learning.course_review",
    },
    "workouts": {
        "workouts.index",
        "workouts.plan_detail",
        "workouts.update_plan",
        "workouts.create_result",
        "workouts.remove_result",
        "workouts.save_weight",
        "workouts.save_weight_plan",
        "workouts.remove_weight",
    },
    "nutrition": {
        "nutrition.index",
        "nutrition.edit_profile",
        "nutrition.save_profile",
        "nutrition.create_entry",
        "nutrition.remove_entry",
        "nutrition.new_custom_food",
        "nutrition.create_custom_food",
        "nutrition.remove_custom_food",
    },
}

HOME_ENDPOINTS = {"index", "account_settings", "logout"}
GROUPED_ENDPOINT_ACCESS = {
    "reports_hub": {"budget", "car"},
    "shootings_hub": {"shootings", "photo_projects", "scenarios"},
    "sport_hub": {"workouts", "nutrition"},
}
SYSTEM_ENDPOINTS = {
    "login",
    "setup_2fa",
    "static",
    "health",
    "web_push_service_worker",
    "web_push_config",
    "web_push_subscribe",
    "web_push_unsubscribe",
    "web_push_inbox",
    "web_push_inbox_read",
    "web_push_test",
    "telegram_external_push",
    "user_avatar_file",
    "update_account_avatar",
    "remove_account_avatar",
    "update_account_password",
    "start_account_2fa_setup",
    "disable_account_2fa",
    "logout_all_devices",
    "logout_device_session",
}


@dataclass(frozen=True)
class ManagedUserForm:
    username: str
    display_name: str
    password: str
    permissions: set[str]


def normalize_username(value: str) -> str:
    return (value or "").strip().lower()


def is_system_admin_user(user=None) -> bool:
    candidate = user or current_user
    return bool(getattr(candidate, "is_system_admin", False)) or is_main_admin_user(candidate)


def _users_table_columns(conn) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}


def _configured_main_admin_username() -> str:
    return normalize_username(
        os.getenv("MAIN_ADMIN_USERNAME")
        or os.getenv("ADMIN_USERNAME")
        or "admin"
    )


def _root_account_filter(columns: set[str]) -> str:
    filters = ["COALESCE(is_active, 1) = 1"]
    if "data_database_name" in columns:
        filters.append("COALESCE(TRIM(data_database_name), '') = ''")
    if "created_by_user_id" in columns:
        filters.append("created_by_user_id IS NULL")
    return " AND ".join(filters)


def get_main_admin_user_id() -> int | None:
    conn = get_master_connection()
    try:
        columns = _users_table_columns(conn)
        configured_username = _configured_main_admin_username()
        if configured_username:
            row = conn.execute(
                """
                SELECT id
                FROM users
                WHERE LOWER(username) = ?
                  AND COALESCE(is_active, 1) = 1
                LIMIT 1
                """,
                (configured_username,),
            ).fetchone()
            if row:
                return int(row["id"])

        root_filter = _root_account_filter(columns)
        row = conn.execute(
            f"""
            SELECT id
            FROM users
            WHERE COALESCE(is_system_admin, 0) = 1
              AND {root_filter}
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if row:
            return int(row["id"])

        row = conn.execute(
            f"""
            SELECT id
            FROM users
            WHERE {root_filter}
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        return int(row["id"]) if row else None
    finally:
        conn.close()


def is_main_admin_user(user=None) -> bool:
    candidate = user or current_user
    if not getattr(candidate, "is_authenticated", False):
        return False
    try:
        candidate_id = int(getattr(candidate, "id"))
    except (TypeError, ValueError):
        return False
    return candidate_id == get_main_admin_user_id()


def is_managed_user(user_id: int) -> bool:
    conn = get_master_connection()
    try:
        row = conn.execute(
            "SELECT data_database_name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return bool(row and (row.get("data_database_name") or "").strip())
    finally:
        conn.close()


def get_user_permissions(user_id: int) -> set[str]:
    conn = get_master_connection()
    try:
        rows = conn.execute(
            "SELECT section_key FROM user_section_permissions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {row["section_key"] for row in rows}
    finally:
        conn.close()


def set_user_permissions(user_id: int, permissions: set[str]) -> None:
    safe_permissions = sorted(set(permissions) & set(SECTION_LABELS))
    conn = get_master_connection()
    try:
        conn.execute("DELETE FROM user_section_permissions WHERE user_id = ?", (user_id,))
        conn.executemany(
            """
            INSERT INTO user_section_permissions (user_id, section_key)
            VALUES (?, ?)
            """,
            [(user_id, section_key) for section_key in safe_permissions],
        )
        conn.commit()
    finally:
        conn.close()


def section_for_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    for section_key, endpoints in SECTION_ENDPOINTS.items():
        if endpoint in endpoints:
            return section_key
    return None


def has_section_access(section_key: str) -> bool:
    if not section_key:
        return True
    if not current_user.is_authenticated:
        return False
    if is_system_admin_user(current_user):
        return True
    if not is_managed_user(int(current_user.id)):
        return True
    return section_key in get_user_permissions(int(current_user.id))


def enforce_section_access():
    endpoint = request.endpoint
    if endpoint in SYSTEM_ENDPOINTS or endpoint in HOME_ENDPOINTS:
        return None
    if not current_user.is_authenticated:
        return None
    if is_system_admin_user(current_user):
        return None
    if not is_managed_user(int(current_user.id)):
        return None

    grouped_sections = GROUPED_ENDPOINT_ACCESS.get(endpoint)
    if grouped_sections:
        if any(has_section_access(section_key) for section_key in grouped_sections):
            return None
        if request.method == "GET":
            return redirect(url_for("index"))
        abort(403)

    section_key = section_for_endpoint(endpoint)
    if section_key and not has_section_access(section_key):
        if request.method == "GET":
            return redirect(url_for("index"))
        abort(403)
    return None


def user_data_directory() -> Path:
    configured = str(current_app.config.get("USER_DATABASE_DIR") or "").strip()
    if configured:
        return Path(configured)
    master_path = Path(Config.DATABASE_NAME)
    base_dir = master_path.parent if str(master_path.parent) not in {"", "."} else Path(".")
    return base_dir / "user_databases"


def _database_path_for_user(user_id: int, username: str) -> str:
    safe_username = re.sub(r"[^a-z0-9_-]+", "_", normalize_username(username)).strip("_")
    if not safe_username:
        safe_username = f"user_{user_id}"
    return str(user_data_directory() / f"user_{user_id}_{safe_username}.db")


def initialize_user_database(database_name: str) -> None:
    from app.learning import init_learning_db
    from app.nutrition import init_nutrition_db
    from app.planner import init_planner_db
    from app.web_push import init_web_push_db
    from app.workouts import init_workouts_db

    with use_database(database_name):
        init_db()
        init_planner_db()
        init_learning_db()
        init_workouts_db()
        init_nutrition_db()
        init_web_push_db()


def create_managed_user(form: ManagedUserForm, created_by_user_id: int) -> int:
    username = normalize_username(form.username)
    if not username:
        raise ValueError("Укажите логин пользователя.")
    if len(username) < 3:
        raise ValueError("Логин должен быть не короче 3 символов.")
    if not re.fullmatch(r"[a-z0-9_.-]+", username):
        raise ValueError("Логин может содержать только латиницу, цифры, точку, дефис и подчёркивание.")
    if len(form.password) < 8:
        raise ValueError("Пароль должен быть не короче 8 символов.")

    display_name = (form.display_name or "").strip() or username
    conn = get_master_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?)",
            (username,),
        ).fetchone()
        if existing:
            raise ValueError("Пользователь с таким логином уже существует.")

        cursor = conn.execute(
            """
            INSERT INTO users (
                username, display_name, password_hash, otp_secret, otp_enabled,
                created_by_user_id, is_system_admin, is_active
            )
            VALUES (?, ?, ?, ?, 0, ?, 0, 1)
            """,
            (
                username,
                display_name,
                generate_password_hash(form.password),
                generate_totp_secret(),
                created_by_user_id,
            ),
        )
        user_id = int(cursor.lastrowid)
        database_name = _database_path_for_user(user_id, username)
        conn.execute(
            "UPDATE users SET data_database_name = ? WHERE id = ?",
            (database_name, user_id),
        )
        conn.commit()
    finally:
        conn.close()

    initialize_user_database(database_name)
    set_user_permissions(user_id, form.permissions)
    return user_id


def update_managed_user(
    user_id: int,
    display_name: str | None,
    password: str,
    permissions: set[str],
) -> None:
    conn = get_master_connection()
    try:
        user = conn.execute(
            "SELECT id, is_system_admin FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            raise ValueError("Пользователь не найден.")
        if user.get("is_system_admin"):
            raise ValueError("Системного администратора нельзя изменить здесь.")

        updates: list[str] = []
        params: list[str] = []

        if display_name is not None:
            normalized_name = display_name.strip()
            if not normalized_name:
                raise ValueError("Укажите имя пользователя.")
            updates.append("display_name = ?")
            params.append(normalized_name)

        if password:
            if len(password) < 8:
                raise ValueError("Пароль должен быть не короче 8 символов.")
            updates.append("password_hash = ?")
            params.append(generate_password_hash(password))

        if updates:
            conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                (*params, user_id),
            )
            conn.commit()
    finally:
        conn.close()

    set_user_permissions(user_id, permissions)


def delete_managed_user(user_id: int) -> None:
    conn = get_master_connection()
    try:
        user = conn.execute(
            """
            SELECT id, username, is_system_admin, data_database_name, is_active
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if not user:
            raise ValueError("Пользователь не найден.")
        if user["is_system_admin"]:
            raise ValueError("Системного администратора нельзя удалить здесь.")
        if not (user["data_database_name"] or "").strip():
            raise ValueError("Этого пользователя нельзя удалить здесь.")

        deleted_username = f"{user['username']}__deleted_{user_id}"
        conn.execute(
            """
            UPDATE users
            SET username = ?, is_active = 0
            WHERE id = ?
            """,
            (deleted_username, user_id),
        )
        conn.execute("DELETE FROM user_section_permissions WHERE user_id = ?", (user_id,))
        conn.execute(
            "UPDATE user_login_sessions SET is_active = 0 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_managed_users() -> list[dict]:
    conn = get_master_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, username, display_name, data_database_name, is_active
            FROM users
            WHERE COALESCE(is_system_admin, 0) = 0
              AND COALESCE(is_active, 1) = 1
              AND COALESCE(TRIM(data_database_name), '') <> ''
            ORDER BY username COLLATE NOCASE ASC
            """
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            **dict(row),
            "permissions": get_user_permissions(int(row["id"])),
        }
        for row in rows
    ]


def build_managed_user_form(source) -> ManagedUserForm:
    return ManagedUserForm(
        username=source.get("username", ""),
        display_name=source.get("display_name", ""),
        password=source.get("password", ""),
        permissions={
            key
            for key in source.getlist("permissions")
            if key in SECTION_LABELS
        },
    )
