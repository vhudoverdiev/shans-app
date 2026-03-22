from flask import Flask
from flask_login import LoginManager

from config import Config
from app.auth import load_user_from_db, create_admin_if_not_exists
from app.database import init_db
from app.routes import register_routes

login_manager = LoginManager()


def create_app():
    """
    Создаём и настраиваем Flask-приложение.
    """

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    app.config.from_object(Config)

    # 1. Подключаем Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Сначала войдите в систему."

    @login_manager.user_loader
    def load_user(user_id):
        return load_user_from_db(user_id)

    # 2. Готовим базу данных
    init_db()

    # 3. Создаём администратора, если его ещё нет
    create_admin_if_not_exists()

    # 4. Регистрируем маршруты
    register_routes(app)

    return app