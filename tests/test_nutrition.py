import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from flask import Flask
from flask_login import LoginManager, UserMixin
from jinja2 import DictLoader

from config import Config
from app.database import get_connection
from app.nutrition import (
    add_custom_food,
    add_nutrition_entry,
    build_daily_summary,
    build_nutrition_progress_insight,
    calculate_calorie_plan,
    delete_custom_food,
    delete_nutrition_entry,
    get_food_catalog,
    get_nutrition_entries,
    get_nutrition_history,
    get_nutrition_profile,
    init_nutrition_db,
    nutrition_bp,
    upsert_nutrition_profile,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_STYLE_FILE = PROJECT_ROOT / "app" / "static" / "css" / "nutrition.css"
NUTRITION_TEMPLATE = PROJECT_ROOT / "app" / "templates" / "nutrition.html"
NUTRITION_PROFILE_EDIT_TEMPLATE = (
    PROJECT_ROOT / "app" / "templates" / "nutrition_profile_edit.html"
)


class TestUser(UserMixin):
    def __init__(self, user_id):
        self.id = user_id


class NutritionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database_name = Config.DATABASE_NAME
        Config.DATABASE_NAME = str(Path(self.temp_dir.name) / "nutrition-test.db")
        init_nutrition_db()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_dir.cleanup()

    def _create_app(self):
        app = Flask("nutrition-tests")
        app.config.update(SECRET_KEY="test", TESTING=True)
        app.jinja_loader = DictLoader(
            {
                "nutrition.html": (
                    "{{ foods|length }}|{{ entries|length }}|"
                    "{{ summary.calories }}|{{ target_calories or 0 }}"
                ),
                "nutrition_custom_food.html": "custom food page",
                "nutrition_profile_edit.html": (
                    "edit profile page|{{ profile.formula_sex }}|"
                    "{{ profile.age }}|{{ activity_levels|length }}|"
                    "{{ nutrition_goals|length }}|{{ formula_sexes|length }}"
                ),
            }
        )
        login_manager = LoginManager(app)

        @login_manager.user_loader
        def load_user(user_id):
            return TestUser(int(user_id))

        app.register_blueprint(nutrition_bp)
        return app

    def _login(self, client, user_id=1):
        with client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def test_catalog_is_large_diverse_and_seed_is_idempotent(self):
        first_catalog = get_food_catalog(1)
        init_nutrition_db()
        second_catalog = get_food_catalog(1)

        self.assertGreaterEqual(len(first_catalog), 150)
        self.assertGreaterEqual(len({item["category"] for item in first_catalog}), 10)
        self.assertEqual(len(first_catalog), len(second_catalog))
        self.assertTrue(all(item["is_builtin"] for item in first_catalog))

    def test_calorie_plan_uses_profile_and_goal_direction(self):
        maintain = calculate_calorie_plan(
            "male",
            30,
            180,
            80,
            "moderate",
            "maintain",
        )
        lose = calculate_calorie_plan(
            "male",
            30,
            180,
            80,
            "moderate",
            "lose",
        )
        gain = calculate_calorie_plan(
            "male",
            30,
            180,
            80,
            "moderate",
            "gain",
        )

        self.assertEqual(maintain["bmr"], 1780)
        self.assertEqual(maintain["maintenance_calories"], 2760)
        self.assertLess(lose["target_calories"], maintain["target_calories"])
        self.assertGreater(gain["target_calories"], maintain["target_calories"])
        self.assertAlmostEqual(maintain["bmi"], 24.7)

    def test_progress_insight_projects_weight_and_protein_gap(self):
        profile = {
            "weight_kg": 80,
            "goal": "gain",
        }
        plan = {
            "maintenance_calories": 2760,
        }
        summary = {
            "calories": 2000,
            "protein": 90,
        }

        insight = build_nutrition_progress_insight(
            profile,
            plan,
            summary,
            is_today=True,
        )

        self.assertEqual(insight["day_text"], "За сегодня вы сбросили 0,10 кг.")
        self.assertEqual(
            insight["week_text"],
            "Если каждый день будет примерно так же, за неделю вы сбросите 0,69 кг.",
        )
        self.assertEqual(insight["protein_target"], 144)
        self.assertEqual(insight["protein_missing"], 54)
        self.assertIn("Для набора мышечной массы не хватает", insight["protein_message"])

    def test_progress_insight_shows_negative_result_after_overeating(self):
        profile = {
            "weight_kg": 80,
            "goal": "lose",
        }
        plan = {
            "maintenance_calories": 2760,
        }
        summary = {
            "calories": 3530,
            "protein": 90,
        }

        insight = build_nutrition_progress_insight(
            profile,
            plan,
            summary,
            is_today=True,
        )

        self.assertEqual(
            insight["day_text"],
            "Результат похудения сегодня: -0,10 кг.",
        )
        self.assertEqual(
            insight["week_text"],
            "Если каждый день будет примерно так же, результат похудения за неделю: -0,70 кг.",
        )
        self.assertIn("сегодня", insight["day_text"])
        self.assertNotIn("сбросили", insight["day_text"])
        self.assertNotIn("сбросите", insight["week_text"])
        self.assertIn("-0,10 кг", insight["day_text"])

    def test_progress_insight_does_not_predict_weight_loss_without_food_entries(self):
        profile = {
            "weight_kg": 80,
            "goal": "lose",
        }
        plan = {
            "maintenance_calories": 2760,
        }
        summary = {
            "calories": 0,
            "protein": 0,
        }

        insight = build_nutrition_progress_insight(
            profile,
            plan,
            summary,
            is_today=True,
        )

        self.assertFalse(insight["has_food_entries"])
        self.assertEqual(
            insight["day_text"],
            "Добавьте продукты сегодня, и прогноз веса появится.",
        )
        self.assertEqual(
            insight["week_text"],
            "Пока нет записей за день, недельный прогноз не рассчитывается.",
        )
        self.assertNotIn("сбросили", insight["day_text"])
        self.assertNotIn("сбросите", insight["week_text"])

    def test_profile_is_updated_and_isolated_by_user(self):
        upsert_nutrition_profile(
            1,
            "female",
            34,
            168,
            67,
            60,
            "light",
            "lose",
        )
        profile = get_nutrition_profile(1)

        self.assertEqual(profile["goal"], "lose")
        self.assertEqual(profile["target_weight_kg"], 60)
        self.assertIsNone(get_nutrition_profile(2))

        upsert_nutrition_profile(
            1,
            "female",
            34,
            168,
            65.5,
            60,
            "moderate",
            "maintain",
        )
        updated = get_nutrition_profile(1)
        self.assertEqual(updated["weight_kg"], 65.5)
        self.assertEqual(updated["goal"], "maintain")

    def test_custom_food_is_shared_and_only_owner_can_delete_it(self):
        custom_id = add_custom_food(1, "Мой йогурт", 88, 7, 3, 9)
        first_user_food = next(
            item for item in get_food_catalog(1)
            if item["id"] == custom_id
        )
        second_user_food = next(
            item for item in get_food_catalog(2)
            if item["id"] == custom_id
        )

        self.assertEqual(first_user_food["name"], "Мой йогурт")
        self.assertEqual(second_user_food["name"], "Мой йогурт")
        self.assertEqual(first_user_food["can_delete"], 1)
        self.assertEqual(second_user_food["can_delete"], 0)
        self.assertFalse(delete_custom_food(2, custom_id))

        entry_id = add_nutrition_entry(
            1,
            custom_id,
            150,
            "breakfast",
            date.today().isoformat(),
        )
        second_entry_id = add_nutrition_entry(
            2,
            custom_id,
            100,
            "snack",
            date.today().isoformat(),
        )
        self.assertTrue(delete_custom_food(1, custom_id))

        entries = get_nutrition_entries(1, date.today().isoformat())
        self.assertEqual(entries[0]["id"], entry_id)
        self.assertEqual(entries[0]["food_name"], "Мой йогурт")
        self.assertAlmostEqual(entries[0]["calories"], 132)
        second_entries = get_nutrition_entries(2, date.today().isoformat())
        self.assertEqual(second_entries[0]["id"], second_entry_id)
        self.assertEqual(second_entries[0]["food_name"], "Мой йогурт")
        self.assertAlmostEqual(second_entries[0]["calories"], 88)

    def test_custom_food_catalog_deduplicates_repeated_additions(self):
        first_id = add_custom_food(1, "  Мой творог  ", 120, 18, 5, 3)
        second_id = add_custom_food(1, "мой   творог", 130, 19, 6, 4)

        self.assertEqual(second_id, first_id)
        matches = [
            item for item in get_food_catalog(1)
            if item["name"].strip().casefold() == "мой творог"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["calories"], 120)

    def test_food_catalog_hides_existing_duplicate_rows_from_legacy_data(self):
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO nutrition_foods (
                    catalog_key, user_id, name, category, calories,
                    protein, fat, carbs, is_builtin
                ) VALUES (NULL, 1, 'Дубликат', 'Мои продукты', 100, 10, 1, 2, 0)
                """
            )
            conn.execute(
                """
                INSERT INTO nutrition_foods (
                    catalog_key, user_id, name, category, calories,
                    protein, fat, carbs, is_builtin
                ) VALUES (NULL, 1, '  дубликат  ', 'Мои продукты', 200, 20, 2, 4, 0)
                """
            )
            conn.commit()
        finally:
            conn.close()

        matches = [
            item for item in get_food_catalog(1)
            if item["name"].strip().casefold() == "дубликат"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["calories"], 100)

    def test_diary_scales_macros_and_history_includes_empty_days(self):
        food = next(
            item for item in get_food_catalog(1)
            if item["name"] == "Куриная грудка, готовая"
        )
        today = date.today()
        yesterday = today - timedelta(days=1)
        entry_id = add_nutrition_entry(
            1,
            food["id"],
            200,
            "lunch",
            yesterday.isoformat(),
        )

        entries = get_nutrition_entries(1, yesterday.isoformat())
        summary = build_daily_summary(entries)
        history = get_nutrition_history(1, today, days=3)

        self.assertAlmostEqual(summary["calories"], 330)
        self.assertAlmostEqual(summary["protein"], 62)
        self.assertEqual(history[0]["date"], today.isoformat())
        self.assertEqual(history[0]["calories"], 0)
        self.assertEqual(history[1]["date"], yesterday.isoformat())
        self.assertEqual(history[1]["calories"], 330)
        self.assertTrue(delete_nutrition_entry(1, entry_id))
        self.assertFalse(delete_nutrition_entry(2, entry_id))

    def test_routes_save_profile_and_diary_entry(self):
        app = self._create_app()
        client = app.test_client()
        self._login(client)

        response = client.get("/nutrition")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_data(as_text=True).startswith("175|0|0"))

        response = client.post(
            "/nutrition/profile",
            data={
                "formula_sex": "male",
                "age": "30",
                "height_cm": "180",
                "weight_kg": "80",
                "target_weight_kg": "75",
                "activity_level": "moderate",
                "goal": "lose",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(get_nutrition_profile(1))

        food = get_food_catalog(1)[0]
        response = client.post(
            "/nutrition/entries",
            data={
                "food_query": f"{food['id']} — {food['name']}",
                "grams": "125",
                "meal_type": "dinner",
                "eaten_on": date.today().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            len(get_nutrition_entries(1, date.today().isoformat())),
            1,
        )

    def test_routes_accept_display_food_label_with_nutrients(self):
        app = self._create_app()
        client = app.test_client()
        self._login(client)

        food = next(item for item in get_food_catalog(1) if item["name"] == "Борщ")
        response = client.post(
            "/nutrition/entries",
            data={
                "food_query": "Борщ (49ккал)(б-1.8,ж-2.2,у-5.4)",
                "grams": "100",
                "meal_type": "lunch",
                "eaten_on": date.today().isoformat(),
            },
        )

        self.assertEqual(response.status_code, 302)
        entries = get_nutrition_entries(1, date.today().isoformat())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["food_name"], food["name"])
        self.assertEqual(entries[0]["calories"], food["calories"])

    def test_invalid_profile_and_future_entry_do_not_write(self):
        app = self._create_app()
        client = app.test_client()
        self._login(client)

        response = client.post(
            "/nutrition/profile",
            data={
                "formula_sex": "male",
                "age": "12",
                "height_cm": "180",
                "weight_kg": "80",
                "activity_level": "moderate",
                "goal": "maintain",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(get_nutrition_profile(1))

        food = get_food_catalog(1)[0]
        response = client.post(
            "/nutrition/entries",
            data={
                "food_query": f"{food['id']} — {food['name']}",
                "grams": "100",
                "meal_type": "lunch",
                "eaten_on": (date.today() + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            get_nutrition_entries(
                1,
                (date.today() + timedelta(days=1)).isoformat(),
            ),
            [],
        )

    def test_profile_edit_page_is_separate_and_updates_profile(self):
        app = self._create_app()
        client = app.test_client()
        self._login(client)

        response = client.get("/nutrition/profile/edit")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/nutrition#nutrition-profile")

        upsert_nutrition_profile(
            1,
            "male",
            30,
            180,
            80,
            75,
            "moderate",
            "lose",
        )

        response = client.get("/nutrition/profile/edit")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "edit profile page|male|30|5|3|2")

        response = client.post(
            "/nutrition/profile",
            data={
                "profile_source": "edit",
                "formula_sex": "male",
                "age": "12",
                "height_cm": "180",
                "weight_kg": "80",
                "activity_level": "moderate",
                "goal": "lose",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/nutrition/profile/edit")
        self.assertEqual(get_nutrition_profile(1)["age"], 30)

        response = client.post(
            "/nutrition/profile",
            data={
                "profile_source": "edit",
                "formula_sex": "female",
                "age": "34",
                "height_cm": "168",
                "weight_kg": "65",
                "target_weight_kg": "60",
                "activity_level": "light",
                "goal": "maintain",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/nutrition#nutrition-profile")

        profile = get_nutrition_profile(1)
        self.assertEqual(profile["formula_sex"], "female")
        self.assertEqual(profile["age"], 34)
        self.assertEqual(profile["goal"], "maintain")

    def test_templates_expose_nutrition_through_development_navigation(self):
        hub = (
            PROJECT_ROOT / "app" / "templates" / "study_hub.html"
        ).read_text(encoding="utf-8")
        sport_hub = (
            PROJECT_ROOT / "app" / "templates" / "sport_hub.html"
        ).read_text(encoding="utf-8")
        base = (
            PROJECT_ROOT / "app" / "templates" / "base.html"
        ).read_text(encoding="utf-8")
        template = (
            PROJECT_ROOT / "app" / "templates" / "nutrition.html"
        ).read_text(encoding="utf-8")
        custom_template = (
            PROJECT_ROOT / "app" / "templates" / "nutrition_custom_food.html"
        ).read_text(encoding="utf-8")
        profile_edit_template = NUTRITION_PROFILE_EDIT_TEMPLATE.read_text(
            encoding="utf-8"
        )

        self.assertNotIn("url_for('nutrition.index')", hub)
        self.assertIn("url_for('nutrition.index')", sport_hub)
        self.assertIn(">Питание<", sport_hub)
        self.assertIn("request.endpoint.startswith('nutrition.')", base)
        self.assertIn("url_for('sport_hub')", base)
        self.assertIn("База продуктов", template)
        catalog_block = template.split(
            '<section class="nutrition-card nutrition-catalog-card">',
            1,
        )[1]
        self.assertNotIn("Поиск продукта", catalog_block)
        self.assertIn('id="nutrition-catalog-search"', catalog_block)
        self.assertIn(
            "{{ food.name }} ({{ food.calories|round(0)|int }}ккал)(б-{{ food.protein|round(1) }},ж-{{ food.fat|round(1) }},у-{{ food.carbs|round(1) }})",
            template,
        )
        self.assertNotIn("{{ food.id }} — {{ food.name }}", template)
        self.assertIn("Добавить продукт вручную", template)
        quick_entry_block = template.split('id="add-food-entry"', 1)[1].split(
            'id="nutrition-profile"',
            1,
        )[0]

        self.assertIn(
            'class="nutrition-card nutrition-quick-entry-card" id="add-food-entry"',
            template,
        )
        self.assertNotIn("nutrition-foldout-panel", template)
        self.assertNotIn("nutrition-foldout-button", template)
        self.assertNotIn("<details", quick_entry_block)
        self.assertNotIn("<summary", quick_entry_block)
        self.assertIn(">Добавить</button>", quick_entry_block)
        self.assertNotIn("Добавить в", quick_entry_block)
        profile_card_block = template.split(
            '<section class="nutrition-card" id="nutrition-profile">',
            1,
        )[1].split(
            'id="diary"',
            1,
        )[0]
        self.assertIn("url_for('nutrition.edit_profile')", profile_card_block)
        self.assertIn("nutrition-profile-edit-button", profile_card_block)
        self.assertIn(">Изменить данные</a>", profile_card_block)
        self.assertNotIn("nutrition-profile-details", profile_card_block)
        self.assertNotIn("<details", profile_card_block)
        self.assertNotIn("<summary", profile_card_block)
        self.assertNotIn('name="formula_sex"', profile_card_block)
        self.assertIn("url_for('nutrition.new_custom_food')", template)
        self.assertIn('class="nutrition-icon-button"', template)
        self.assertIn("food.can_delete", template)
        self.assertIn("добавлен пользователем", template)
        self.assertNotIn("мой продукт", template)
        self.assertNotIn("data-open-custom-food", template)
        self.assertNotIn('id="custom-food" hidden', template)
        self.assertNotIn("По этикетке", template)
        self.assertIn('class="nutrition-back-link nutrition-edit-back-link"', custom_template)
        self.assertIn("← Назад к питанию", custom_template)
        self.assertIn("url_for('nutrition.create_custom_food')", custom_template)
        self.assertIn("Сохранить продукт", custom_template)
        self.assertIn('class="nutrition-back-link nutrition-edit-back-link"', profile_edit_template)
        self.assertIn("← Назад к питанию", profile_edit_template)
        self.assertIn("url_for('nutrition.save_profile')", profile_edit_template)
        self.assertIn('name="profile_source" value="edit"', profile_edit_template)
        self.assertIn("Сохранить расчёт", profile_edit_template)
        self.assertIn("nutrition-profile-edit-card", profile_edit_template)
        self.assertNotIn("Полезные ориентиры", template)
        self.assertNotIn("Рекомендации", template)
        self.assertNotIn("nutrition-recommendations", template)
        self.assertNotIn("recommendations", template)
        self.assertNotIn(">Тренировки →</a>", template)
        self.assertNotIn("Открыть тренировки", template)
        self.assertIn("Последние 14 дней", template)
        self.assertNotIn("<aside class=\"nutrition-disclaimer\">", template)
        self.assertNotIn("<strong>Важно</strong>", template)
        self.assertIn("Прогноз веса", template)
        self.assertIn("progress_insight.day_text", template)
        self.assertIn("progress_insight.protein_message", template)
        self.assertNotIn("autofocus", template)

    def test_nutrition_pages_keep_back_button_visible_on_mobile(self):
        template = NUTRITION_TEMPLATE.read_text(encoding="utf-8")
        styles = NUTRITION_STYLE_FILE.read_text(encoding="utf-8")
        mobile_block = styles.split("@media (max-width: 900px) and (pointer: coarse)", 1)[1].split(
            "@media (hover: hover) and (pointer: fine)",
            1,
        )[0]

        self.assertIn("url_for('sport_hub')", template)
        self.assertIn('class="nutrition-back-link">← Спорт</a>', template)
        self.assertNotIn(".nutrition-back-link {\n        display: none;", mobile_block)
        self.assertIn(".nutrition-custom-food-page .nutrition-back-link", mobile_block)
        self.assertIn(".nutrition-profile-edit-page .nutrition-back-link", mobile_block)
        edit_back_rule = mobile_block.split(".nutrition-custom-food-page .nutrition-back-link,", 1)[1].split(
            "}",
            1,
        )[0]
        self.assertIn("display: inline-flex;", edit_back_rule)
        self.assertNotIn("width: 100%;", edit_back_rule)
        self.assertNotIn("justify-content: center;", edit_back_rule)

    def test_nutrition_edit_back_buttons_match_learning_back_link_style(self):
        styles = NUTRITION_STYLE_FILE.read_text(encoding="utf-8")

        self.assertIn(".nutrition-edit-back-link {", styles)
        self.assertIn("color: #6d28d9;", styles)
        self.assertIn(".nutrition-edit-back-link:hover", styles)
        self.assertIn("color: #4c1d95;", styles)
        self.assertIn(".nutrition-edit-back-link {\n        color: var(--nutrition-blue);", styles)

    def test_custom_food_page_is_separate_from_catalog(self):
        app = self._create_app()
        client = app.test_client()
        self._login(client)

        response = client.get("/nutrition/foods/new")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "custom food page")

        response = client.post(
            "/nutrition/foods",
            data={
                "name": "",
                "calories": "90",
                "protein": "5",
                "fat": "2",
                "carbs": "12",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/nutrition/foods/new")

    def test_nutrition_desktop_theme_uses_neutral_surface(self):
        styles = NUTRITION_STYLE_FILE.read_text(encoding="utf-8")
        desktop_theme = styles.split(
            "/* Desktop nutrition uses neutral cards;",
            1,
        )[1]

        self.assertIn("@media (hover: hover) and (pointer: fine)", desktop_theme)
        self.assertIn(".nutrition-hero", desktop_theme)
        self.assertIn("background: #ffffff;", desktop_theme)
        self.assertIn("border-color: #e5eaf2;", desktop_theme)
        self.assertIn(".nutrition-onboarding", desktop_theme)
        self.assertIn(".nutrition-card", desktop_theme)
        self.assertNotIn(
            "linear-gradient(135deg, #2563eb 0%, #1d4ed8 55%, #3b82f6 100%)",
            desktop_theme,
        )
        for old_accent in (
            "#047857",
            "#0f9f83",
            "#14b8a6",
            "#059669",
            "#10b981",
            "#6d28d9",
            "#7c3aed",
            "#8b5cf6",
            "rgba(5, 150, 105",
            "rgba(139, 92, 246",
        ):
            self.assertNotIn(old_accent, desktop_theme)

    def test_nutrition_quick_entry_is_always_expanded(self):
        styles = NUTRITION_STYLE_FILE.read_text(encoding="utf-8")
        script = (
            PROJECT_ROOT / "app" / "static" / "js" / "nutrition.js"
        ).read_text(encoding="utf-8")

        self.assertIn(".nutrition-profile-edit-button", styles)
        self.assertIn(".nutrition-profile-edit-card", styles)
        self.assertIn(".nutrition-profile-edit-card .nutrition-profile-form", styles)
        self.assertNotIn(".nutrition-profile-details", styles)
        self.assertNotIn(".nutrition-profile-save-button", styles)
        self.assertIn(".nutrition-quick-entry-card .nutrition-entry-form", styles)
        self.assertNotIn(".nutrition-foldout-panel", styles)
        self.assertNotIn(".nutrition-foldout-button", styles)
        self.assertIn(".nutrition-icon-button", styles)
        self.assertIn("white-space: nowrap;", styles)
        self.assertIn("text-decoration: none;", styles)
        self.assertIn(".nutrition-custom-food-card", styles)
        self.assertIn(".nutrition-food-row[hidden]", styles)
        self.assertRegex(
            styles,
            r"\.nutrition-food-row\[hidden\]\s*\{\s*display:\s*none;",
        )
        self.assertNotIn(".nutrition-recommendation-grid", styles)
        self.assertNotIn(".nutrition-disclaimer", styles)
        self.assertNotIn(".nutrition-text-link", styles)
        self.assertIn('search.addEventListener("input", applyFilter);', script)
        self.assertIn('search.addEventListener("search", applyFilter);', script)
        self.assertNotIn("entryCard.open = true;", script)
        self.assertNotIn("customCard.hidden", script)
        self.assertNotIn('trigger.setAttribute("aria-expanded"', script)

    def test_database_uses_snapshot_nutrients_for_diary_entries(self):
        food = get_food_catalog(1)[0]
        add_nutrition_entry(
            1,
            food["id"],
            100,
            "snack",
            date.today().isoformat(),
        )
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT food_name, calories, protein, fat, carbs "
                "FROM nutrition_entries WHERE user_id = 1"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(row["food_name"], food["name"])
        self.assertEqual(row["calories"], food["calories"])
        self.assertEqual(row["protein"], food["protein"])
        self.assertEqual(row["fat"], food["fat"])
        self.assertEqual(row["carbs"], food["carbs"])


if __name__ == "__main__":
    unittest.main()
