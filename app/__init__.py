from flask import Flask
from flask_login import LoginManager

from config import Config
from app.auth import load_user_from_db, create_admin_if_not_exists
from app.database import init_db
from app.routes import register_routes
from app.planner import planner_bp, init_planner_db


login_manager = LoginManager()


def format_money(value):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "0 Р"
    return f"{number:,}".replace(",", " ") + " Р"


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Сначала войдите в систему."

    @login_manager.user_loader
    def load_user(user_id):
        return load_user_from_db(user_id)

    init_db()
    init_planner_db()
    create_admin_if_not_exists()

    register_routes(app)
    app.register_blueprint(planner_bp)

    app.jinja_env.filters["money"] = format_money
    return app
