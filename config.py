import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """
    Класс с настройками приложения.
    Здесь хранятся основные конфиги проекта.
    """

    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_me")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "app.db")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    DEBUG = _to_bool(os.getenv("FLASK_DEBUG"), default=False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _to_bool(os.getenv("SESSION_COOKIE_SECURE"), default=False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    IMPORT_CENTER_PASSWORD = os.getenv("IMPORT_CENTER_PASSWORD", "")
