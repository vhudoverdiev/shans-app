from datetime import datetime

from flask import (
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from app.auth import verify_user
from app.models import (
    create_budget_entry,
    create_car_done_service,
    create_car_notification,
    create_car_planned_service,
    delete_budget_entry,
    get_all_budget_entries,
    get_budget_entry_by_id,
    get_budget_summary,
    get_car_done_services,
    get_car_last_mileage,
    get_car_notifications,
    get_car_planned_services,
    get_car_total_spent,
    get_current_balance,
    set_current_balance,
    update_budget_entry,
)
from app.utils import build_budget_excel


MONTHS = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

BASE_CATEGORIES = ["Авто", "Еда", "Другое"]

MONTH_MAP = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}


def _get_current_month_name() -> str:
    return MONTH_MAP[datetime.now().month]


def _resolve_budget_category(form):
    """
    Возвращает итоговую категорию бюджета.
    Если выбрано 'Другое', берём custom_category.
    """
    category = form.get("category", "").strip()
    custom_category = form.get("custom_category", "").strip()

    if category == "Другое":
        return custom_category.strip()

    return category.strip()


def _collect_budget_categories(entries):
    """
    Собирает категории для фильтров:
    сначала базовые, затем все реальные категории из записей.
    """
    categories = ["Авто", "Еда"]

    existing = set(categories)

    for entry in entries:
        category = (entry["category"] if isinstance(entry, dict) else entry["category"]).strip()
        if category and category not in existing:
            categories.append(category)
            existing.add(category)

    if "Другое" not in categories:
        categories.append("Другое")

    return categories


