import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
ACCOUNT_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "account_settings.html"
SETUP_2FA_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "setup_2fa.html"


class AccountSettingsLayoutTests(unittest.TestCase):
    def test_letter_avatar_uses_shared_centering_layer(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")
        base_template = BASE_TEMPLATE.read_text(encoding="utf-8")
        account_template = ACCOUNT_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('class="header-avatar-letter"', base_template)
        self.assertIn('class="header-avatar-letter" id="avatar-preview-letter"', account_template)
        self.assertIn('fallback.className = "header-avatar-letter";', base_template)
        self.assertRegex(
            stylesheet,
            r"\.header-avatar\s*\{[^}]*display:\s*inline-grid;[^}]*place-items:\s*center;[^}]*line-height:\s*1;",
        )
        self.assertRegex(
            stylesheet,
            r"\.header-avatar-letter\s*\{[^}]*display:\s*inline-grid;[^}]*place-items:\s*center;[^}]*transform:\s*translateY\(1px\);",
        )

    def test_account_settings_hides_redundant_security_tab_button(self):
        template = ACCOUNT_TEMPLATE.read_text(encoding="utf-8")
        mobile_styles = (
            PROJECT_ROOT / "app" / "static" / "css" / "mobile.css"
        ).read_text(encoding="utf-8")

        self.assertIn('data-account-panel="security"', template)
        self.assertNotIn('data-account-tab="security"', template)
        self.assertNotIn(">Безопасность</button>", template)
        self.assertIn('const initialTab = tabFromUrl && allowedTabs.has(tabFromUrl) ? tabFromUrl : "security";', template)
        self.assertIn("function syncTabUrl(target)", template)
        self.assertIn("window.history.replaceState", template)
        self.assertIn("activateTab(button.dataset.accountTab, true)", template)
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
        self.assertIn("data-managed-user-form", template)
        self.assertIn("data-managed-user-save-status", template)
        self.assertNotIn('id="managed_display_name_{{ user.id }}"', template)
        self.assertNotIn('input[name="display_name"], input[name="password"]', template)
        self.assertIn("url_for('delete_account_user'", template)
        self.assertIn('form="delete_managed_user_{{ user.id }}"', template)
        self.assertIn("account-managed-user-delete-form", template)
        self.assertIn("autosaveManagedUserForm", template)
        self.assertIn("managedUserPending", template)
        self.assertNotIn("user.data_database_name", template)
        self.assertNotIn("Сохранить пользователя", template)
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

    def test_mobile_login_and_logout_button_gap_is_compact(self):
        mobile_styles = (
            PROJECT_ROOT / "app" / "static" / "css" / "mobile.css"
        ).read_text(encoding="utf-8")

        profile_rule = mobile_styles.split(".account-profile-main-line {", 1)[1].split("}", 1)[0]
        logout_rule = mobile_styles.split(".account-logout-btn {", 1)[1].split("}", 1)[0]

        self.assertIn("margin-bottom: 6px;", profile_rule)
        self.assertIn("margin-top: 8px;", logout_rule)
        self.assertNotIn("margin-bottom: 12px;", profile_rule)
        self.assertNotIn("margin-top: 16px;", logout_rule)

    def test_hidden_inline_notice_does_not_reserve_vertical_space(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")

        self.assertRegex(
            stylesheet,
            r"\.account-inline-notice\[hidden\]\s*\{\s*display:\s*none;\s*\}",
        )

    def test_logout_all_devices_button_has_room_below_login_history(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")

        self.assertRegex(
            stylesheet,
            r"\.account-card\s+\.account-logout-all-form\s*\{[^}]*display:\s*block;[^}]*margin-top:\s*24px;",
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

    def test_setup_2fa_page_has_back_button_to_account_settings(self):
        template = SETUP_2FA_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("url_for('account_settings')", template)
        self.assertIn('class="btn btn-secondary">Назад</a>', template)

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
