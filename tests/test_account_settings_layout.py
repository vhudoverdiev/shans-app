import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "style.css"


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


if __name__ == "__main__":
    unittest.main()
