import logging
import time
from collections import defaultdict, deque
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import has_request_context, request
from flask_login import current_user
from werkzeug.exceptions import HTTPException


SUSPICIOUS_STATUS_CODES = {400, 403, 429, 500}


def _current_username() -> str:
    if current_user and getattr(current_user, "is_authenticated", False):
        return current_user.username
    return "anonymous"


def _client_ip() -> str:
    if not has_request_context():
        return "n/a"
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def setup_logging(app):
    logs_dir = Path(app.root_path).parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    technical_handler = RotatingFileHandler(
        logs_dir / "technical.log", maxBytes=1_048_576, backupCount=5, encoding="utf-8"
    )
    technical_handler.setLevel(logging.INFO)
    technical_handler.setFormatter(formatter)

    audit_handler = RotatingFileHandler(
        logs_dir / "audit.log", maxBytes=1_048_576, backupCount=10, encoding="utf-8"
    )
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(formatter)

    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(technical_handler)

    app.audit_logger = logging.getLogger("audit")
    app.audit_logger.setLevel(logging.INFO)
    app.audit_logger.handlers.clear()
    app.audit_logger.addHandler(audit_handler)
    app.audit_logger.propagate = False

    app.extensions["request_counters"] = defaultdict(deque)



def log_audit(app, event: str, **details):
    username = _current_username()
    ip_address = _client_ip()
    payload = " ".join(f"{key}={value!r}" for key, value in details.items())
    app.audit_logger.info(
        "event=%s user=%s ip=%s path=%s method=%s %s",
        event,
        username,
        ip_address,
        request.path if has_request_context() else "n/a",
        request.method if has_request_context() else "n/a",
        payload,
    )



def log_invalid_form(app, form_name: str, reason: str):
    app.logger.warning(
        "Invalid form: form=%s reason=%s user=%s ip=%s path=%s",
        form_name,
        reason,
        _current_username(),
        _client_ip(),
        request.path if has_request_context() else "n/a",
    )



def log_import_result(app, import_type: str, rows_added: int, errors_count: int, mode: str):
    log_audit(
        app,
        "excel_import",
        import_type=import_type,
        rows_added=rows_added,
        errors_count=errors_count,
        mode=mode,
    )
    app.logger.info(
        "Excel import completed: type=%s mode=%s rows_added=%s errors=%s user=%s ip=%s",
        import_type,
        mode,
        rows_added,
        errors_count,
        _current_username(),
        _client_ip(),
    )



def register_request_hooks(app):
    @app.before_request
    def track_request_rate():
        ip_address = _client_ip()
        key = f"{ip_address}:{request.endpoint}"
        window = 60
        threshold = 80
        now = time.time()
        bucket = app.extensions["request_counters"][key]
        bucket.append(now)
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) > threshold:
            app.logger.warning(
                "Suspicious frequent requests: ip=%s endpoint=%s count=%s window=%ss",
                ip_address,
                request.endpoint,
                len(bucket),
                window,
            )

    @app.after_request
    def log_suspicious_statuses(response):
        if response.status_code in SUSPICIOUS_STATUS_CODES or response.status_code >= 500:
            app.logger.warning(
                "Suspicious HTTP response: status=%s method=%s path=%s user=%s ip=%s",
                response.status_code,
                request.method,
                request.path,
                _current_username(),
                _client_ip(),
            )
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error

        app.logger.exception(
            "Unhandled Flask exception: method=%s path=%s user=%s ip=%s",
            request.method,
            request.path,
            _current_username(),
            _client_ip(),
        )
        raise error
