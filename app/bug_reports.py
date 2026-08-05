from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ipaddress

from app.database import get_master_connection


BUG_REPORT_NAME_MAX_LENGTH = 80
BUG_REPORT_DESCRIPTION_MAX_LENGTH = 2000
BUG_REPORT_DAILY_LIMIT = 3


class BugReportLimitExceeded(ValueError):
    pass


def _normalize_text(value: object, max_length: int) -> str:
    return " ".join(str(value or "").strip().split())[:max_length]


def _normalize_description(value: object) -> str:
    return str(value or "").strip()[:BUG_REPORT_DESCRIPTION_MAX_LENGTH]


def build_bug_report_rate_limit_key(ip_address: object) -> str:
    normalized_ip = _normalize_text(ip_address or "unknown", 128) or "unknown"
    try:
        address = ipaddress.ip_address(normalized_ip)
    except ValueError:
        return f"raw:{normalized_ip.lower()}"

    if isinstance(address, ipaddress.IPv4Address):
        network = ipaddress.ip_network(f"{address}/24", strict=False)
        return f"ipv4:{network}"

    network = ipaddress.ip_network(f"{address}/64", strict=False)
    return f"ipv6:{network}"


def create_bug_report(user_id, name, description, ip_address, user_agent="", page_url=""):
    normalized_name = _normalize_text(name, BUG_REPORT_NAME_MAX_LENGTH)
    normalized_description = _normalize_description(description)
    normalized_ip = _normalize_text(ip_address or "unknown", 128) or "unknown"
    rate_limit_key = build_bug_report_rate_limit_key(normalized_ip)
    normalized_user_agent = _normalize_text(user_agent, 500)
    normalized_page_url = _normalize_text(page_url, 500)

    if not normalized_name:
        raise ValueError("Укажите имя.")
    if not normalized_description:
        raise ValueError("Опишите ошибку.")

    conn = get_master_connection()
    try:
        sent_today = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM bug_reports
            WHERE (
                rate_limit_key = ?
                OR (rate_limit_key IS NULL AND ip_address = ?)
                OR (? IS NOT NULL AND user_id = ?)
            )
              AND datetime(created_at) >= datetime('now', 'start of day')
            """,
            (rate_limit_key, normalized_ip, user_id, user_id),
        ).fetchone()
        if int(sent_today["total"] if sent_today else 0) >= BUG_REPORT_DAILY_LIMIT:
            raise BugReportLimitExceeded("Лимит: максимум 3 сообщения об ошибке в сутки.")

        created_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat(sep=" ")
        cursor = conn.execute(
            """
            INSERT INTO bug_reports (
                user_id,
                name,
                description,
                ip_address,
                rate_limit_key,
                user_agent,
                page_url,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                normalized_name,
                normalized_description,
                normalized_ip,
                rate_limit_key,
                normalized_user_agent,
                normalized_page_url,
                created_at,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_recent_bug_reports(days=30, limit=200):
    threshold = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).replace(
        tzinfo=None,
        microsecond=0,
    ).isoformat(sep=" ")
    safe_limit = max(1, min(int(limit), 500))
    conn = get_master_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                bug_reports.id,
                bug_reports.user_id,
                bug_reports.name,
                bug_reports.description,
                bug_reports.ip_address,
                bug_reports.user_agent,
                bug_reports.page_url,
                bug_reports.created_at,
                users.username
            FROM bug_reports
            LEFT JOIN users ON users.id = bug_reports.user_id
            WHERE datetime(bug_reports.created_at) >= datetime(?)
            ORDER BY datetime(bug_reports.created_at) DESC, bug_reports.id DESC
            LIMIT ?
            """,
            (threshold, safe_limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
