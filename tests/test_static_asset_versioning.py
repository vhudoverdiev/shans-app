import tempfile
import unittest
from pathlib import Path

from app import build_static_asset_version


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
ACCOUNT_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "account_settings.html"
PLANNER_STYLESHEET = PROJECT_ROOT / "app" / "static" / "css" / "planner.css"


class StaticAssetVersioningTests(unittest.TestCase):
    def test_asset_version_changes_when_styles_change(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            static_root = Path(temp_directory)
            css_directory = static_root / "css"
            css_directory.mkdir()
            stylesheet = css_directory / "planner.css"
            stylesheet.write_text(".switch { color: blue; }", encoding="utf-8")

            first_version = build_static_asset_version(static_root)
            stylesheet.write_text(".switch { color: red; }", encoding="utf-8")
            second_version = build_static_asset_version(static_root)

        self.assertEqual(len(first_version), 12)
        self.assertNotEqual(first_version, second_version)

    def test_asset_version_changes_when_favicon_changes(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            static_root = Path(temp_directory)
            favicon = static_root / "favicon.png"
            favicon.write_bytes(b"first-favicon")

            first_version = build_static_asset_version(static_root)
            favicon.write_bytes(b"second-favicon")
            second_version = build_static_asset_version(static_root)

        self.assertNotEqual(first_version, second_version)

    def test_templates_append_asset_version_to_css_and_javascript(self):
        base_template = BASE_TEMPLATE.read_text(encoding="utf-8")
        account_template = ACCOUNT_TEMPLATE.read_text(encoding="utf-8")

        for filename in (
            "css/style.css",
            "css/mobile.css",
            "css/planner.css",
            "css/learning.css",
            "js/intro-loader.js",
            "js/offline-support.js",
            "js/push-inbox.js",
        ):
            self.assertIn(
                f"filename='{filename}', v=static_asset_version",
                base_template,
            )
        self.assertIn("filename='logo.png', v=static_asset_version", base_template)
        self.assertIn("filename='favicon.png', v=static_asset_version", base_template)
        self.assertIn(
            "filename='js/push-notifications.js', v=config.get('STATIC_ASSET_VERSION', 'dev')",
            account_template,
        )

    def test_calendar_switch_has_complete_visual_styles(self):
        stylesheet = PLANNER_STYLESHEET.read_text(encoding="utf-8")

        self.assertIn(".planner-calendar-switch{", stylesheet)
        self.assertIn(".planner-calendar-switch-link{", stylesheet)
        self.assertIn(".planner-calendar-switch-link-active{", stylesheet)
        self.assertIn("grid-template-columns:repeat(2,minmax(0,1fr));", stylesheet)
        self.assertIn("text-decoration:none;", stylesheet)


if __name__ == "__main__":
    unittest.main()
