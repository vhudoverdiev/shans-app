import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESPONSIVE_STYLESHEETS = (
    PROJECT_ROOT / "app" / "static" / "css" / "style.css",
    PROJECT_ROOT / "app" / "static" / "css" / "mobile.css",
    PROJECT_ROOT / "app" / "static" / "css" / "planner.css",
    PROJECT_ROOT / "app" / "static" / "css" / "learning.css",
    PROJECT_ROOT / "app" / "static" / "css" / "nutrition.css",
    PROJECT_ROOT / "app" / "static" / "css" / "workouts.css",
)


class DesktopLayoutLockTests(unittest.TestCase):
    def test_all_narrow_viewport_breakpoints_require_a_coarse_pointer(self):
        offenders = []

        for stylesheet in RESPONSIVE_STYLESHEETS:
            source = stylesheet.read_text(encoding="utf-8")
            media_queries = re.findall(r"@media\s+([^\{]+)\{", source)
            narrow_queries = [query.strip() for query in media_queries if "max-width:" in query]

            self.assertTrue(
                narrow_queries,
                f"No responsive breakpoints found in {stylesheet.name}",
            )
            offenders.extend(
                f"{stylesheet.name}: {query}"
                for query in narrow_queries
                if "(pointer: coarse)" not in query
            )

        self.assertEqual(
            offenders,
            [],
            "Width-only mobile breakpoints found:\n" + "\n".join(offenders),
        )

    def test_desktop_layout_keeps_the_full_content_canvas(self):
        source = RESPONSIVE_STYLESHEETS[0].read_text(encoding="utf-8")

        desktop_rule = re.search(
            r"@media\s*\(hover:\s*hover\)\s*and\s*\(pointer:\s*fine\)\s*\{"
            r"(?P<body>.*?)\n\}",
            source,
            re.DOTALL,
        )

        self.assertIsNotNone(desktop_rule, "Desktop input-capability rule is missing")
        self.assertRegex(desktop_rule.group("body"), r"min-width:\s*1280px")

    def test_login_and_otp_stages_stay_centered_in_a_narrow_desktop_window(self):
        stylesheet = RESPONSIVE_STYLESHEETS[0].read_text(encoding="utf-8")
        base_template = (
            PROJECT_ROOT / "app" / "templates" / "base.html"
        ).read_text(encoding="utf-8")
        login_template = (
            PROJECT_ROOT / "app" / "templates" / "login.html"
        ).read_text(encoding="utf-8")

        self.assertIn("request.endpoint == 'login'", base_template)
        self.assertIn("login-centered-document", base_template)
        self.assertIn("html:not(.login-centered-document) body", stylesheet)
        self.assertRegex(
            stylesheet,
            r"html\.login-centered-document,\s*"
            r"html\.login-centered-document body\s*\{"
            r"[^}]*overflow:\s*hidden;"
            r"[^}]*overscroll-behavior:\s*none;",
        )
        self.assertRegex(
            stylesheet,
            r"html\.login-centered-document\s+\.app-body\s*\{"
            r"[^}]*height:\s*100dvh;"
            r"[^}]*overflow:\s*hidden;",
        )
        self.assertRegex(
            stylesheet,
            r"html\.login-centered-document\s+\.page-shell\s*\{"
            r"[^}]*height:\s*100dvh;"
            r"[^}]*padding:\s*0;"
            r"[^}]*overflow:\s*hidden;",
        )
        self.assertRegex(
            stylesheet,
            r"html\.login-centered-document\s+\.page-shell\s*\{"
            r"[^}]*max-width:\s*none;"
            r"[^}]*padding:\s*0;",
        )
        self.assertRegex(
            stylesheet,
            r"\.flash-stack\s*\{"
            r"[^}]*position:\s*fixed;"
            r"[^}]*right:\s*24px;"
            r"[^}]*bottom:\s*24px;"
            r"[^}]*width:\s*min\(340px,\s*calc\(100vw - 48px\)\);",
        )
        self.assertRegex(
            stylesheet,
            r"html\.shans-push-inbox-floating-active\s+\.flash-stack\s*\{"
            r"[^}]*right:\s*92px;",
        )
        self.assertRegex(
            stylesheet,
            r"\.flash-message-text\s*\{"
            r"[^}]*min-width:\s*0;"
            r"[^}]*-webkit-line-clamp:\s*3;"
            r"[^}]*overflow-wrap:\s*anywhere;",
        )
        self.assertIn('<div class="flash-stack" role="status" aria-live="polite">', base_template)
        self.assertLess(
            login_template.index('<div class="login-page">'),
            login_template.index('{% if login_stage == "otp" %}'),
        )

    def test_account_tabs_use_the_same_touch_only_mobile_detection(self):
        source = (
            PROJECT_ROOT / "app" / "templates" / "account_settings.html"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'matchMedia("(max-width: 768px) and (pointer: coarse)")',
            source,
        )
        self.assertNotIn('matchMedia("(max-width: 768px)")', source)


if __name__ == "__main__":
    unittest.main()
