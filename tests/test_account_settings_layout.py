import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
ACCOUNT_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "account_settings.html"


class AccountSettingsLayoutTests(unittest.TestCase):
    def test_account_settings_hides_redundant_security_tab_button(self):
        template = ACCOUNT_TEMPLATE.read_text(encoding="utf-8")
        mobile_styles = (
            PROJECT_ROOT / "app" / "static" / "css" / "mobile.css"
        ).read_text(encoding="utf-8")

        self.assertIn('data-account-panel="security"', template)
        self.assertNotIn('data-account-tab="security"', template)
        self.assertNotIn(">Безопасность</button>", template)
        self.assertIn('const initialTab = tabFromUrl && allowedTabs.has(tabFromUrl) ? tabFromUrl : "security";', template)
        self.assertRegex(
            mobile_styles,
            r"\.account-nav\s*\{\s*display:\s*none;",
        )

    def test_managed_users_section_is_desktop_only(self):
        template = ACCOUNT_TEMPLATE.read_text(encoding="utf-8")
        mobile_styles = (
            PROJECT_ROOT / "app" / "static" / "css" / "mobile.css"
        ).read_text(encoding="utf-8")

        self.assertIn("{% if can_manage_users %}", template)
        self.assertIn('data-account-tab="users"', template)
        self.assertIn('data-account-panel="users"', template)
        self.assertIn("account-users-desktop-only", template)
        self.assertIn("url_for('create_account_user')", template)
        self.assertIn("available_sections.items()", template)
        self.assertRegex(
            mobile_styles,
            r"\.account-users-desktop-only\s*\{\s*display:\s*none\s*!important;",
        )

    def test_profile_card_starts_without_removed_hero_gap(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")

        self.assertRegex(
            stylesheet,
            r"\.account-hero-card\s*\{[^}]*margin-top:\s*0;",
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

    def test_push_notifications_card_is_available_on_desktop(self):
        template = ACCOUNT_TEMPLATE.read_text(encoding="utf-8")
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")

        self.assertIn('id="push-notifications-card"', template)
        self.assertIn('id="push-notifications-toggle"', template)
        push_card = template.split('id="push-notifications-card"', 1)[1].split(
            '<div class="card account-card">',
            1,
        )[0]
        self.assertIn("data-push-toggle-mobile-label>Включить</span>", push_card)
        self.assertIn('id="push-notifications-status"', push_card)
        self.assertIn('aria-live="polite" hidden', push_card)
        self.assertNotIn("Уведомления личного графика", push_card)
        self.assertNotIn("В 10:00", push_card)
        self.assertNotIn('id="push-notifications-test"', push_card)
        self.assertIn("push-notifications.js", template)
        self.assertNotRegex(
            stylesheet,
            r"\.account-settings-page\s+\.account-push-card\s*\{\s*display:\s*none;",
        )
        self.assertRegex(
            stylesheet,
            r"\.account-push-status\[hidden\]\s*\{\s*display:\s*none;",
        )


if __name__ == "__main__":
    unittest.main()
