import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "base.html"
AJAX_FORMS_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "ajax-forms.js"
WORKOUT_DETAIL_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "workout_plan_detail.html"
WORKOUTS_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "workouts.html"
WORKOUTS_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "workouts.js"
NUTRITION_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "nutrition.html"
NUTRITION_CUSTOM_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "nutrition_custom_food.html"
NUTRITION_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "nutrition.js"


class AjaxFormTests(unittest.TestCase):
    def test_base_loads_shared_ajax_form_handler(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("js/ajax-forms.js", template)
        self.assertIn("defer", template)

    def test_ajax_form_handler_replaces_server_rendered_fragments(self):
        script = AJAX_FORMS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('form[data-ajax-submit]', script)
        self.assertIn("window.fetch", script)
        self.assertIn("new FormData(form)", script)
        self.assertIn('formData.append("_csrf_token"', script)
        self.assertIn('"X-CSRFToken"', script)
        self.assertIn("DOMParser", script)
        self.assertIn("replaceFragments", script)
        self.assertIn("showFlashStack", script)
        self.assertIn("shans:ajax-updated", script)
        self.assertIn("hasErrorFlash", script)
        self.assertIn("form.submit()", script)

    def test_csrf_tokens_are_added_after_ajax_fragment_updates(self):
        template = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("function injectCsrfTokens(scope)", template)
        self.assertIn("injectCsrfTokens(document);", template)
        self.assertIn('document.addEventListener("shans:ajax-updated"', template)
        self.assertIn("input[name='_csrf_token']", template)

    def test_workout_add_forms_update_without_page_reload(self):
        detail = WORKOUT_DETAIL_TEMPLATE.read_text(encoding="utf-8")
        overview = WORKOUTS_TEMPLATE.read_text(encoding="utf-8")
        script = WORKOUTS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("url_for('workouts.create_result')", detail)
        self.assertIn("data-ajax-submit", detail)
        self.assertIn('data-ajax-update=".workout-plan-diary"', detail)
        self.assertIn('data-ajax-reset="true"', detail)
        self.assertIn("url_for('workouts.remove_result'", detail)
        self.assertIn('data-ajax-update=".workout-plan-diary"', detail)
        self.assertIn("url_for('workouts.save_weight')", overview)
        self.assertIn('data-ajax-update=".workouts-summary, .workouts-weight-section"', overview)
        self.assertIn("window.ShansWorkouts.renderWeightChart", script)
        self.assertIn('document.addEventListener("shans:ajax-updated"', script)

    def test_nutrition_add_forms_update_without_page_reload(self):
        template = NUTRITION_TEMPLATE.read_text(encoding="utf-8")
        custom_template = NUTRITION_CUSTOM_TEMPLATE.read_text(encoding="utf-8")
        script = NUTRITION_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("url_for('nutrition.create_entry')", template)
        self.assertIn('data-ajax-update="#nutrition-summary, #diary, .nutrition-history"', template)
        self.assertIn("url_for('nutrition.new_custom_food')", template)
        self.assertNotIn("data-open-custom-food", template)
        self.assertNotIn("#custom-food", template)
        self.assertIn("url_for('nutrition.create_custom_food')", custom_template)
        self.assertNotIn("data-ajax-submit", custom_template)
        self.assertIn("data-ajax-reset=\"true\"", template)
        self.assertIn("initializeNutritionPage", script)
        self.assertIn('document.addEventListener("shans:ajax-updated"', script)
        self.assertIn("nutritionSearchReady", script)
        self.assertIn("nutritionSelectReady", script)
        self.assertNotIn("nutritionCustomReady", script)


if __name__ == "__main__":
    unittest.main()
