from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import sqlite3

from config import Config

_database_override = ContextVar("database_override", default=None)


class DictRow(dict):
    """
    Словарь-обёртка строки SQLite:
    - поддерживает доступ по имени колонки (row["name"])
    - поддерживает доступ по индексу (row[0], row[1], ...)
    - имеет стандартный dict.get(...)
    """

    def __init__(self, data, values):
        super().__init__(data)
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


def _dict_row_factory(cursor, row):
    columns = [column[0] for column in cursor.description]
    data = {column: row[index] for index, column in enumerate(columns)}
    return DictRow(data, row)


def _master_database_name():
    return Config.DATABASE_NAME


def get_master_connection():
    conn = sqlite3.connect(_master_database_name())
    conn.row_factory = _dict_row_factory
    return conn


def _active_user_database_name():
    try:
        from flask import has_request_context
        from flask_login import current_user
    except RuntimeError:
        return None

    if not has_request_context() or not current_user.is_authenticated:
        return None

    user_id = getattr(current_user, "id", None)
    if not user_id:
        return None

    conn = get_master_connection()
    try:
        row = conn.execute(
            "SELECT data_database_name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

    database_name = (row.get("data_database_name") if row else "") or ""
    if not database_name:
        return None
    return database_name


@contextmanager
def use_database(database_name):
    token = _database_override.set(database_name)
    try:
        yield
    finally:
        _database_override.reset(token)


def get_connection(database_name=None):
    """
    Создаёт подключение к SQLite и включает доступ к колонкам по имени.
    """
    active_database = (
        database_name
        or _database_override.get()
        or _active_user_database_name()
        or _master_database_name()
    )
    active_path = Path(active_database)
    if active_path.parent and str(active_path.parent) not in {"", "."}:
        active_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(active_path))
    conn.row_factory = _dict_row_factory
    return conn


def _get_table_columns(cursor, table_name):
    """
    Возвращает список колонок таблицы.
    """
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [column["name"] for column in cursor.fetchall()]


