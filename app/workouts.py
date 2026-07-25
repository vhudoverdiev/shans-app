from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.database import get_connection


workouts_bp = Blueprint("workouts", __name__, url_prefix="/workouts")

DEFAULT_WORKOUT_PLANS = (
    (
        "Тренировка 1",
        "Грудь, плечи и трицепс. Начните с разминки, затем выполните жимовые "
        "упражнения и завершите тренировку лёгкой растяжкой.",
    ),
    (
        "Тренировка 2",
        "Спина и бицепс. Сосредоточьтесь на контролируемой технике в тягах, "
        "не перегружайте поясницу и фиксируйте рабочие веса.",
    ),
    (
        "Тренировка 3",
        "Ноги и мышцы кора. После суставной разминки выполните приседания или "
        "их безопасную альтернативу, затем упражнения на заднюю поверхность бедра и пресс.",
    ),
)


def init_workouts_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workout_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workout_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                workout_plan_id INTEGER NOT NULL,
                exercise TEXT NOT NULL,
                result TEXT NOT NULL,
                performed_on TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weight_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                measured_on TEXT NOT NULL,
                weight_kg REAL NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, measured_on)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_workout_results_user_date
            ON workout_results (user_id, performed_on DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_weight_entries_user_date
            ON weight_entries (user_id, measured_on ASC)
            """
        )
        conn.commit()
    finally:
        conn.close()


def ensure_default_workout_plans(user_id: int) -> None:
    conn = get_connection()
    try:
        for position, (name, description) in enumerate(DEFAULT_WORKOUT_PLANS, start=1):
            conn.execute(
                """
                INSERT OR IGNORE INTO workout_plans (
                    user_id,
                    name,
                    description,
                    position
                ) VALUES (?, ?, ?, ?)
                """,
                (user_id, name, description, position),
            )
        conn.commit()
    finally:
        conn.close()


def get_workout_plans(user_id: int):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, name, description, position
            FROM workout_plans
            WHERE user_id = ?
            ORDER BY position, id
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def update_workout_plan_description(user_id: int, plan_id: int, description: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE workout_plans
            SET description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (description, plan_id, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def add_workout_result(
    user_id: int,
    plan_id: int,
    exercise: str,
    result: str,
    performed_on: str,
    notes: str = "",
) -> int:
    conn = get_connection()
    try:
        plan = conn.execute(
            "SELECT id FROM workout_plans WHERE id = ? AND user_id = ?",
            (plan_id, user_id),
        ).fetchone()
        if not plan:
            raise ValueError("Выбранная тренировка не найдена.")

        cursor = conn.execute(
            """
            INSERT INTO workout_results (
                user_id,
                workout_plan_id,
                exercise,
                result,
                performed_on,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, plan_id, exercise, result, performed_on, notes),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_workout_results(user_id: int, limit: int | None = 50):
    conn = get_connection()
    try:
        limit_clause = ""
        parameters = [user_id]
        if limit is not None:
            limit_clause = "LIMIT ?"
            parameters.append(max(1, int(limit)))
        return conn.execute(
            f"""
            SELECT
                workout_results.id,
                workout_results.exercise,
                workout_results.result,
                workout_results.performed_on,
                workout_results.notes,
                workout_plans.name AS workout_name
            FROM workout_results
            JOIN workout_plans
                ON workout_plans.id = workout_results.workout_plan_id
                AND workout_plans.user_id = workout_results.user_id
            WHERE workout_results.user_id = ?
            ORDER BY workout_results.performed_on DESC, workout_results.id DESC
            {limit_clause}
            """,
            parameters,
        ).fetchall()
    finally:
        conn.close()


def delete_workout_result(user_id: int, result_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM workout_results WHERE id = ? AND user_id = ?",
            (result_id, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def upsert_weight_entry(
    user_id: int,
    measured_on: str,
    weight_kg: float,
    notes: str = "",
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO weight_entries (user_id, measured_on, weight_kg, notes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, measured_on) DO UPDATE SET
                weight_kg = excluded.weight_kg,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, measured_on, weight_kg, notes),
        )
        conn.commit()
    finally:
        conn.close()


def get_weight_entries(user_id: int):
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT id, measured_on, weight_kg, notes
            FROM weight_entries
            WHERE user_id = ?
            ORDER BY measured_on ASC, id ASC
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def delete_weight_entry(user_id: int, entry_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM weight_entries WHERE id = ? AND user_id = ?",
            (entry_id, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def build_workout_summary(results, weight_entries) -> dict:
    current_weight = None
    total_change = None
    minimum_weight = None
    maximum_weight = None
    if weight_entries:
        weights = [float(item["weight_kg"]) for item in weight_entries]
        current_weight = weights[-1]
        total_change = current_weight - weights[0]
        minimum_weight = min(weights)
        maximum_weight = max(weights)

    cutoff = date.today() - timedelta(days=29)
    recent_workout_days = set()
    for item in results:
        try:
            result_date = datetime.strptime(item["performed_on"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if cutoff <= result_date <= date.today():
            recent_workout_days.add(result_date)

    return {
        "current_weight": current_weight,
        "total_change": total_change,
        "minimum_weight": minimum_weight,
        "maximum_weight": maximum_weight,
        "weight_entries_count": len(weight_entries),
        "result_count": len(results),
        "recent_workout_days": len(recent_workout_days),
    }


def _validate_date(raw_value: str, field_label: str) -> str:
    normalized = (raw_value or "").strip()
    try:
        parsed = datetime.strptime(normalized, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Укажите корректную дату для поля «{field_label}».") from exc
    if parsed.isoformat() != normalized:
        raise ValueError(f"Укажите корректную дату для поля «{field_label}».")
    if parsed > date.today():
        raise ValueError(f"Дата в поле «{field_label}» не может быть в будущем.")
    return parsed.isoformat()


def _validate_text(raw_value: str, field_label: str, max_length: int) -> str:
    normalized = (raw_value or "").strip()
    if not normalized:
        raise ValueError(f"Заполните поле «{field_label}».")
    if len(normalized) > max_length:
        raise ValueError(
            f"Поле «{field_label}» не должно быть длиннее {max_length} символов."
        )
    return normalized


def _validate_optional_text(raw_value: str, field_label: str, max_length: int) -> str:
    normalized = (raw_value or "").strip()
    if len(normalized) > max_length:
        raise ValueError(
            f"Поле «{field_label}» не должно быть длиннее {max_length} символов."
        )
    return normalized


def _validate_weight(raw_value: str) -> float:
    normalized = (raw_value or "").strip().replace(",", ".")
    try:
        weight = float(normalized)
    except ValueError as exc:
        raise ValueError("Вес должен быть числом.") from exc
    if not math.isfinite(weight) or not 20 <= weight <= 500:
        raise ValueError("Укажите вес от 20 до 500 кг.")
    return round(weight, 2)


def _format_date_ru(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return value


@workouts_bp.route("")
@login_required
def index():
    user_id = int(current_user.id)
    ensure_default_workout_plans(user_id)
    plans = get_workout_plans(user_id)
    all_results = get_workout_results(user_id, limit=None)
    weight_entries = get_weight_entries(user_id)
    chart_points = [
        {
            "date": item["measured_on"],
            "weight": round(float(item["weight_kg"]), 2),
        }
        for item in weight_entries
    ]
    result_history = [
        {**dict(item), "display_date": _format_date_ru(item["performed_on"])}
        for item in all_results[:50]
    ]
    weight_history = [
        {**dict(item), "display_date": _format_date_ru(item["measured_on"])}
        for item in reversed(weight_entries)
    ]
    return render_template(
        "workouts.html",
        plans=plans,
        workout_results=result_history,
        weight_entries=weight_history,
        weight_chart_points=chart_points,
        summary=build_workout_summary(all_results, weight_entries),
        today=date.today().isoformat(),
    )


@workouts_bp.route("/plans/<int:plan_id>", methods=["POST"])
@login_required
def update_plan(plan_id: int):
    user_id = int(current_user.id)
    try:
        description = _validate_text(
            request.form.get("description", ""),
            "Описание",
            800,
        )
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("workouts.index", _anchor=f"plan-{plan_id}"))

    if not update_workout_plan_description(user_id, plan_id, description):
        abort(404)
    flash("Описание тренировки сохранено.", "success")
    return redirect(url_for("workouts.index", _anchor=f"plan-{plan_id}"))


@workouts_bp.route("/results", methods=["POST"])
@login_required
def create_result():
    user_id = int(current_user.id)
    try:
        raw_plan_id = request.form.get("workout_plan_id", "")
        try:
            plan_id = int(raw_plan_id)
        except (TypeError, ValueError) as error:
            raise ValueError("Выберите тренировку.") from error
        exercise = _validate_text(request.form.get("exercise", ""), "Упражнение", 120)
        result = _validate_text(request.form.get("result", ""), "Результат", 120)
        performed_on = _validate_date(
            request.form.get("performed_on", ""),
            "Дата тренировки",
        )
        notes = _validate_optional_text(request.form.get("notes", ""), "Заметка", 500)
        add_workout_result(
            user_id,
            plan_id,
            exercise,
            result,
            performed_on,
            notes,
        )
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("workouts.index", _anchor="add-result"))

    flash("Результат упражнения добавлен.", "success")
    return redirect(url_for("workouts.index", _anchor="results"))


@workouts_bp.route("/results/<int:result_id>/delete", methods=["POST"])
@login_required
def remove_result(result_id: int):
    if not delete_workout_result(int(current_user.id), result_id):
        abort(404)
    flash("Результат удалён.", "success")
    return redirect(url_for("workouts.index", _anchor="results"))


@workouts_bp.route("/weight", methods=["POST"])
@login_required
def save_weight():
    user_id = int(current_user.id)
    try:
        measured_on = _validate_date(
            request.form.get("measured_on", ""),
            "Дата измерения",
        )
        weight_kg = _validate_weight(request.form.get("weight_kg", ""))
        notes = _validate_optional_text(request.form.get("notes", ""), "Заметка", 300)
        upsert_weight_entry(user_id, measured_on, weight_kg, notes)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("workouts.index", _anchor="add-weight"))

    flash("Вес сохранён. Повторная запись за ту же дату обновляет значение.", "success")
    return redirect(url_for("workouts.index", _anchor="weight-progress"))


@workouts_bp.route("/weight/<int:entry_id>/delete", methods=["POST"])
@login_required
def remove_weight(entry_id: int):
    if not delete_weight_entry(int(current_user.id), entry_id):
        abort(404)
    flash("Измерение веса удалено.", "success")
    return redirect(url_for("workouts.index", _anchor="weight-progress"))
