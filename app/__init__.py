from flask import Flask
from flask_login import LoginManager

from config import Config
from app.auth import load_user_from_db, create_admin_if_not_exists
from app.database import init_db
from app.routes import register_routes

try:
    from app.planner import register_planner_routes
except Exception:
    register_planner_routes = None


login_manager = LoginManager()


def format_money(value):
    """Форматирует число как деньги: 12500 -> 12 500 Р"""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "0 Р"
    return f"{number:,}".replace(",", " ") + " Р"


def _remove_route(app, endpoint_name: str) -> None:
    """
    Безопасно удаляет маршрут Flask по endpoint.
    Ничего не делает, если маршрут не найден.

    Важно: НЕ присваиваем app.url_map._rules новый список,
    потому что в некоторых версиях Werkzeug это read-only property.
    """
    rules_to_remove = [
        rule for rule in list(app.url_map.iter_rules()) if rule.endpoint == endpoint_name
    ]

    for rule in rules_to_remove:
        try:
            app.url_map._rules.remove(rule)
        except (ValueError, AttributeError):
            pass

        rules_by_endpoint = getattr(app.url_map, "_rules_by_endpoint", None)
        if isinstance(rules_by_endpoint, dict):
            endpoint_rules = rules_by_endpoint.get(endpoint_name, [])
            if rule in endpoint_rules:
                endpoint_rules.remove(rule)
            if not endpoint_rules and endpoint_name in rules_by_endpoint:
                rules_by_endpoint.pop(endpoint_name, None)

    app.view_functions.pop(endpoint_name, None)


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(Config)

    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Сначала войдите в систему."

    @login_manager.user_loader
    def load_user(user_id):
        return load_user_from_db(user_id)

    init_db()
    create_admin_if_not_exists()

    # Сначала подключаем старые маршруты
    register_routes(app)

    # Если есть новый модуль py, заменяем старые заглушки
    # на полноценные разделы графика и фотопроектов
    if register_planner_routes is not None:
        _remove_route(app, "schedule")
        _remove_route(app, "photo_projects")
        register_planner_routes(app)

    app.jinja_env.filters["money"] = format_money
    return app