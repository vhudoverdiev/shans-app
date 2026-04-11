import logging
import os
import secrets
import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from app.database import get_connection
from app.models import get_user_by_id


logger = logging.getLogger(__name__)


class User(UserMixin):
    """
    Класс пользователя для Flask-Login.
    """
    def __init__(self, user_id, username, password_hash, otp_enabled=False, avatar_filename=None):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash
        self.otp_enabled = bool(otp_enabled)
        self.avatar_filename = avatar_filename


def create_admin_if_not_exists():
    """
    Создаёт администратора при первом запуске,
    если его ещё нет в базе.
    """
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD")
    generated_password = None

    if not admin_password:
        if Config.is_production():
            raise RuntimeError("ADMIN_PASSWORD must be set in production mode")

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
        otp_secret = generate_totp_secret()
        cursor.execute(
            "INSERT INTO users (username, password_hash, otp_secret, otp_enabled) VALUES (?, ?, ?, 0)",
            (admin_username, password_hash, otp_secret)
        )
        conn.commit()
        if generated_password:
            logger.warning(
                "ADMIN_PASSWORD не задан. Создан временный пароль администратора: %s",
                generated_password,
            )

    if existing_user and not existing_user.get("otp_secret"):
        otp_secret = generate_totp_secret()
        cursor.execute(
            "UPDATE users SET otp_secret = ? WHERE id = ?",
            (otp_secret, existing_user["id"]),
        )
        conn.commit()

    conn.close()


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def register_failed_login(username, ip_address):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO login_attempts (username, ip_address, attempted_at)
        VALUES (?, ?, ?)
        """,
        (username, ip_address, _utcnow_iso()),
    )
    conn.commit()
    conn.close()


def clear_failed_logins(username, ip_address):
    conn = get_connection()
    conn.execute(
        "DELETE FROM login_attempts WHERE username = ? AND ip_address = ?",
        (username, ip_address),
    )
    conn.commit()
    conn.close()


def is_login_rate_limited(username, ip_address):
    window_seconds = Config.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    max_attempts = Config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
    lower_bound = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()

    conn = get_connection()
    count_row = conn.execute(
        """
        SELECT COUNT(*) AS attempts_count
        FROM login_attempts
        WHERE username = ? AND ip_address = ? AND attempted_at >= ?
        """,
        (username, ip_address, lower_bound),
    ).fetchone()
    conn.close()

    attempts_count = count_row["attempts_count"] if count_row else 0
    return attempts_count >= max_attempts


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
        return User(
            user["id"],
            user["username"],
            user["password_hash"],
            user.get("otp_enabled", 0),
            user.get("avatar_filename"),
        )

    return None


def load_user_from_db(user_id):
    """
    Загружает пользователя из базы по ID.
    """
    user = get_user_by_id(user_id)
    if user:
        return User(
            user["id"],
            user["username"],
            user["password_hash"],
            user.get("otp_enabled", 0),
            user.get("avatar_filename"),
        )
    return None


def generate_totp_secret():
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("utf-8").rstrip("=")


def _totp_code_for_counter(secret: str, counter: int) -> str:
    normalized = (secret or "").strip().replace(" ", "").upper()
    if not normalized:
        return ""
    padding = "=" * ((8 - (len(normalized) % 8)) % 8)
    key = base64.b32decode(normalized + padding)
    counter_bytes = counter.to_bytes(8, "big")
    digest = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = (
        ((digest[offset] & 0x7F) << 24)
        | ((digest[offset + 1] & 0xFF) << 16)
        | ((digest[offset + 2] & 0xFF) << 8)
        | (digest[offset + 3] & 0xFF)
    )
    return f"{binary % 1000000:06d}"


def verify_totp_code(secret: str, code: str, drift_windows: int = 1) -> bool:
    cleaned_code = (code or "").strip().replace(" ", "")
    if len(cleaned_code) != 6 or not cleaned_code.isdigit():
        return False
    now_counter = int(datetime.now(timezone.utc).timestamp() // 30)
    for offset in range(-drift_windows, drift_windows + 1):
        expected_code = _totp_code_for_counter(secret, now_counter + offset)
        if expected_code and hmac.compare_digest(expected_code, cleaned_code):
            return True
    return False
