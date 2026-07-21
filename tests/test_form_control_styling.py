import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
DATE_TYPES = {"date", "time", "month", "datetime-local"}


class FormControlStylingTests(unittest.TestCase):
    def test_every_date_control_and_select_uses_shared_form_style(self):
        uncovered_controls = []

        for template_path in TEMPLATES_DIR.glob("*.html"):
            template = template_path.read_text(encoding="utf-8")
            for tag in re.findall(r"<(?:input|select)\b[^>]*>", template, flags=re.IGNORECASE):
                is_select = tag.lower().startswith("<select")
                type_match = re.search(r'\btype=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
                is_date_control = bool(
                    type_match and type_match.group(1).lower() in DATE_TYPES
                )
                if not is_select and not is_date_control:
                    continue

                class_match = re.search(r'\bclass=["\']([^"\']*)["\']', tag, flags=re.IGNORECASE)
                classes = class_match.group(1).split() if class_match else []
                if "form-input" not in classes:
                    uncovered_controls.append(f"{template_path.name}: {tag}")

        self.assertEqual(uncovered_controls, [])

    def test_shared_css_styles_selects_and_native_date_pickers(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")

        self.assertIn("select.form-input {", stylesheet)
        self.assertIn('input[type="date"]', stylesheet)
        self.assertIn('input[type="time"]', stylesheet)
        self.assertIn('input[type="month"]', stylesheet)
        self.assertIn('input[type="datetime-local"]', stylesheet)
        self.assertIn("::-webkit-calendar-picker-indicator", stylesheet)
        self.assertIn("appearance: none;", stylesheet)


if __name__ == "__main__":
    unittest.main()
