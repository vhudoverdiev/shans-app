import sqlite3
from config import Config


def get_connection():
    """
    Создаёт подключение к SQLite.
    """
    conn = sqlite3.connect(Config.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Создаёт таблицы проекта.
    Если таблица budget_entries уже существует, но в ней нет колонки month_name,
    то колонка будет добавлена.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_type TEXT NOT NULL,
            month_name TEXT,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            entry_date TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS car_done_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            service_cost REAL NOT NULL DEFAULT 0,
            mileage INTEGER NOT NULL DEFAULT 0,
            service_date TEXT NOT NULL,
            brand TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS car_planned_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            planned_cost REAL NOT NULL DEFAULT 0,
            priority TEXT DEFAULT 'Обычный',
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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
    
    cursor.execute("PRAGMA table_info(budget_entries)")
    columns = [column["name"] for column in cursor.fetchall()]

    if "month_name" not in columns:
        cursor.execute("ALTER TABLE budget_entries ADD COLUMN month_name TEXT")

    conn.commit()
    conn.close()