def register_routes(app):
    @app.route("/")
    @login_required
    def index():
        return render_template("index.html", username=current_user.username)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            user = verify_user(username, password)
            if user:
                login_user(user)
                return redirect(url_for("index"))

            flash("Неверный логин или пароль.", "danger")

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/budget")
    @login_required
    def budget():
        current_month = _get_current_month_name()
        summary = get_budget_summary(current_month)
        current_balance = get_current_balance()

        return render_template(
            "budget.html",
            current_month=current_month,
            summary=summary,
            current_balance=current_balance,
        )

    @app.route("/budget/manage", methods=["GET", "POST"])
    @login_required
    def budget_manage():
        if request.method == "POST":
            form_type = request.form.get("form_type", "").strip()

            if form_type == "add_entry":
                month_name = request.form.get("month_name", "").strip()
                entry_type = request.form.get("entry_type", "").strip()
                amount_raw = request.form.get("amount", "").strip()
                category = _resolve_budget_category(request.form)

                if not month_name or not entry_type or not amount_raw:
                    flash("Заполни все обязательные поля.", "warning")
                    return redirect(url_for("budget_manage"))

                if not category:
                    flash("Если выбрано 'Другое', укажи свою категорию.", "warning")
                    return redirect(url_for("budget_manage"))

                try:
                    amount_value = int(amount_raw)
                except ValueError:
                    flash("Сумма должна быть целым числом.", "danger")
                    return redirect(url_for("budget_manage"))

                create_budget_entry(
                    entry_type=entry_type,
                    month_name=month_name,
                    category=category,
                    amount=amount_value,
                )
                flash("Запись успешно добавлена.", "success")
                return redirect(url_for("budget_manage"))

            if form_type == "set_balance":
                balance_raw = request.form.get("current_balance", "").strip()

                if not balance_raw:
                    flash("Введите текущий баланс.", "warning")
                    return redirect(url_for("budget_manage"))

                try:
                    balance_value = int(balance_raw)
                except ValueError:
                    flash("Баланс должен быть целым числом.", "danger")
                    return redirect(url_for("budget_manage"))

                set_current_balance(balance_value)
                flash("Текущий баланс обновлён.", "success")
                return redirect(url_for("budget_manage"))

            flash("Неизвестный тип формы.", "danger")
            return redirect(url_for("budget_manage"))

        month_filter = request.args.get("month", "").strip()
        type_filter = request.args.get("type_filter", "").strip()
        category_filter = request.args.get("category_filter", "").strip()
        sort_by = request.args.get("sort_by", "newest").strip()

        entries = get_all_budget_entries(
            month_filter=month_filter,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by=sort_by,
        )

        all_entries = get_all_budget_entries(sort_by="newest")
        categories = _collect_budget_categories(all_entries)
        current_balance = get_current_balance()

        return render_template(
            "budget_manage.html",
            months=MONTHS,
            categories=categories,
            base_categories=BASE_CATEGORIES,
            current_balance=current_balance,
            entries=entries,
            month_filter=month_filter,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by=sort_by,
        )

    @app.route("/budget/report")
    @login_required
    def budget_report():
        current_month = _get_current_month_name()

        selected_month = request.args.get("month", current_month).strip()
        type_filter = request.args.get("type_filter", "").strip()
        category_filter = request.args.get("category_filter", "").strip()

        entries = get_all_budget_entries(
            month_filter=selected_month,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by="newest",
        )
        all_entries = get_all_budget_entries(sort_by="newest")
        categories = _collect_budget_categories(all_entries)

        summary = get_budget_summary(selected_month)

        return render_template(
            "budget_report.html",
            entries=entries,
            summary=summary,
            selected_month=selected_month,
            type_filter=type_filter,
            category_filter=category_filter,
            months=MONTHS,
            categories=categories,
        )

    @app.route("/budget/edit/<int:entry_id>", methods=["GET", "POST"])
    @login_required
    def budget_edit(entry_id):
        entry = get_budget_entry_by_id(entry_id)
        if not entry:
            flash("Запись не найдена.", "danger")
            return redirect(url_for("budget_manage"))

        all_entries = get_all_budget_entries(sort_by="newest")
        categories = _collect_budget_categories(all_entries)

        if request.method == "POST":
            entry_type = request.form.get("entry_type", "").strip()
            month_name = request.form.get("month_name", "").strip()
            amount_raw = request.form.get("amount", "").strip()
            category = _resolve_budget_category(request.form)

            if not entry_type or not month_name or not amount_raw:
                flash("Заполни все обязательные поля.", "warning")
                return redirect(url_for("budget_edit", entry_id=entry_id))

            if not category:
                flash("Если выбрано 'Другое', укажи свою категорию.", "warning")
                return redirect(url_for("budget_edit", entry_id=entry_id))

            try:
                amount_value = int(amount_raw)
            except ValueError:
                flash("Сумма должна быть целым числом.", "danger")
                return redirect(url_for("budget_edit", entry_id=entry_id))

            update_budget_entry(
                entry_id=entry_id,
                entry_type=entry_type,
                month_name=month_name,
                category=category,
                amount=amount_value,
            )
            flash("Запись успешно обновлена.", "success")
            return redirect(url_for("budget_manage"))

        return render_template(
            "budget_edit.html",
            entry=entry,
            months=MONTHS,
            categories=categories,
            base_categories=BASE_CATEGORIES,
        )

    @app.route("/budget/delete/<int:entry_id>", methods=["POST"])
    @login_required
    def budget_delete(entry_id):
        delete_budget_entry(entry_id)
        flash("Запись успешно удалена.", "success")
        return redirect(url_for("budget_manage"))

    @app.route("/budget/export")
    @login_required
    def budget_export():
        current_month = _get_current_month_name()

        selected_month = request.args.get("month", current_month).strip()
        type_filter = request.args.get("type_filter", "").strip()
        category_filter = request.args.get("category_filter", "").strip()

        entries = get_all_budget_entries(
            month_filter=selected_month,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by="newest",
        )
        summary = get_budget_summary(selected_month)
        current_balance = get_current_balance()

        excel_file = build_budget_excel(
            entries=entries,
            summary=summary,
            current_balance=current_balance,
            selected_month=selected_month,
        )

        return send_file(
            excel_file,
            as_attachment=True,
            download_name=f"budget_{selected_month}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.route("/schedule")
    @login_required
    def schedule():
        return render_template("schedule.html")

    @app.route("/photo-projects")
    @login_required
    def photo_projects():
        return render_template("photo_projects.html")

    @app.route("/shootings")
    @login_required
    def shootings():
        return render_template("shootings.html")

    @app.route("/car", methods=["GET", "POST"])
    @login_required
    def car():
        if request.method == "POST":
            form_type = request.form.get("form_type", "").strip()

            if form_type == "done_service":
                service_name = request.form.get("service_name", "").strip()
                service_cost_raw = request.form.get("service_cost", "").strip()
                mileage_raw = request.form.get("mileage", "").strip()
                service_date = request.form.get("service_date", "").strip()
                brand = request.form.get("brand", "").strip()
                note = request.form.get("note", "").strip()

                if not service_name or not service_cost_raw or not mileage_raw or not service_date:
                    flash("Заполни обязательные поля выполненной работы.", "warning")
                    return redirect(url_for("car"))

                try:
                    service_cost = int(service_cost_raw)
                    mileage = int(mileage_raw)
                except ValueError:
                    flash("Стоимость и пробег должны быть целыми числами.", "danger")
                    return redirect(url_for("car"))

                create_car_done_service(
                    service_name=service_name,
                    service_cost=service_cost,
                    mileage=mileage,
                    service_date=service_date,
                    brand=brand,
                    note=note,
                )
                flash("Выполненная работа добавлена.", "success")
                return redirect(url_for("car"))

            if form_type == "planned_service":
                service_name = request.form.get("service_name", "").strip()
                planned_cost_raw = request.form.get("planned_cost", "").strip()
                priority = request.form.get("priority", "").strip()
                note = request.form.get("note", "").strip()

                if not service_name or not planned_cost_raw:
                    flash("Заполни обязательные поля планируемой работы.", "warning")
                    return redirect(url_for("car"))

                try:
                    planned_cost = int(planned_cost_raw)
                except ValueError:
                    flash("Планируемая стоимость должна быть целым числом.", "danger")
                    return redirect(url_for("car"))

                create_car_planned_service(
                    service_name=service_name,
                    planned_cost=planned_cost,
                    priority=priority or "Обычный",
                    note=note,
                )
                flash("Планируемая работа добавлена.", "success")
                return redirect(url_for("car"))

            flash("Неизвестный тип формы.", "danger")
            return redirect(url_for("car"))

        done_services = get_car_done_services()
        planned_services = get_car_planned_services()
        total_spent = get_car_total_spent()
        last_mileage = get_car_last_mileage()

        return render_template(
            "car.html",
            done_services=done_services,
            planned_services=planned_services,
            total_spent=total_spent,
            last_mileage=last_mileage,
        )

    @app.route("/car/notifications", methods=["GET", "POST"])
    @login_required
    def car_notifications():
        if request.method == "POST":
            service_name = request.form.get("service_name", "").strip()
            period_value = request.form.get("period_value", "").strip()
            last_service_date = request.form.get("last_service_date", "").strip()
            mileage_at_service_raw = request.form.get("mileage_at_service", "").strip()
            brand = request.form.get("brand", "").strip()
            status = request.form.get("status", "").strip()

            if (
                not service_name
                or not period_value
                or not last_service_date
                or not mileage_at_service_raw
                or not status
            ):
                flash("Заполни все обязательные поля уведомления.", "warning")
                return redirect(url_for("car_notifications"))

            try:
                mileage_at_service = int(mileage_at_service_raw)
            except ValueError:
                flash("Пробег должен быть целым числом.", "danger")
                return redirect(url_for("car_notifications"))

            create_car_notification(
                service_name=service_name,
                period_value=period_value,
                last_service_date=last_service_date,
                mileage_at_service=mileage_at_service,
                brand=brand,
                status=status,
            )
            flash("Уведомление добавлено.", "success")
            return redirect(url_for("car_notifications"))

        notifications = get_car_notifications()
        prepared_notifications = []

        for item in notifications:
            next_date = ""

            try:
                base_date = datetime.strptime(item["last_service_date"], "%Y-%m-%d")

                if item["period_value"] == "Раз в пол года":
                    month = base_date.month + 6
                    year = base_date.year
                    day = base_date.day

                    if month > 12:
                        month -= 12
                        year += 1

                    next_date = f"{year:04d}-{month:02d}-{day:02d}"

                elif item["period_value"] == "Раз в год":
                    next_date = (
                        f"{base_date.year + 1:04d}-"
                        f"{base_date.month:02d}-"
                        f"{base_date.day:02d}"
                    )
                else:
                    next_date = "Не задано"

            except Exception:
                next_date = "Ошибка даты"

            prepared_notifications.append(
                {
                    "id": item["id"],
                    "service_name": item["service_name"],
                    "period_value": item["period_value"],
                    "last_service_date": item["last_service_date"],
                    "mileage_at_service": item["mileage_at_service"],
                    "brand": item["brand"],
                    "status": item["status"],
                    "next_date": next_date,
                }
            )

        return render_template(
            "car_notifications.html",
            notifications=prepared_notifications,
        )