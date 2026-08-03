#!/usr/bin/env python3
"""Send a Telegram bot message copy into Shans CRM Web Push."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_CRM_PUSH_URL = "https://shansplanner.ru/api/push/external/telegram"
DEFAULT_TITLE = "Shans - Telegram"


def send_crm_push(
    body: str,
    *,
    title: str = DEFAULT_TITLE,
    navigate_path: str = "/",
    url: str | None = None,
    secret: str | None = None,
    timeout: float = 10,
) -> dict:
    resolved_body = (body or "").strip()
    if not resolved_body:
        raise ValueError("Push body must not be empty.")

    raw_url = url if url is not None else os.getenv("CRM_TELEGRAM_PUSH_URL")
    raw_secret = secret if secret is not None else os.getenv("TELEGRAM_PUSH_SECRET")
    resolved_url = (raw_url or DEFAULT_CRM_PUSH_URL).strip()
    resolved_secret = (raw_secret or "").strip()
    if not resolved_url:
        raise ValueError("CRM_TELEGRAM_PUSH_URL must not be empty.")
    if not resolved_secret:
        raise ValueError("TELEGRAM_PUSH_SECRET must be set.")

    payload = {
        "title": (title or DEFAULT_TITLE).strip() or DEFAULT_TITLE,
        "body": resolved_body,
        "navigate_path": (navigate_path or "/").strip() or "/",
    }
    request = Request(
        resolved_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Shans-Push-Secret": resolved_secret,
        },
        method="POST",
    )

    with urlopen(request, timeout=timeout) as response:
        raw_response = response.read()

    if not raw_response:
        return {}
    return json.loads(raw_response.decode("utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Duplicate a Telegram bot notification into Shans CRM push."
    )
    parser.add_argument("body", help="Notification text to send.")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Notification title.")
    parser.add_argument("--navigate-path", default="/", help="CRM path opened on tap.")
    parser.add_argument(
        "--url",
        default=None,
        help="CRM endpoint. Defaults to CRM_TELEGRAM_PUSH_URL or production URL.",
    )
    parser.add_argument(
        "--secret",
        default=None,
        help="Push secret. Defaults to TELEGRAM_PUSH_SECRET.",
    )
    parser.add_argument("--timeout", type=float, default=10, help="Request timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        response = send_crm_push(
            args.body,
            title=args.title,
            navigate_path=args.navigate_path,
            url=args.url,
            secret=args.secret,
            timeout=args.timeout,
        )
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        print(f"CRM push failed: HTTP {error.code} {details}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, ValueError) as error:
        print(f"CRM push failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
