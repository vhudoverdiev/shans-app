import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = PROJECT_ROOT / "app" / "templates"
STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
MOBILE_STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "mobile.css"


class MobileAppNavigationTests(unittest.TestCase):
    def test_desktop_dashboard_keeps_original_six_cards(self):
        source = (TEMPLATES / "index.html").read_text(encoding="utf-8")
        desktop_grid = re.search(
            r'<div class="dashboard-grid dashboard-grid-desktop">(?P<body>.*?)'
            r'<div class="dashboard-grid dashboard-grid-mobile',
            source,
            re.DOTALL,
        )

        self.assertIsNotNone(desktop_grid)
        body = desktop_grid.group("body")
        self.assertEqual(body.count('class="dashboard-card"'), 6)
        for endpoint in (
            "budget",
            "car",
            "planner.schedule",
            "shootings",
            "planner.photo_projects",
            "scenarios",
        ):
            self.assertIn(f"url_for('{endpoint}')", body)

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
            3,
        )
        self.assertIn("url_for('planner.schedule')", mobile_grid)
        self.assertIn("url_for('shootings_hub')", mobile_grid)
        self.assertIn("url_for('reports_hub')", mobile_grid)

    def test_mobile_hubs_group_existing_sections(self):
        shootings = (TEMPLATES / "shootings_hub.html").read_text(encoding="utf-8")
        reports = (TEMPLATES / "reports_hub.html").read_text(encoding="utf-8")
        routes = (PROJECT_ROOT / "app" / "routes.py").read_text(encoding="utf-8")

        for endpoint in ("planner.photo_projects", "shootings", "scenarios"):
            self.assertIn(f"url_for('{endpoint}')", shootings)
        for endpoint in ("budget", "car"):
            self.assertIn(f"url_for('{endpoint}')", reports)
        self.assertIn('@app.route("/shootings-hub")', routes)
        self.assertIn('@app.route("/reports")', routes)

    def test_bottom_navigation_replaces_mobile_avatar_menu(self):
        base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
        mobile_styles = MOBILE_STYLE_FILE.read_text(encoding="utf-8")

        self.assertNotIn("mobile-fab", base)
        self.assertNotIn("mobile-fab", mobile_styles)
        self.assertEqual(base.count('class="app-bottom-nav-link '), 4)
        for label in ("Главная", "График", "Съёмки", "Аккаунт"):
            self.assertIn(f"<span>{label}</span>", base)
        self.assertIn(
            "@media (max-width: 900px) and (pointer: coarse)",
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
            r"\.account-logout-btn\s*\{\s*display:\s*none;",
        )
        self.assertRegex(
            mobile_styles,
            r"\.dashboard-grid-desktop\s*\{\s*display:\s*none\s*!important;",
        )
        self.assertRegex(
            mobile_styles,
            r"\.account-logout-btn\s*\{[^}]*display:\s*inline-flex;",
        )
        self.assertIn("url_for('logout')", account)
        self.assertIn('id="account-logout-btn"', account)


if __name__ == "__main__":
    unittest.main()
