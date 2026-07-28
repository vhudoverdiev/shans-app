from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.database import get_connection
from app.nutrition_catalog import BUILTIN_FOODS


nutrition_bp = Blueprint("nutrition", __name__, url_prefix="/nutrition")

ACTIVITY_LEVELS = {
    "sedentary": (1.2, "Минимальная", "В основном сидячий день"),
    "light": (1.375, "Лёгкая", "1–3 лёгкие тренировки в неделю"),
    "moderate": (1.55, "Средняя", "3–5 тренировок в неделю"),
    "high": (1.725, "Высокая", "6–7 активных дней в неделю"),
    "very_high": (1.9, "Очень высокая", "Тяжёлая физическая работа или интенсивный спорт"),
}

NUTRITION_GOALS = {
    "lose": ("Похудение", 0.85),
    "maintain": ("Поддержание веса", 1.0),
    "gain": ("Набор массы", 1.1),
}

CALORIES_PER_KG = 7700
PROTEIN_TARGETS_BY_GOAL = {
    "lose": 1.6,
    "maintain": 1.4,
    "gain": 1.8,
}

FORMULA_SEXES = {
    "male": "Мужская формула",
    "female": "Женская формула",
}

MEAL_TYPES = {
    "breakfast": "Завтрак",
    "lunch": "Обед",
    "dinner": "Ужин",
    "snack": "Перекус",
}


def init_nutrition_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nutrition_profiles (
                user_id INTEGER PRIMARY KEY,
                formula_sex TEXT NOT NULL,
                age INTEGER NOT NULL,
                height_cm REAL NOT NULL,
                weight_kg REAL NOT NULL,
                target_weight_kg REAL,
                activity_level TEXT NOT NULL,
                goal TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nutrition_foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                catalog_key TEXT UNIQUE,
                user_id INTEGER,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                calories REAL NOT NULL,
                protein REAL NOT NULL,
                fat REAL NOT NULL,
                carbs REAL NOT NULL,
                is_builtin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nutrition_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                food_id INTEGER,
                food_name TEXT NOT NULL,
                grams REAL NOT NULL,
                calories REAL NOT NULL,
                protein REAL NOT NULL,
                fat REAL NOT NULL,
                carbs REAL NOT NULL,
                meal_type TEXT NOT NULL,
                eaten_on TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_nutrition_foods_user_name
            ON nutrition_foods (user_id, name)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_nutrition_entries_user_date
            ON nutrition_entries (user_id, eaten_on DESC, id DESC)
            """
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO nutrition_foods (
                catalog_key,
                user_id,
                name,
                category,
                calories,
                protein,
                fat,
                carbs,
                is_builtin
            ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, 1)
            """,
            BUILTIN_FOODS,
        )
        conn.commit()
    finally:
        conn.close()


def _parse_number(
    raw_value: str,
    field_label: str,
    minimum: float,
    maximum: float,
    *,
    decimals: int = 1,
) -> float:
    normalized = (raw_value or "").strip().replace(",", ".")
    try:
        value = float(normalized)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Поле «{field_label}» должно быть числом.") from error
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(
            f"Поле «{field_label}» должно быть от {minimum:g} до {maximum:g}."
        )
    return round(value, decimals)


def _parse_integer(
    raw_value: str,
    field_label: str,
    minimum: int,
    maximum: int,
) -> int:
    normalized = (raw_value or "").strip()
    try:
        value = int(normalized)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Поле «{field_label}» должно быть целым числом.") from error
    if not minimum <= value <= maximum:
        raise ValueError(
            f"Поле «{field_label}» должно быть от {minimum} до {maximum}."
        )
    return value


def _parse_date(raw_value: str, field_label: str = "Дата") -> str:
    normalized = (raw_value or "").strip()
    try:
        parsed = date.fromisoformat(normalized)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Укажите корректное значение поля «{field_label}».") from error
    if parsed > date.today():
        raise ValueError(f"Поле «{field_label}» не может быть в будущем.")
    return parsed.isoformat()


