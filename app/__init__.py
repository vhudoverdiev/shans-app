import os
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import Flask
from flask import request, session, abort, jsonify, redirect, url_for, flash
from flask_login import LoginManager

from config import Config
from app.auth import (
    load_user_from_db,
    create_admin_if_not_exists,
)
from app.database import init_db, get_connection
from app.routes import register_routes
from app.planner import planner_bp, init_planner_db
from app.logging_setup import setup_logging, register_request_hooks
from app.vk_notifications import (
    init_vk_notifications_db,
    start_vk_scheduler,
    diagnose_vk_notifications,
    send_vk_tomorrow_tasks_message,
    get_vk_settings,
    update_vk_settings,
)


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

    @app.cli.command("vk-diagnose")
    @click.option("--remote-check", is_flag=True, default=False, help="Also validate token/profile through VK API.")
    def vk_diagnose_cmd(remote_check):
        data = diagnose_vk_notifications(check_remote=remote_check)
        click.echo("VK notifications diagnostics:")
        for key in sorted(data.keys()):
            click.echo(f"- {key}: {data[key]}")

    @app.cli.command("vk-send-test")
    def vk_send_test_cmd():
        ok, message = send_vk_tomorrow_tasks_message(force=True)
        if ok:
            click.echo(f"ok: {message}")
            return
        raise click.ClickException(message)

    @app.cli.command("vk-set-config")
    @click.option("-token", "--token", default=None, help="VK access token.")
    @click.option("-profile-url", "--profile-url", default=None, help="VK profile URL, e.g. https://vk.com/username")
    @click.option("-timezone", "--timezone", default=None, help="Timezone, e.g. Europe/Moscow")
    @click.option("--enabled/--disabled", default=None, help="Enable or disable VK notifications.")
    def vk_set_config_cmd(token, profile_url, timezone, enabled):
        current = get_vk_settings()
        if not current:
            raise click.ClickException("VK settings row not found.")

        new_enabled = bool(current["is_enabled"]) if enabled is None else enabled
        new_token = (current["access_token"] or "") if token is None else token
        new_profile_url = (current["profile_url"] or "") if profile_url is None else profile_url
        new_timezone = (current["timezone_name"] or "Europe/Moscow") if timezone is None else timezone

        update_vk_settings(
            is_enabled=new_enabled,
            access_token=new_token,
            profile_url=new_profile_url,
            timezone_name=new_timezone,
        )
        click.echo("VK settings updated.")


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    if not app.config.get("AVATAR_UPLOAD_DIR"):
        app.config["AVATAR_UPLOAD_DIR"] = os.path.join(app.instance_path, "uploads", "avatars")
    os.makedirs(app.config["AVATAR_UPLOAD_DIR"], exist_ok=True)
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
    werkzeug_run_main = (os.getenv("WERKZEUG_RUN_MAIN") or "").strip().lower()
    if werkzeug_run_main in {"", "true", "1"}:
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

    @app.errorhandler(413)
    def handle_request_entity_too_large(_error):
        if request.path.startswith("/account/settings/avatar"):
            flash("Файл слишком большой для загрузки. Уменьшите размер изображения и попробуйте снова.", "danger")
            return redirect(url_for("account_settings"))
        return (
            jsonify({"status": "error", "message": "Payload too large"}),
            413,
        )

    return app
