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
    ENV = os.getenv("FLASK_ENV", "development")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _to_bool(os.getenv("SESSION_COOKIE_SECURE"), default=False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    IMPORT_CENTER_PASSWORD = os.getenv("IMPORT_CENTER_PASSWORD", "")

    LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "900"))
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5"))

    @classmethod
    def is_production(cls) -> bool:
        env = (cls.ENV or "").strip().lower()
        return env == "production" and not cls.DEBUG

    @classmethod
    def validate_security_settings(cls):
        if not cls.is_production():
            return

        if cls.SECRET_KEY == "dev_secret_key_change_me":
            raise RuntimeError(
                "Production startup blocked: SECRET_KEY must be set via environment variable."
            )

        if not os.getenv("ADMIN_PASSWORD"):
            raise RuntimeError(
                "Production startup blocked: ADMIN_PASSWORD must be set via environment variable."
            )
