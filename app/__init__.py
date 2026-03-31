import os
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import Flask
from flask import request, session, abort, jsonify
from flask_login import LoginManager

from config import Config
from app.auth import load_user_from_db, create_admin_if_not_exists
from app.database import init_db, get_connection
from app.routes import register_routes
from app.planner import planner_bp, init_planner_db
from app.logging_setup import setup_logging, register_request_hooks
from app.vk_notifications import init_vk_notifications_db, start_vk_scheduler


login_manager = LoginManager()


def format_money(value):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "0 Р"
    return f"{number:,}".replace(",", " ") + " Р"


def _register_management_commands(app):
    @app.cli.command("backup-db")
    @click.option("--output-dir", default="backups", help="Directory where backup file will be stored")
    def backup_db(output_dir):
        db_path = Path(app.config["DATABASE_NAME"])
        if not db_path.exists():
            raise click.ClickException(f"Database file not found: {db_path}")

        backup_dir = Path(output_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = backup_dir / f"{db_path.stem}_{timestamp}{db_path.suffix}"
        shutil.copy2(db_path, backup_path)
        click.echo(f"Database backup created: {backup_path}")

    @app.cli.command("healthcheck")
    def healthcheck_cmd():
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        click.echo("ok")


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    setup_logging(app)
    register_request_hooks(app)
    Config.validate_security_settings()

    if app.config.get("SECRET_KEY") == "dev_secret_key_change_me":
        app.logger.warning(
            "Используется небезопасный SECRET_KEY по умолчанию. "
            "Установите SECRET_KEY в переменных окружения."
        )

    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Сначала войдите в систему."

    @login_manager.user_loader
    def load_user(user_id):
        return load_user_from_db(user_id)

    init_db()
    init_planner_db()
    init_vk_notifications_db()
    create_admin_if_not_exists()

    register_routes(app)
    app.register_blueprint(planner_bp)
    _register_management_commands(app)
    if os.getenv("WERKZEUG_RUN_MAIN") in {None, "true"}:
        start_vk_scheduler(app)

    app.jinja_env.filters["money"] = format_money

    @app.route("/health")
    def health():
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify(
            {
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "environment": os.getenv("FLASK_ENV", "development"),
            }
        )

    @app.context_processor
    def inject_csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return {"csrf_token": token}

    @app.before_request
    def validate_csrf():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None

        if request.endpoint in {"static", "health"}:
            return None

        session_token = session.get("_csrf_token")
        if not session_token:
            abort(400, description="CSRF token missing in session")

        request_token = (
            request.form.get("_csrf_token")
            or request.headers.get("X-CSRFToken")
        )

        if request_token != session_token:
            abort(400, description="CSRF token mismatch")
        return None

    return app
