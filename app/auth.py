import os
import secrets
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.database import get_connection
from app.models import get_user_by_id


class User(UserMixin):
    """
    Класс пользователя для Flask-Login.
    """
    def __init__(self, user_id, username, password_hash):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash


def create_admin_if_not_exists():
    """
    Создаёт администратора при первом запуске,
    если его ещё нет в базе.
    """
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD")
    generated_password = None
    if not admin_password:
        generated_password = secrets.token_urlsafe(12)
        admin_password = generated_password

    conn = get_connection()
    cursor = conn.cursor()

    existing_user = cursor.execute(
        "SELECT * FROM users WHERE username = ?",
        (admin_username,)
    ).fetchone()

    if not existing_user:
        password_hash = generate_password_hash(admin_password)
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (admin_username, password_hash)
        )
        conn.commit()
        if generated_password:
            print(
                "WARNING: ADMIN_PASSWORD не задан. "
                f"Создан временный пароль администратора: {generated_password}"
            )

    conn.close()


def verify_user(username, password):
    """
    Проверяет логин и пароль пользователя.
    """
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        return User(user["id"], user["username"], user["password_hash"])

    return None


def load_user_from_db(user_id):
    """
    Загружает пользователя из базы по ID.
    """
    user = get_user_by_id(user_id)
    if user:
        return User(user["id"], user["username"], user["password_hash"])
    return None
