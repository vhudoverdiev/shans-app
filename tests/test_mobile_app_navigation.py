import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = PROJECT_ROOT / "app" / "templates"
STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
MOBILE_STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "mobile.css"
NUTRITION_STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "nutrition.css"


class MobileAppNavigationTests(unittest.TestCase):
    def test_desktop_dashboard_includes_study_card(self):
        source = (TEMPLATES / "index.html").read_text(encoding="utf-8")
        desktop_grid = re.search(
            r'<div class="dashboard-grid dashboard-grid-desktop">(?P<body>.*?)'
            r'<div class="dashboard-grid dashboard-grid-mobile',
            source,
            re.DOTALL,
        )

        self.assertIsNotNone(desktop_grid)
        body = desktop_grid.group("body")
        self.assertEqual(body.count('class="dashboard-card"'), 8)
        for endpoint in (
            "budget",
            "car",
            "planner.schedule",
            "shootings",
            "planner.photo_projects",
            "scenarios",
            "learning.study_hub",
            "sport_hub",
        ):
            self.assertIn(f"url_for('{endpoint}')", body)
        self.assertIn('<div class="dashboard-card-title">Учёба</div>', body)
        self.assertIn('<div class="dashboard-card-title">Спорт</div>', body)

    def test_dashboard_does_not_render_welcome_purple_block(self):
        source = (TEMPLATES / "index.html").read_text(encoding="utf-8")

        self.assertNotIn("welcome-card", source)
        self.assertNotIn("welcome-name", source)
        self.assertNotIn("Добро пожаловать", source)

    def test_mobile_dashboard_has_only_requested_sections(self):
        source = (TEMPLATES / "index.html").read_text(encoding="utf-8")
        mobile_grid = source.split(
            '<div class="dashboard-grid dashboard-grid-mobile dashboard-primary-grid">',
            1,
        )[1]

        self.assertEqual(
            mobile_grid.count('class="dashboard-card')
            - mobile_grid.count('class="dashboard-card-icon')
            - mobile_grid.count('class="dashboard-card-title')
            - mobile_grid.count('class="dashboard-card-text')
            - mobile_grid.count('class="dashboard-card-arrow'),
            5,
        )
        self.assertIn("url_for('planner.schedule')", mobile_grid)
        self.assertIn("url_for('shootings_hub')", mobile_grid)
        self.assertIn("url_for('reports_hub')", mobile_grid)
        self.assertIn("url_for('learning.study_hub')", mobile_grid)
        self.assertIn("url_for('sport_hub')", mobile_grid)
        self.assertIn('<div class="dashboard-card-title">Учёба</div>', mobile_grid)
        self.assertIn('<div class="dashboard-card-title">Спорт</div>', mobile_grid)

    def test_desktop_shootings_nav_opens_booking_list_and_mobile_keeps_hub(self):
        source = (TEMPLATES / "base.html").read_text(encoding="utf-8")
        top_nav = source.split('<nav class="top-nav" id="top-nav-menu">', 1)[1].split(
            '<div class="header-user-block">',
            1,
        )[0]
        bottom_nav = source.split('<nav class="app-bottom-nav"', 1)[1].split(
            '<button',
            1,
        )[0]

        self.assertIn("url_for('shootings')", top_nav)
        self.assertNotIn("url_for('shootings_hub')", top_nav)
        self.assertIn("url_for('shootings_hub')", bottom_nav)

    def test_mobile_hubs_group_existing_sections(self):
        shootings = (TEMPLATES / "shootings_hub.html").read_text(encoding="utf-8")
        reports = (TEMPLATES / "reports_hub.html").read_text(encoding="utf-8")
        sport = (TEMPLATES / "sport_hub.html").read_text(encoding="utf-8")
        routes = (PROJECT_ROOT / "app" / "routes.py").read_text(encoding="utf-8")

        for endpoint in ("planner.photo_projects", "shootings", "scenarios"):
            self.assertIn(f"url_for('{endpoint}')", shootings)
        for endpoint in ("budget", "car"):
            self.assertIn(f"url_for('{endpoint}')", reports)
        for endpoint in ("workouts.index", "nutrition.index"):
            self.assertIn(f"url_for('{endpoint}')", sport)
        self.assertIn('@app.route("/shootings-hub")', routes)
        self.assertIn('@app.route("/reports")', routes)
        self.assertIn('@app.route("/sport")', routes)

    def test_subsection_pages_include_back_buttons_to_their_hubs(self):
        shooting_section_templates = (
            "photo_projects.html",
            "shootings_upcoming.html",
            "shootings_archive.html",
            "scenarios_upcoming.html",
            "scenarios_archive.html",
        )
        for template_name in shooting_section_templates:
            source = (TEMPLATES / template_name).read_text(encoding="utf-8")
            self.assertIn("url_for('shootings_hub')", source, template_name)
            self.assertIn('class="btn btn-secondary">Назад</a>', source, template_name)

        for template_name, endpoint in (
            ("shootings_add.html", "shootings_upcoming"),
            ("shooting_edit.html", "shootings_archive' if shooting.is_archive else 'shootings_upcoming"),
            ("scenarios_add.html", "scenarios_upcoming"),
            ("scenario_edit.html", "scenarios_archive' if scenario.is_archive else 'scenarios_upcoming"),
        ):
            source = (TEMPLATES / template_name).read_text(encoding="utf-8")
            self.assertIn(f"url_for('{endpoint}')", source, template_name)
            self.assertIn('class="btn btn-secondary">Назад</a>', source, template_name)

        for template_name in ("budget.html", "car.html"):
            source = (TEMPLATES / template_name).read_text(encoding="utf-8")
            self.assertIn("url_for('reports_hub')", source, template_name)
            self.assertIn('class="btn btn-secondary">Назад</a>', source, template_name)

        car_notifications = (TEMPLATES / "car_notifications.html").read_text(encoding="utf-8")
        self.assertIn("url_for('car')", car_notifications)
        self.assertIn('class="btn btn-secondary">Назад</a>', car_notifications)

    def test_car_header_actions_are_compact_icon_buttons_on_mobile(self):
        car_template = (TEMPLATES / "car.html").read_text(encoding="utf-8")
        mobile_styles = MOBILE_STYLE_FILE.read_text(encoding="utf-8")
        styles = STYLE_FILE.read_text(encoding="utf-8")

        self.assertIn("car-header-actions", car_template)
        self.assertEqual(car_template.count("car-header-icon-link"), 3)
        for label in ("Редактировать марку", "Периодические ТО", "Добавить работу"):
            self.assertIn(f'title="{label}"', car_template)
            self.assertIn(f'aria-label="{label}"', car_template)
            self.assertIn(f'data-tooltip="{label}"', car_template)
            self.assertNotIn(f">{label}</a>", car_template)

        self.assertIn(".car-header-icon-link::after", styles)
        self.assertIn("content: attr(data-tooltip);", styles)
        self.assertIn(".car-header-actions {", mobile_styles)
        car_header_mobile_rule = mobile_styles.split(".car-header-actions {", 1)[1].split("}", 1)[0]
        self.assertIn("display: grid;", car_header_mobile_rule)
        self.assertIn("grid-template-columns: minmax(76px, 1fr) repeat(3, 52px);", car_header_mobile_rule)
        self.assertIn("overflow: visible;", car_header_mobile_rule)
        self.assertNotIn("overflow-x: auto;", car_header_mobile_rule)

    def test_service_sections_do_not_render_hero_headers(self):
        styles = STYLE_FILE.read_text(encoding="utf-8")
        mobile_styles = MOBILE_STYLE_FILE.read_text(encoding="utf-8")

        for template_name in (
            "schedule.html",
            "shootings_hub.html",
            "reports_hub.html",
            "sport_hub.html",
            "account_settings.html",
            "study_hub.html",
        ):
            source = (TEMPLATES / template_name).read_text(encoding="utf-8")
            self.assertIn("section-styled-page", source)
            self.assertNotIn("section-hero", source)
            self.assertNotIn("section-hero-kicker", source)

        self.assertNotIn(".section-hero", styles)
        self.assertNotIn(".section-hero", mobile_styles)
        self.assertNotIn("section-hero-schedule", styles)
        self.assertNotIn("section-hero-schedule", mobile_styles)

        study_hub = (TEMPLATES / "study_hub.html").read_text(encoding="utf-8")
        self.assertNotIn("learning-hero-mark", study_hub)

    def test_service_section_cards_keep_desktop_neutral_theme(self):
        styles = STYLE_FILE.read_text(encoding="utf-8")
        desktop_neutral_theme = styles.split(
            "/* Desktop keeps service section cards neutral;",
            1,
        )[1]

        self.assertIn("@media (hover: hover) and (pointer: fine)", desktop_neutral_theme)
        self.assertIn(".section-styled-page .hub-grid .dashboard-card", desktop_neutral_theme)
        self.assertIn("background: #ffffff;", desktop_neutral_theme)
        self.assertIn("border-color: #e5eaf2;", desktop_neutral_theme)

    def test_bottom_navigation_replaces_mobile_avatar_menu(self):
        base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
        mobile_styles = MOBILE_STYLE_FILE.read_text(encoding="utf-8")

        self.assertNotIn("mobile-fab", base)
        self.assertNotIn("mobile-fab", mobile_styles)
        self.assertEqual(base.count('class="app-bottom-nav-link '), 6)
        for label in ("График", "Съёмки", "Отчёт", "Развитие", "Спорт", "Аккаунт"):
            self.assertIn(f"<span>{label}</span>", base)
        self.assertNotIn("<span>Учёба</span>", base)
        self.assertNotIn("<span>Главная</span>", base)
        self.assertIn('data-nav-count="{{ bottom_nav_count }}"', base)
        self.assertIn("show_bottom_schedule", base)
        self.assertIn("show_bottom_reports", base)
        self.assertIn("show_bottom_sport", base)
        self.assertIn("grid-template-columns: repeat(6, minmax(0, 1fr));", mobile_styles)
        for count in ("1", "2", "3", "4", "5"):
            self.assertIn(f'.app-bottom-nav[data-nav-count="{count}"]', mobile_styles)
        self.assertIn("--app-bottom-nav-width: 224px;", mobile_styles)
        self.assertIn("--app-bottom-nav-width: 560px;", mobile_styles)
        self.assertIn("bottom: 0;", mobile_styles)
        self.assertIn("padding: 7px 7px calc(7px + env(safe-area-inset-bottom));", mobile_styles)
        self.assertIn("html.shans-standalone-app .app-bottom-nav", mobile_styles)
        self.assertIn("overscroll-behavior-y: none;", mobile_styles)
        self.assertIn("html.shans-standalone-app .app-body-authenticated .page-shell", mobile_styles)
        self.assertIn("min-height: 100dvh;", mobile_styles)
        self.assertIn("padding-bottom: 106px;", mobile_styles)
        self.assertIn("bottom: 0;", mobile_styles.split("html.shans-standalone-app .app-bottom-nav", 1)[1].split("}", 1)[0])
        self.assertIn("padding: 7px;", mobile_styles)
        self.assertIn("transform: translate3d(-50%, 0, 0);", mobile_styles)
        self.assertIn("will-change: transform;", mobile_styles)
        self.assertIn("html.shans-standalone-app .account-settings-page", mobile_styles)
        self.assertIn("min-height: calc(100dvh - 106px);", mobile_styles)
        self.assertIn("html.shans-standalone-app .mobile-push-inbox-trigger", mobile_styles)
        self.assertIn("bottom: 91px;", mobile_styles)
        self.assertIn("border-radius: 24px 24px 0 0;", mobile_styles)
        self.assertNotIn("bottom: max(9px, env(safe-area-inset-bottom));", mobile_styles)
        self.assertIn("is_reports_section", base)
        self.assertIn("url_for('reports_hub')", base)
        self.assertIn("is_study_section", base)
        self.assertIn("url_for('learning.study_hub')", base)
        self.assertIn("is_workouts_section", base)
        self.assertIn("is_nutrition_section", base)
        self.assertIn("is_sport_section", base)
        self.assertIn("url_for('sport_hub')", base)
        self.assertIn(
            "{% set is_mobile_development_section = is_development_section %}",
            base,
        )
        self.assertIn(
            "@media (max-width: 900px) and (pointer: coarse)",
            mobile_styles,
        )
        self.assertIn(
            ".page-shell {\n        padding: max(12px, env(safe-area-inset-top)) max(10px, env(safe-area-inset-right)) max(20px, env(safe-area-inset-bottom)) max(10px, env(safe-area-inset-left));\n    }",
            mobile_styles,
        )
        self.assertIn(".app-bottom-nav-link-active", mobile_styles)
        self.assertIn("env(safe-area-inset-bottom)", mobile_styles)

    def test_mobile_only_elements_are_hidden_on_desktop(self):
        styles = STYLE_FILE.read_text(encoding="utf-8")
        mobile_styles = MOBILE_STYLE_FILE.read_text(encoding="utf-8")
        account = (TEMPLATES / "account_settings.html").read_text(encoding="utf-8")

        self.assertRegex(
            styles,
            r"\.dashboard-grid-mobile,\s*\.app-bottom-nav\s*\{\s*display:\s*none;",
        )
        self.assertRegex(
            styles,
            r"\.account-logout-btn\s*\{\s*display:\s*none\s*!important;",
        )
        self.assertNotRegex(
            styles,
            r"\.account-settings-page\s+\.account-push-card\s*\{\s*display:\s*none;",
        )
        self.assertRegex(
            mobile_styles,
            r"\.dashboard-grid-desktop\s*\{\s*display:\s*none\s*!important;",
        )
        self.assertRegex(
            mobile_styles,
            r"\.account-logout-btn\s*\{[^}]*display:\s*inline-flex\s*!important;",
        )
        self.assertRegex(
            mobile_styles,
            r"\.account-settings-page\s+\.account-push-card\s*\{\s*display:\s*block;",
        )
        self.assertIn("url_for('logout')", account)
        self.assertIn('id="account-logout-btn"', account)

    def test_mobile_page_headers_hide_text_but_keep_page_actions(self):
        styles = STYLE_FILE.read_text(encoding="utf-8")
        mobile_styles = MOBILE_STYLE_FILE.read_text(encoding="utf-8")

        self.assertRegex(
            mobile_styles,
            r"\.page-header\s*>\s*:not\(\.page-actions\)\s*\{\s*"
            r"display:\s*none;",
        )
        self.assertRegex(
            mobile_styles,
            r"\.page-header\s*>\s*\.page-actions\s*\{[^}]*"
            r"margin-bottom:\s*14px;",
        )
        self.assertNotRegex(
            styles,
            r"\.page-header\s*>\s*:not\(\.page-actions\)",
        )

    def test_flash_messages_are_full_width_at_the_bottom(self):
        styles = STYLE_FILE.read_text(encoding="utf-8")

        self.assertRegex(
            styles,
            r"\.flash-stack\s*\{"
            r"[^}]*left:\s*24px;"
            r"[^}]*right:\s*24px;"
            r"[^}]*width:\s*auto;",
        )
        mobile_flash_rule = styles.split(
            "bottom: calc(86px + env(safe-area-inset-bottom, 0px));",
            1,
        )[0].rsplit(".flash-stack {", 1)[1]
        self.assertIn("left: 14px;", mobile_flash_rule)
        self.assertIn("right: 14px;", mobile_flash_rule)
        mobile_flash_rule_after_bottom = styles.split(
            "bottom: calc(86px + env(safe-area-inset-bottom, 0px));",
            1,
        )[1].split("}", 1)[0]
        self.assertIn("width: auto;", mobile_flash_rule_after_bottom)
        self.assertNotIn("width: min(340px", mobile_flash_rule)

    def test_mobile_blue_buttons_use_bottom_navigation_purple_theme(self):
        styles = STYLE_FILE.read_text(encoding="utf-8")
        mobile_styles = MOBILE_STYLE_FILE.read_text(encoding="utf-8")

        self.assertIn(
            "--mobile-action-gradient: linear-gradient(135deg, #2563eb, #7c3aed);",
            mobile_styles,
        )
        for selector in (
            ".app-body .btn-primary",
            ".app-body .btn-tab-active",
            ".app-body .car-tab-link-active",
            ".app-body .budget-mobile-tab-btn-active",
            ".app-body .shooting-nav-link-active",
            ".app-body .app-bottom-nav-link-active",
            ".app-body .planner-calendar-switch-link-active",
            ".app-body .btn-secondary",
        ):
            self.assertIn(selector, mobile_styles)
        self.assertIn(
            "background: var(--mobile-action-gradient);",
            mobile_styles,
        )
        self.assertIn("--mobile-action-shadow: none;", mobile_styles)
        no_mobile_button_glow = mobile_styles.split(
            "@media (max-width: 900px) and (pointer: coarse) {",
            1,
        )[1]
        self.assertIn(".app-body .app-bottom-nav-link-active", no_mobile_button_glow)
        self.assertIn(".app-body .shooting-nav-link-active", no_mobile_button_glow)
        self.assertIn(".app-body .btn-tab-active", no_mobile_button_glow)
        self.assertIn("box-shadow: none !important;", no_mobile_button_glow)
        self.assertIn("filter: none !important;", no_mobile_button_glow)
        self.assertIn(
            ".app-body .planner-calendar-switch-link-active {\n        box-shadow: none;",
            mobile_styles,
        )
        self.assertIn(
            ".app-bottom-nav-link-active {\n        color: #ffffff;\n        background: var(--mobile-action-gradient);\n        box-shadow: none;",
            mobile_styles,
        )
        self.assertNotIn("--mobile-action-gradient", styles)

    def test_button_styles_do_not_add_square_glow(self):
        styles = STYLE_FILE.read_text(encoding="utf-8")
        mobile_styles = MOBILE_STYLE_FILE.read_text(encoding="utf-8")
        nutrition_styles = NUTRITION_STYLE_FILE.read_text(encoding="utf-8")

        for selector in (
            ".top-nav-link-active",
            ".btn-primary",
            ".btn-tab-active",
            ".avatar-file-label",
        ):
            block = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\}}", styles, re.DOTALL)
            self.assertIsNotNone(block, selector)
            self.assertIn("box-shadow: none;", block.group("body"))

        self.assertNotIn("box-shadow: var(--mobile-action-shadow);", mobile_styles)
        self.assertNotIn("rgba(109, 40, 217, 0.18)", mobile_styles)

        primary_button_block = re.search(
            r"\.nutrition-primary-button,\s*\.nutrition-secondary-button\s*\{(?P<body>.*?)\}",
            nutrition_styles,
            re.DOTALL,
        )
        self.assertIsNotNone(primary_button_block)
        self.assertIn("box-shadow: none;", primary_button_block.group("body"))


if __name__ == "__main__":
    unittest.main()
