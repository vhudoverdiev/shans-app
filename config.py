import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()


class Config:
    """
    Класс с настройками приложения.
    Здесь хранятся основные конфиги проекта.
    """

    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "app.db")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")