def _add_column_if_not_exists(cursor, table_name, column_name, column_definition):
    """
    Добавляет колонку в таблицу, только если её ещё нет.
    """
    columns = _get_table_columns(cursor, table_name)
    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def init_db(database_name=None):
    """
    Создаёт таблицы приложения и выполняет мягкие миграции
    для уже существующей базы.
    """
    conn = get_connection(database_name)
    cursor = conn.cursor()

    # VK-доставка удалена из приложения. Удаляем сохранённые токены и
    # служебные блокировки, чтобы старые настройки не могли ожить при откате.
    cursor.execute("DROP TABLE IF EXISTS vk_daily_send_locks")
    cursor.execute("DROP TABLE IF EXISTS vk_notification_settings")

    # =========================================================
    # SHOOTINGS
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shootings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            client_name TEXT NOT NULL,
            shooting_date TEXT NOT NULL,
            shooting_time TEXT,
            duration_hours REAL NOT NULL DEFAULT 1,
            phone TEXT,
            price REAL NOT NULL DEFAULT 0,
            prepayment REAL NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _add_column_if_not_exists(cursor, "shootings", "shooting_time", "TEXT")
    _add_column_if_not_exists(cursor, "shootings", "location", "TEXT")
    _add_column_if_not_exists(cursor, "shootings", "package_name", "TEXT")
    _add_column_if_not_exists(cursor, "shootings", "status", "TEXT NOT NULL DEFAULT 'Запланирована'")
    _add_column_if_not_exists(cursor, "shootings", "phone", "TEXT")
    _add_column_if_not_exists(cursor, "shootings", "price", "REAL NOT NULL DEFAULT 0")
    _add_column_if_not_exists(cursor, "shootings", "prepayment", "REAL NOT NULL DEFAULT 0")
    _add_column_if_not_exists(cursor, "shootings", "notes", "TEXT")
    _add_column_if_not_exists(cursor, "shootings", "duration_hours", "REAL NOT NULL DEFAULT 1")
    _add_column_if_not_exists(cursor, "shootings", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    # =========================================================
    # SCENARIOS
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            shooting_date TEXT NOT NULL,
            scenario_status TEXT NOT NULL DEFAULT 'in_progress',
            scenario_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _add_column_if_not_exists(
        cursor,
        "scenarios",
        "scenario_status",
        "TEXT NOT NULL DEFAULT 'in_progress'",
    )
    _add_column_if_not_exists(cursor, "scenarios", "scenario_text", "TEXT")
    _add_column_if_not_exists(cursor, "scenarios", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    # =========================================================
    # USERS
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            otp_secret TEXT,
            otp_enabled INTEGER NOT NULL DEFAULT 0,
            avatar_filename TEXT
        )
    """)
    _add_column_if_not_exists(cursor, "users", "otp_secret", "TEXT")
    _add_column_if_not_exists(cursor, "users", "otp_enabled", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_not_exists(cursor, "users", "avatar_filename", "TEXT")
    _add_column_if_not_exists(cursor, "users", "last_login_ip", "TEXT")
    _add_column_if_not_exists(cursor, "users", "display_name", "TEXT")
    _add_column_if_not_exists(cursor, "users", "data_database_name", "TEXT")
    _add_column_if_not_exists(cursor, "users", "created_by_user_id", "INTEGER")
    _add_column_if_not_exists(cursor, "users", "is_system_admin", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_not_exists(cursor, "users", "is_active", "INTEGER NOT NULL DEFAULT 1")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_section_permissions (
            user_id INTEGER NOT NULL,
            section_key TEXT NOT NULL,
            PRIMARY KEY (user_id, section_key)
        )
    """)

    # =========================================================
    # APP SETTINGS
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
    """)
    default_import_password = (Config.IMPORT_CENTER_PASSWORD or "").strip()
    existing_import_password = cursor.execute(
        "SELECT value FROM app_settings WHERE key = 'system_password'"
    ).fetchone()
    if not existing_import_password:
        cursor.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            ("system_password", default_import_password),
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            attempted_at TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_login_sessions (
            session_key TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            device TEXT NOT NULL,
            browser TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            first_login_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS car_notification_hidden (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notification_key TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """)

    # =========================================================
    # BUDGET BALANCE HISTORY
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget_balance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_name TEXT NOT NULL,
            year_value INTEGER NOT NULL DEFAULT 2026,
            balance_value REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =========================================================
    # BUDGET ENTRIES
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_type TEXT NOT NULL,
            month_name TEXT,
            year_value INTEGER NOT NULL DEFAULT 2026,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            entry_date TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    _add_column_if_not_exists(cursor, "budget_entries", "month_name", "TEXT")
    _add_column_if_not_exists(
        cursor,
        "budget_entries",
        "year_value",
        "INTEGER NOT NULL DEFAULT 2026",
    )
    _add_column_if_not_exists(cursor, "budget_entries", "entry_date", "TEXT")
    _add_column_if_not_exists(cursor, "budget_entries", "comment", "TEXT")
    _add_column_if_not_exists(
        cursor,
        "budget_entries",
        "created_at",
        "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    )

    # =========================================================
    # BUDGET SETTINGS
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget_settings (
            id INTEGER PRIMARY KEY,
            current_balance REAL NOT NULL DEFAULT 0
        )
    """)

    existing_settings = cursor.execute(
        "SELECT id FROM budget_settings WHERE id = 1"
    ).fetchone()

    if not existing_settings:
        cursor.execute("""
            INSERT INTO budget_settings (id, current_balance)
            VALUES (1, 0)
        """)

    # =========================================================
    # CAR DONE SERVICES
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS car_done_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            service_cost REAL NOT NULL DEFAULT 0,
            mileage INTEGER NOT NULL DEFAULT 0,
            service_date TEXT NOT NULL,
            detail_description TEXT,
            work_kind TEXT NOT NULL DEFAULT 'Разовая',
            period_type TEXT,
            status TEXT NOT NULL DEFAULT 'Выполнено',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    _add_column_if_not_exists(cursor, "car_done_services", "detail_description", "TEXT")
    _add_column_if_not_exists(
        cursor,
        "car_done_services",
        "work_kind",
        "TEXT NOT NULL DEFAULT 'Разовая'",
    )
    _add_column_if_not_exists(cursor, "car_done_services", "period_type", "TEXT")
    _add_column_if_not_exists(
        cursor,
        "car_done_services",
        "status",
        "TEXT NOT NULL DEFAULT 'Выполнено'",
    )
    _add_column_if_not_exists(
        cursor,
        "car_done_services",
        "created_at",
        "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    )

    # =========================================================
    # CAR PLANNED SERVICES
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS car_planned_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            planned_cost REAL NOT NULL DEFAULT 0,
            mileage INTEGER NOT NULL DEFAULT 0,
            detail_description TEXT,
            work_kind TEXT NOT NULL DEFAULT 'Разовая',
            period_type TEXT,
            status TEXT NOT NULL DEFAULT 'В работе',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    _add_column_if_not_exists(
        cursor,
        "car_planned_services",
        "mileage",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _add_column_if_not_exists(cursor, "car_planned_services", "detail_description", "TEXT")
    _add_column_if_not_exists(
        cursor,
        "car_planned_services",
        "work_kind",
        "TEXT NOT NULL DEFAULT 'Разовая'",
    )
    _add_column_if_not_exists(cursor, "car_planned_services", "period_type", "TEXT")
    _add_column_if_not_exists(
        cursor,
        "car_planned_services",
        "status",
        "TEXT NOT NULL DEFAULT 'В работе'",
    )
    _add_column_if_not_exists(
        cursor,
        "car_planned_services",
        "created_at",
        "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    )

    # =========================================================
    # CAR NOTIFICATIONS
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS car_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            period_value TEXT NOT NULL,
            last_service_date TEXT NOT NULL,
            mileage_at_service INTEGER NOT NULL DEFAULT 0,
            brand TEXT,
            status TEXT NOT NULL DEFAULT 'Скоро',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    _add_column_if_not_exists(cursor, "car_notifications", "brand", "TEXT")
    _add_column_if_not_exists(
        cursor,
        "car_notifications",
        "status",
        "TEXT NOT NULL DEFAULT 'Скоро'",
    )
    _add_column_if_not_exists(
        cursor,
        "car_notifications",
        "created_at",
        "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    )

    conn.commit()
    conn.close()
