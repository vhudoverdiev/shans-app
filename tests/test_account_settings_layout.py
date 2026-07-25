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

    def test_mobile_authenticator_input_waits_for_deliberate_user_interaction(self):
        template = ACCOUNT_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn("autofocus", template)
        self.assertIn("autocomplete=\"off\" readonly data-manual-focus", template)
        self.assertIn("function enableManualInput(event)", template)
        self.assertIn('input.addEventListener("pointerdown", enableManualInput', template)
        self.assertIn('input.addEventListener("touchstart", enableManualInput', template)
        self.assertIn('input.addEventListener("keydown", enableManualInput', template)
        self.assertIn("dismissRestoredMobileInputFocus", template)
        self.assertIn('window.addEventListener("pageshow"', template)
        self.assertIn("activeElement.blur()", template)
        self.assertIn(
            'window.matchMedia("(max-width: 768px) and (pointer: coarse)")',
            template,
        )


if __name__ == "__main__":
    unittest.main()
