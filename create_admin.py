#!/usr/bin/env python3
"""Create or update the main administrator and the import access password."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

from app.auth import generate_totp_secret
from app.database import get_connection, init_db
from config import Config


MIN_PASSWORD_LENGTH = 8


def _validate_username(username: str) -> str:
    normalized = (username or "").strip()
    if not normalized:
        raise ValueError("Имя администратора не может быть пустым.")
    if len(normalized) > 64:
        raise ValueError("Имя администратора должно быть не длиннее 64 символов.")
    if any(character.isspace() or ord(character) < 32 for character in normalized):
        raise ValueError("Имя администратора не должно содержать пробелы или служебные символы.")
    return normalized


def _validate_password(password: str, label: str) -> str:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"{label} должен содержать не менее {MIN_PASSWORD_LENGTH} символов."
        )
    return password


def configure_admins(
    username: str,
    admin_password: str,
    import_password: str,
) -> str:
    """Persist both credentials atomically and return created/updated status."""
    username = _validate_username(username)
    admin_password = _validate_password(
        admin_password,
        "Пароль основного администратора",
    )
    import_password = _validate_password(
        import_password,
        "Пароль администратора импорта",
    )
    if admin_password == import_password:
        raise ValueError("Пароли основного администратора и импорта должны отличаться.")

    init_db()
    connection = get_connection()
    try:
        existing_user = connection.execute(
            "SELECT id, otp_secret FROM users WHERE LOWER(username) = LOWER(?)",
            (username,),
        ).fetchone()
        password_hash = generate_password_hash(admin_password)

        if existing_user:
            user_id = existing_user["id"]
            otp_secret = existing_user["otp_secret"] or generate_totp_secret()
            connection.execute(
                """
                UPDATE users
                SET password_hash = ?, otp_secret = ?, is_system_admin = 1, is_active = 1
                WHERE id = ?
                """,
                (password_hash, otp_secret, user_id),
            )
            connection.execute(
                "UPDATE user_login_sessions SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )
            result = "updated"
        else:
            connection.execute(
                """
                INSERT INTO users (
                    username, password_hash, otp_secret, otp_enabled,
                    display_name, is_system_admin, is_active
                )
                VALUES (?, ?, ?, 0, ?, 1, 1)
                """,
                (username, password_hash, generate_totp_secret(), username),
            )
            result = "created"

        connection.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES ('system_password', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (import_password,),
        )
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _read_confirmed_password(label: str) -> str:
    first = getpass.getpass(f"{label}: ")
    second = getpass.getpass(f"Повторите {label.lower()}: ")
    if first != second:
        raise ValueError("Введённые пароли не совпадают.")
    return first


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Создаёт или обновляет основного администратора и отдельный пароль "
            "для раздела импорта данных."
        )
    )
    parser.add_argument(
        "--username",
        help="Имя основного администратора (по умолчанию ADMIN_USERNAME или admin).",
    )
    parser.add_argument(
        "--database",
        help="Путь к SQLite-базе (по умолчанию DATABASE_NAME из .env).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.database:
        Config.DATABASE_NAME = args.database

    default_username = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
    entered_username = args.username
    if entered_username is None:
        entered_username = input(
            f"Имя основного администратора [{default_username}]: "
        ).strip() or default_username

    try:
        admin_password = _read_confirmed_password("Пароль основного администратора")
        import_password = _read_confirmed_password("Пароль администратора импорта")
        result = configure_admins(
            entered_username,
            admin_password,
            import_password,
        )
    except (EOFError, KeyboardInterrupt):
        print("\nОперация отменена.", file=sys.stderr)
        return 130
    except ValueError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Не удалось сохранить администраторов: {error}", file=sys.stderr)
        return 1

    action = "создан" if result == "created" else "обновлён"
    database_path = Path(Config.DATABASE_NAME).resolve()
    print(f"Основной администратор '{entered_username}' {action}.")
    print("Отдельный пароль администратора импорта установлен.")
    print(f"База данных: {database_path}")
    if result == "updated":
        print("Все прежние активные сессии этого администратора завершены.")
    print(
        "Для импорта войдите под основным администратором, затем введите "
        "отдельный пароль импорта."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
