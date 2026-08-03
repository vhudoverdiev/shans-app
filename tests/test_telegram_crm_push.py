import json
import unittest
from unittest.mock import patch

from telegram_crm_push import send_crm_push


class _Response:
    def __init__(self, body=b'{"ok": true, "sent": 1, "failed": 0}'):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body


class TelegramCrmPushClientTests(unittest.TestCase):
    def test_sends_minimal_payload_without_recipient_override(self):
        with patch("telegram_crm_push.urlopen", return_value=_Response()) as urlopen_mock:
            response = send_crm_push(
                "Bot finished.",
                title="Bot",
                navigate_path="/",
                url="https://crm.example.test/api/push/external/telegram",
                secret="test-secret",
            )

        self.assertEqual(response, {"ok": True, "sent": 1, "failed": 0})
        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {"title": "Bot", "body": "Bot finished.", "navigate_path": "/"})
        self.assertEqual(request.headers["X-shans-push-secret"], "test-secret")
        self.assertNotIn("username", payload)
        self.assertNotIn("user_id", payload)

    def test_requires_secret(self):
        with self.assertRaisesRegex(ValueError, "TELEGRAM_PUSH_SECRET"):
            send_crm_push(
                "Bot finished.",
                url="https://crm.example.test/api/push/external/telegram",
                secret="",
            )


if __name__ == "__main__":
    unittest.main()
