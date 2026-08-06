import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
BASE_TEMPLATE = TEMPLATES_DIR / "base.html"
STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "style.css"
FORM_CONTROLS_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "form-controls.js"
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
        self.assertIn("width: min(286px, calc(100vw - 24px));", stylesheet)
        self.assertIn("width: min(304px, calc(100vw - 20px));", stylesheet)
        self.assertRegex(
            stylesheet,
            r"\.custom-select-button\s*\{[^}]*font-weight:\s*400;",
        )
        self.assertRegex(
            stylesheet,
            r"\.custom-select-option\s*\{[^}]*font-weight:\s*400;",
        )

    def test_base_template_loads_custom_form_control_enhancement(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("js/form-controls.js", template)
        self.assertIn("defer", template)

    def test_custom_form_control_assets_cover_dropdowns_and_calendars(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")
        script = FORM_CONTROLS_SCRIPT.read_text(encoding="utf-8")

        for selector in (
            ".custom-select-button",
            ".custom-select-menu",
            ".custom-select-option",
            ".custom-date-button",
            ".custom-date-value",
            ".custom-date-icon",
            ".custom-date-panel",
            ".custom-date-calendar",
            ".custom-date-day-selected",
            ".custom-month-grid",
            ".custom-month-option-selected",
        ):
            self.assertIn(selector, stylesheet)

        self.assertIn("select.form-input:not([multiple]):not([data-native-control])", script)
        self.assertIn("input.form-input[type='date']:not([data-native-control])", script)
        self.assertIn("input.form-input[type='datetime-local']:not([data-native-control])", script)
        self.assertIn("input.form-input[type='month']:not([data-native-control])", script)
        self.assertIn('!panel.classList.contains("custom-date-panel")', script)
        self.assertIn('panel.style.minWidth = shouldMatchAnchorWidth ? rect.width + "px" : "";', script)
        self.assertIn("dispatchNativeChange", script)
        self.assertIn("MutationObserver", script)

    def test_custom_select_recovers_when_ajax_removes_floating_menu(self):
        script = FORM_CONTROLS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function resetEnhancedSelect(select)", script)
        self.assertIn("function selectNeedsRebuild(select)", script)
        self.assertIn('select.dataset.customControlMenuId = menu.id;', script)
        self.assertIn('!document.getElementById(menuId)', script)
        self.assertIn('document.addEventListener("shans:ajax-updated"', script)
        self.assertIn("initFormControls(document);", script)

    def test_custom_date_control_uses_single_visible_picker_surface(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")
        script = FORM_CONTROLS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('input.classList.add("custom-date-input", "custom-native-control")', script)
        self.assertIn('input.classList.add("custom-date-input", "custom-month-input", "custom-native-control")', script)
        self.assertIn("input.tabIndex = -1;", script)
        self.assertNotIn('input.addEventListener("focus", open);', script)
        self.assertIn('buttonText.className = "custom-date-value";', script)
        self.assertIn('buttonIcon.className = "custom-date-icon";', script)
        self.assertIn("button.focus();", script)
        self.assertIn("formatDateButtonText", script)
        self.assertIn("formatMonthButtonText", script)

        self.assertRegex(
            stylesheet,
            r"\.custom-date-button\s*\{[^}]*display:\s*flex;[^}]*align-items:\s*center;",
        )
        self.assertRegex(
            stylesheet,
            r"\.custom-date-button\s*\{[^}]*line-height:\s*1;",
        )
        self.assertIn(".custom-control-invalid .custom-date-button", stylesheet)

    def test_custom_date_icon_has_no_top_binding_dots(self):
        stylesheet = STYLE_FILE.read_text(encoding="utf-8")
        icon_block = stylesheet.split(".custom-date-icon {", 1)[1].split(
            "}",
            1,
        )[0]
        before_block = stylesheet.rsplit(".custom-date-icon::before {", 1)[1].split(
            "}",
            1,
        )[0]

        self.assertIn("border: 2px solid currentColor;", icon_block)
        self.assertIn("height: 2px;", before_block)
        self.assertNotIn(".custom-date-icon::after", stylesheet)
        self.assertNotIn("box-shadow: 7px 0 0 currentColor;", stylesheet)


if __name__ == "__main__":
    unittest.main()