def _format_date_ru(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return value


def _selected_day_label(selected: date) -> str:
    today = date.today()
    if selected == today:
        return "Сегодня"
    if selected == today - timedelta(days=1):
        return "Вчера"
    return selected.strftime("%d.%m.%Y")


def calculate_calorie_plan(
    formula_sex: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    goal: str,
) -> dict:
    if formula_sex not in FORMULA_SEXES:
        raise ValueError("Выберите формулу расчёта.")
    if activity_level not in ACTIVITY_LEVELS:
        raise ValueError("Выберите уровень активности.")
    if goal not in NUTRITION_GOALS:
        raise ValueError("Выберите цель питания.")
    if not 18 <= int(age) <= 100:
        raise ValueError("Возраст должен быть от 18 до 100 лет.")
    if not 120 <= float(height_cm) <= 230:
        raise ValueError("Рост должен быть от 120 до 230 см.")
    if not 30 <= float(weight_kg) <= 300:
        raise ValueError("Вес должен быть от 30 до 300 кг.")

    sex_offset = 5 if formula_sex == "male" else -161
    bmr = (
        10 * float(weight_kg)
        + 6.25 * float(height_cm)
        - 5 * int(age)
        + sex_offset
    )
    activity_factor = ACTIVITY_LEVELS[activity_level][0]
    goal_factor = NUTRITION_GOALS[goal][1]
    maintenance = int(round((bmr * activity_factor) / 10.0) * 10)
    raw_target = int(round((maintenance * goal_factor) / 10.0) * 10)
    target = max(1200, raw_target)
    bmi = round(float(weight_kg) / ((float(height_cm) / 100) ** 2), 1)

    return {
        "bmr": int(round(bmr)),
        "maintenance_calories": maintenance,
        "target_calories": target,
        "target_was_limited": target != raw_target,
        "bmi": bmi,
        "goal_label": NUTRITION_GOALS[goal][0],
        "activity_label": ACTIVITY_LEVELS[activity_level][1],
    }


def get_nutrition_profile(user_id: int):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT
                user_id,
                formula_sex,
                age,
                height_cm,
                weight_kg,
                target_weight_kg,
                activity_level,
                goal
            FROM nutrition_profiles
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def upsert_nutrition_profile(
    user_id: int,
    formula_sex: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    target_weight_kg: float | None,
    activity_level: str,
    goal: str,
) -> None:
    calculate_calorie_plan(
        formula_sex,
        age,
        height_cm,
        weight_kg,
        activity_level,
        goal,
    )
    if target_weight_kg is not None and not 30 <= target_weight_kg <= 300:
        raise ValueError("Целевой вес должен быть от 30 до 300 кг.")

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO nutrition_profiles (
                user_id,
                formula_sex,
                age,
                height_cm,
                weight_kg,
                target_weight_kg,
                activity_level,
                goal
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                formula_sex = excluded.formula_sex,
                age = excluded.age,
                height_cm = excluded.height_cm,
                weight_kg = excluded.weight_kg,
                target_weight_kg = excluded.target_weight_kg,
                activity_level = excluded.activity_level,
                goal = excluded.goal,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                formula_sex,
                age,
                height_cm,
                weight_kg,
                target_weight_kg,
                activity_level,
                goal,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_food_catalog(user_id: int):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT
                id,
                name,
                category,
                calories,
                protein,
                fat,
                carbs,
                is_builtin
            FROM nutrition_foods
            WHERE is_builtin = 1 OR user_id = ?
            ORDER BY is_builtin DESC, category, name
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def get_food(user_id: int, food_id: int):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, name, category, calories, protein, fat, carbs, is_builtin
            FROM nutrition_foods
            WHERE id = ? AND (is_builtin = 1 OR user_id = ?)
            """,
            (food_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def add_custom_food(
    user_id: int,
    name: str,
    calories: float,
    protein: float,
    fat: float,
    carbs: float,
) -> int:
    normalized_name = (name or "").strip()
    if not normalized_name:
        raise ValueError("Введите название продукта.")
    if len(normalized_name) > 120:
        raise ValueError("Название продукта не должно быть длиннее 120 символов.")
    for label, value, maximum in (
        ("Калории", calories, 900),
        ("Белки", protein, 100),
        ("Жиры", fat, 100),
        ("Углеводы", carbs, 100),
    ):
        if not math.isfinite(float(value)) or not 0 <= float(value) <= maximum:
            raise ValueError(f"Поле «{label}» должно быть от 0 до {maximum}.")

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO nutrition_foods (
                catalog_key,
                user_id,
                name,
                category,
                calories,
                protein,
                fat,
                carbs,
                is_builtin
            ) VALUES (NULL, ?, ?, 'Мои продукты', ?, ?, ?, ?, 0)
            """,
            (
                user_id,
                normalized_name,
                round(float(calories), 1),
                round(float(protein), 1),
                round(float(fat), 1),
                round(float(carbs), 1),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def delete_custom_food(user_id: int, food_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            DELETE FROM nutrition_foods
            WHERE id = ? AND user_id = ? AND is_builtin = 0
            """,
            (food_id, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def add_nutrition_entry(
    user_id: int,
    food_id: int,
    grams: float,
    meal_type: str,
    eaten_on: str,
) -> int:
    food = get_food(user_id, food_id)
    if not food:
        raise ValueError("Выбранный продукт не найден.")
    if not math.isfinite(float(grams)) or not 1 <= float(grams) <= 3000:
        raise ValueError("Количество должно быть от 1 до 3000 г или мл.")
    if meal_type not in MEAL_TYPES:
        raise ValueError("Выберите приём пищи.")
    normalized_date = _parse_date(eaten_on, "Дата приёма пищи")
    multiplier = float(grams) / 100

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO nutrition_entries (
                user_id,
                food_id,
                food_name,
                grams,
                calories,
                protein,
                fat,
                carbs,
                meal_type,
                eaten_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                food["id"],
                food["name"],
                round(float(grams), 1),
                round(float(food["calories"]) * multiplier, 1),
                round(float(food["protein"]) * multiplier, 1),
                round(float(food["fat"]) * multiplier, 1),
                round(float(food["carbs"]) * multiplier, 1),
                meal_type,
                normalized_date,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_nutrition_entries(user_id: int, eaten_on: str):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT
                id,
                food_id,
                food_name,
                grams,
                calories,
                protein,
                fat,
                carbs,
                meal_type,
                eaten_on
            FROM nutrition_entries
            WHERE user_id = ? AND eaten_on = ?
            ORDER BY
                CASE meal_type
                    WHEN 'breakfast' THEN 1
                    WHEN 'lunch' THEN 2
                    WHEN 'dinner' THEN 3
                    ELSE 4
                END,
                id DESC
            """,
            (user_id, eaten_on),
        ).fetchall()
    finally:
        conn.close()


def delete_nutrition_entry(user_id: int, entry_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM nutrition_entries WHERE id = ? AND user_id = ?",
            (entry_id, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def build_daily_summary(entries) -> dict:
    return {
        "calories": round(sum(float(item["calories"]) for item in entries), 1),
        "protein": round(sum(float(item["protein"]) for item in entries), 1),
        "fat": round(sum(float(item["fat"]) for item in entries), 1),
        "carbs": round(sum(float(item["carbs"]) for item in entries), 1),
    }


def _format_weight_delta(value: float, *, signed: bool = False) -> str:
    formatted = f"{value:+.2f}" if signed else f"{abs(value):.2f}"
    return formatted.replace(".", ",")


def build_nutrition_progress_insight(
    profile,
    plan: dict | None,
    summary: dict,
    *,
    is_today: bool,
) -> dict | None:
    if not profile or not plan:
        return None

    day_label = "сегодня" if is_today else "за выбранный день"
    has_food_entries = float(summary["calories"]) > 0
    protein_target = round(float(profile["weight_kg"]) * PROTEIN_TARGETS_BY_GOAL.get(profile["goal"], 1.4), 1)
    protein_missing = max(0, round(protein_target - float(summary["protein"]), 1))

    if has_food_entries:
        calorie_delta = float(plan["maintenance_calories"]) - float(summary["calories"])
        daily_weight_delta = round(calorie_delta / CALORIES_PER_KG, 4)
        weekly_weight_delta = round(daily_weight_delta * 7, 4)
        if daily_weight_delta >= 0:
            day_text = (
                f"За {day_label} вы сбросили "
                f"{_format_weight_delta(daily_weight_delta)} кг."
            )
        else:
            day_text = (
                f"За {day_label} прогноз по весу: "
                f"{_format_weight_delta(daily_weight_delta, signed=True)} кг."
            )
        if weekly_weight_delta >= 0:
            week_text = (
                f"Если каждый день будет примерно так же, за неделю вы сбросите "
                f"{_format_weight_delta(weekly_weight_delta)} кг."
            )
        else:
            week_text = (
                "Если каждый день будет примерно так же, за неделю прогноз по весу: "
                f"{_format_weight_delta(weekly_weight_delta, signed=True)} кг."
            )
    else:
        day_text = f"Добавьте продукты {day_label}, и прогноз веса появится."
        week_text = "Пока нет записей за день, недельный прогноз не рассчитывается."

    protein_message = "Белка на сегодня достаточно."
    if protein_missing > 0:
        if profile["goal"] == "gain":
            protein_message = (
                f"Для набора мышечной массы не хватает примерно {protein_missing:g} г белка. "
                "Доберите творогом, яйцами, рыбой, курицей, йогуртом или бобовыми."
            )
        elif profile["goal"] == "lose":
            protein_message = (
                f"Чтобы худеть и лучше сохранять мышцы, доберите ещё примерно {protein_missing:g} г белка."
            )
        else:
            protein_message = f"До дневного ориентира осталось примерно {protein_missing:g} г белка."

    return {
        "day_text": day_text,
        "week_text": week_text,
        "has_food_entries": has_food_entries,
        "protein_target": protein_target,
        "protein_missing": protein_missing,
        "protein_message": protein_message,
        "is_gain_goal": profile["goal"] == "gain",
    }


def get_nutrition_history(user_id: int, end_date: date, days: int = 14) -> list[dict]:
    start_date = end_date - timedelta(days=days - 1)
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                eaten_on,
                ROUND(SUM(calories), 1) AS calories,
                ROUND(SUM(protein), 1) AS protein,
                ROUND(SUM(fat), 1) AS fat,
                ROUND(SUM(carbs), 1) AS carbs
            FROM nutrition_entries
            WHERE user_id = ? AND eaten_on BETWEEN ? AND ?
            GROUP BY eaten_on
            """,
            (user_id, start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
    finally:
        conn.close()

    totals_by_date = {row["eaten_on"]: row for row in rows}
    history = []
    for offset in range(days):
        current_date = end_date - timedelta(days=offset)
        totals = totals_by_date.get(current_date.isoformat())
        history.append(
            {
                "date": current_date.isoformat(),
                "display_date": _selected_day_label(current_date),
                "calories": float(totals["calories"]) if totals else 0,
                "protein": float(totals["protein"]) if totals else 0,
                "fat": float(totals["fat"]) if totals else 0,
                "carbs": float(totals["carbs"]) if totals else 0,
            }
        )
    return history


def _resolve_food_query(user_id: int, raw_query: str):
    normalized = (raw_query or "").strip()
    match = re.match(r"^(\d+)\s*[—-]", normalized)
    if match:
        return get_food(user_id, int(match.group(1)))

    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, name, category, calories, protein, fat, carbs, is_builtin
            FROM nutrition_foods
            WHERE LOWER(name) = LOWER(?) AND (is_builtin = 1 OR user_id = ?)
            ORDER BY is_builtin DESC
            LIMIT 1
            """,
            (normalized, user_id),
        ).fetchone()
    finally:
        conn.close()


def build_nutrition_recommendations(
    profile,
    plan: dict | None,
    summary: dict,
    *,
    is_today: bool,
) -> list[dict]:
    recommendations = []
    if not profile or not plan:
        recommendations.append(
            {
                "title": "Заполните профиль",
                "text": (
                    "Возраст, рост, вес, активность и цель нужны для ориентировочного "
                    "расчёта дневной калорийности."
                ),
            }
        )
    else:
        goal = profile["goal"]
        if goal == "lose":
            recommendations.append(
                {
                    "title": "Сохраняйте умеренный дефицит",
                    "text": (
                        "Цель рассчитана с небольшим дефицитом. Силовые тренировки "
                        "и обычная ходьба помогают сохранять активность и мышечную массу."
                    ),
                }
            )
        elif goal == "gain":
            recommendations.append(
                {
                    "title": "Набирайте постепенно",
                    "text": (
                        "Цель использует небольшой профицит. Добавляйте калории постепенно "
                        "и отслеживайте силовой прогресс и изменение веса."
                    ),
                }
            )
        else:
            recommendations.append(
                {
                    "title": "Ориентируйтесь на стабильность",
                    "text": (
                        "Смотрите на среднее потребление за несколько дней и динамику веса, "
                        "а не на одно отдельное значение."
                    ),
                }
            )

        if is_today and summary["calories"] > 0:
            ratio = summary["calories"] / max(plan["target_calories"], 1)
            if ratio < 0.7:
                recommendations.append(
                    {
                        "title": "Дневник пока заполнен не полностью",
                        "text": (
                            "Проверьте, внесены ли напитки, перекусы, масла и соусы — "
                            "они часто остаются незаписанными."
                        ),
                    }
                )
            elif ratio > 1.15:
                recommendations.append(
                    {
                        "title": "Сегодня выше ориентира",
                        "text": (
                            "Не компенсируйте это голоданием. Вернитесь к обычному режиму "
                            "и оцените среднее значение за неделю."
                        ),
                    }
                )

    recommendations.extend(
        (
            {
                "title": "Собирайте разнообразный рацион",
                "text": (
                    "Чаще выбирайте овощи, фрукты, цельные крупы и разные источники белка. "
                    "Для продуктов в упаковке используйте значения с этикетки."
                ),
            },
            {
                "title": "Двигайтесь регулярно",
                "text": (
                    "Для взрослых ориентир — 150–300 минут умеренной активности в неделю "
                    "и силовые упражнения на основные группы мышц не менее двух дней."
                ),
            },
        )
    )
    return recommendations


@nutrition_bp.route("")
@login_required
def index():
    user_id = int(current_user.id)
    today = date.today()
    raw_date = (request.args.get("date") or "").strip()
    try:
        selected_date = date.fromisoformat(raw_date) if raw_date else today
    except ValueError:
        selected_date = today
    if selected_date > today:
        selected_date = today

    profile = get_nutrition_profile(user_id)
    plan = None
    if profile:
        plan = calculate_calorie_plan(
            profile["formula_sex"],
            profile["age"],
            profile["height_cm"],
            profile["weight_kg"],
            profile["activity_level"],
            profile["goal"],
        )

    foods = get_food_catalog(user_id)
    entries = get_nutrition_entries(user_id, selected_date.isoformat())
    entries_with_labels = [
        {**dict(item), "meal_label": MEAL_TYPES.get(item["meal_type"], "Приём пищи")}
        for item in entries
    ]
    summary = build_daily_summary(entries)
    target_calories = plan["target_calories"] if plan else None
    remaining_calories = (
        round(target_calories - summary["calories"], 1)
        if target_calories is not None
        else None
    )
    progress_percent = (
        min(100, round(summary["calories"] / max(target_calories, 1) * 100))
        if target_calories is not None
        else 0
    )
    previous_date = selected_date - timedelta(days=1)
    next_date = selected_date + timedelta(days=1)

    return render_template(
        "nutrition.html",
        profile=profile,
        plan=plan,
        foods=foods,
        builtin_food_count=sum(1 for item in foods if item["is_builtin"]),
        custom_foods=[item for item in foods if not item["is_builtin"]],
        entries=entries_with_labels,
        summary=summary,
        history=get_nutrition_history(user_id, selected_date),
        recommendations=build_nutrition_recommendations(
            profile,
            plan,
            summary,
            is_today=selected_date == today,
        ),
        progress_insight=build_nutrition_progress_insight(
            profile,
            plan,
            summary,
            is_today=selected_date == today,
        ),
        selected_date=selected_date.isoformat(),
        selected_date_label=_selected_day_label(selected_date),
        selected_date_display=_format_date_ru(selected_date.isoformat()),
        previous_date=previous_date.isoformat(),
        next_date=next_date.isoformat() if next_date <= today else None,
        today=today.isoformat(),
        target_calories=target_calories,
        remaining_calories=remaining_calories,
        progress_percent=progress_percent,
        activity_levels=ACTIVITY_LEVELS,
        nutrition_goals=NUTRITION_GOALS,
        formula_sexes=FORMULA_SEXES,
        meal_types=MEAL_TYPES,
    )


@nutrition_bp.route("/profile", methods=["POST"])
@login_required
def save_profile():
    try:
        formula_sex = (request.form.get("formula_sex") or "").strip()
        age = _parse_integer(request.form.get("age", ""), "Возраст", 18, 100)
        height_cm = _parse_number(
            request.form.get("height_cm", ""),
            "Рост",
            120,
            230,
        )
        weight_kg = _parse_number(
            request.form.get("weight_kg", ""),
            "Вес",
            30,
            300,
        )
        raw_target_weight = (request.form.get("target_weight_kg") or "").strip()
        target_weight = (
            _parse_number(raw_target_weight, "Целевой вес", 30, 300)
            if raw_target_weight
            else None
        )
        activity_level = (request.form.get("activity_level") or "").strip()
        goal = (request.form.get("goal") or "").strip()
        upsert_nutrition_profile(
            int(current_user.id),
            formula_sex,
            age,
            height_cm,
            weight_kg,
            target_weight,
            activity_level,
            goal,
        )
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("nutrition.index", _anchor="nutrition-profile"))

    flash("Профиль и дневная цель обновлены.", "success")
    return redirect(url_for("nutrition.index", _anchor="nutrition-summary"))


@nutrition_bp.route("/entries", methods=["POST"])
@login_required
def create_entry():
    selected_date = (request.form.get("eaten_on") or date.today().isoformat()).strip()
    try:
        food = _resolve_food_query(
            int(current_user.id),
            request.form.get("food_query", ""),
        )
        if not food:
            raise ValueError("Выберите продукт из списка.")
        grams = _parse_number(
            request.form.get("grams", ""),
            "Количество",
            1,
            3000,
        )
        meal_type = (request.form.get("meal_type") or "").strip()
        normalized_date = _parse_date(selected_date, "Дата приёма пищи")
        add_nutrition_entry(
            int(current_user.id),
            int(food["id"]),
            grams,
            meal_type,
            normalized_date,
        )
    except ValueError as error:
        flash(str(error), "error")
        return redirect(
            url_for("nutrition.index", date=selected_date, _anchor="add-food-entry")
        )

    flash("Продукт добавлен в дневник.", "success")
    return redirect(url_for("nutrition.index", date=normalized_date, _anchor="diary"))


@nutrition_bp.route("/entries/<int:entry_id>/delete", methods=["POST"])
@login_required
def remove_entry(entry_id: int):
    redirect_date = (request.form.get("date") or date.today().isoformat()).strip()
    if not delete_nutrition_entry(int(current_user.id), entry_id):
        abort(404)
    flash("Запись удалена из дневника.", "success")
    return redirect(url_for("nutrition.index", date=redirect_date, _anchor="diary"))


@nutrition_bp.route("/foods", methods=["POST"])
@login_required
def create_custom_food():
    try:
        name = request.form.get("name", "")
        calories = _parse_number(
            request.form.get("calories", ""),
            "Калории",
            0,
            900,
        )
        protein = _parse_number(
            request.form.get("protein", ""),
            "Белки",
            0,
            100,
        )
        fat = _parse_number(request.form.get("fat", ""), "Жиры", 0, 100)
        carbs = _parse_number(
            request.form.get("carbs", ""),
            "Углеводы",
            0,
            100,
        )
        add_custom_food(
            int(current_user.id),
            name,
            calories,
            protein,
            fat,
            carbs,
        )
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("nutrition.index", _anchor="custom-food"))

    flash("Личный продукт добавлен. Теперь его можно выбрать в дневнике.", "success")
    return redirect(url_for("nutrition.index", _anchor="add-food-entry"))


@nutrition_bp.route("/foods/<int:food_id>/delete", methods=["POST"])
@login_required
def remove_custom_food(food_id: int):
    if not delete_custom_food(int(current_user.id), food_id):
        abort(404)
    flash("Личный продукт удалён. Старые записи дневника сохранены.", "success")
    return redirect(url_for("nutrition.index", _anchor="custom-food"))
