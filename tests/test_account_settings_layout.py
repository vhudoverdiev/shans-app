import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
ACCOUNT_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "account_settings.html"


class AccountSettingsLayoutTests(unittest.TestCase):
    def test_profile_card_uses_compact_spacing_below_page_subtitle(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")

        self.assertRegex(
            stylesheet,
            r"\.account-hero-card\s*\{[^}]*margin-top:\s*24px;",
        )

    def test_hidden_inline_notice_does_not_reserve_vertical_space(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")

        self.assertRegex(
            stylesheet,
            r"\.account-inline-notice\[hidden\]\s*\{\s*display:\s*none;\s*\}",
        )

    def test_authenticator_code_is_hidden_until_disable_is_requested(self):
        template = ACCOUNT_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn("autofocus", template)
        self.assertIn('id="show-disable-2fa-form"', template)
        self.assertRegex(template, r'id="disable-2fa-form"\s+hidden')
        self.assertIn('autocomplete="off" required', template)
        self.assertIn("function closeDisable2faForm()", template)
        self.assertIn("disable2faForm.hidden = false", template)
        self.assertIn("disable2faForm.hidden = true", template)
        self.assertIn("disable2faOtpInput.blur()", template)
        self.assertIn(
            'window.addEventListener("pageshow", closeDisable2faForm)',
            template,
        )
        self.assertIn('window.addEventListener("pagehide"', template)
        self.assertNotIn("data-manual-focus", template)
        self.assertNotIn("disable2faOtpInput.focus()", template)
        self.assertIn(
            'window.matchMedia("(max-width: 768px) and (pointer: coarse)")',
            template,
        )

        stylesheet = STYLE_FILE.read_text(encoding="utf-8")
        self.assertRegex(
            stylesheet,
            r"\.account-2fa-disable-form\[hidden\]\s*\{\s*display:\s*none;",
        )


if __name__ == "__main__":
    unittest.main()
