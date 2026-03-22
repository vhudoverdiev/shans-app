from datetime import datetime

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from app.auth import verify_user
from app.models import (
    create_budget_entry,
    get_all_budget_entries,
    get_budget_summary,
    delete_budget_entry,
    get_budget_entry_by_id,
    update_budget_entry,
    get_current_balance,
    set_current_balance,
    create_car_done_service,
    create_car_planned_service,
    get_car_done_services,
    get_car_planned_services,
    get_car_total_spent,
    get_car_last_mileage,
    create_car_notification,
    get_car_notifications
)
from app.utils import build_budget_excel


def register_routes(app):
    """
    Регистрирует маршруты приложения.
    """

    months = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]

    categories = ["Авто", "Еда", "Другое"]

    month_map = {
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
        12: "Декабрь"
    }

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

            flash("Неверный логин или пароль.")

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/budget")
    @login_required
    def budget():
        current_month_map = {
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
            12: "Декабрь"
        }

        current_month = current_month_map[datetime.now().month]
        summary = get_budget_summary(current_month)
        current_balance = get_current_balance()

        return render_template(
            "budget.html",
            current_month=current_month,
            summary=summary,
            current_balance=current_balance
        )
        current_month = month_map[datetime.now().month]

        selected_month = request.args.get("month", current_month)
        type_filter = request.args.get("type_filter", "")
        category_filter = request.args.get("category_filter", "")
        sort_by = request.args.get("sort_by", "newest")

        entries = get_all_budget_entries(
            month_filter=selected_month,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by=sort_by
        )

        summary = get_budget_summary(selected_month)
        current_balance = get_current_balance()

        return render_template(
            "budget.html",
            entries=entries,
            summary=summary,
            current_balance=current_balance,
            selected_month=selected_month,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by=sort_by,
            months=months,
            categories=categories
        )

    @app.route("/budget/manage", methods=["GET", "POST"])
    @login_required
    def budget_manage():
        months = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]

        categories = ["Авто", "Еда", "Другое"]

        if request.method == "POST":
            form_type = request.form.get("form_type", "").strip()

            if form_type == "add_entry":
                month_name = request.form.get("month_name", "").strip()
                entry_type = request.form.get("entry_type", "").strip()
                category = request.form.get("category", "").strip()
                amount = request.form.get("amount", "").strip()

                if not month_name or not entry_type or not category or not amount:
                    flash("Заполни все обязательные поля.")
                    return redirect(url_for("budget_manage"))

                try:
                    amount = float(amount)
                except ValueError:
                    flash("Сумма должна быть числом.")
                    return redirect(url_for("budget_manage"))

                create_budget_entry(
                    entry_type=entry_type,
                    month_name=month_name,
                    category=category,
                    amount=amount
                )

                flash("Запись успешно добавлена.")
                return redirect(url_for("budget_manage"))

            if form_type == "set_balance":
                balance_value = request.form.get("current_balance", "").strip()

                try:
                    balance_value = float(balance_value)
                except ValueError:
                    flash("Текущий баланс должен быть числом.")
                    return redirect(url_for("budget_manage"))

                set_current_balance(balance_value)
                flash("Текущий баланс обновлён.")
                return redirect(url_for("budget_manage"))

        entries = get_all_budget_entries(sort_by="newest")
        current_balance = get_current_balance()

        return render_template(
            "budget_manage.html",
            months=months,
            categories=categories,
            current_balance=current_balance,
            entries=entries
        )
        if request.method == "POST":
            form_type = request.form.get("form_type", "").strip()

            if form_type == "add_entry":
                entry_type = request.form.get("entry_type", "").strip()
                month_name = request.form.get("month_name", "").strip()
                category = request.form.get("category", "").strip()
                amount = request.form.get("amount", "").strip()

                if not entry_type or not month_name or not category or not amount:
                    flash("Заполни все обязательные поля.")
                    return redirect(url_for("budget_manage"))

                try:
                    amount = float(amount)
                except ValueError:
                    flash("Сумма должна быть числом.")
                    return redirect(url_for("budget_manage"))

                create_budget_entry(
                    entry_type=entry_type,
                    month_name=month_name,
                    category=category,
                    amount=amount
                )

                flash("Запись успешно добавлена.")
                return redirect(url_for("budget_manage"))

            if form_type == "set_balance":
                balance_value = request.form.get("current_balance", "").strip()

                try:
                    balance_value = float(balance_value)
                except ValueError:
                    flash("Текущий баланс должен быть числом.")
                    return redirect(url_for("budget_manage"))

                set_current_balance(balance_value)
                flash("Текущий баланс обновлён.")
                return redirect(url_for("budget_manage"))

        current_balance = get_current_balance()

        return render_template(
            "budget_manage.html",
            months=months,
            categories=categories,
            current_balance=current_balance
        )

    @app.route("/budget/report")
    @login_required
    def budget_report():
        current_month_map = {
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
            12: "Декабрь"
        }

        current_month = current_month_map[datetime.now().month]

        selected_month = request.args.get("month", current_month)
        type_filter = request.args.get("type_filter", "")
        category_filter = request.args.get("category_filter", "")
        sort_by = request.args.get("sort_by", "newest")

        months = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]

        categories = ["Авто", "Еда", "Другое"]

        entries = get_all_budget_entries(
            month_filter=selected_month,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by=sort_by
        )

        summary = get_budget_summary(selected_month)

        return render_template(
            "budget_report.html",
            entries=entries,
            summary=summary,
            selected_month=selected_month,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by=sort_by,
            months=months,
            categories=categories
        )

        summary = get_budget_summary(selected_month)

        return render_template(
            "budget_report.html",
            entries=entries,
            summary=summary,
            selected_month=selected_month,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by=sort_by,
            months=months,
            categories=categories
        )

    @app.route("/budget/edit/<int:entry_id>", methods=["GET", "POST"])
    @login_required
    def budget_edit(entry_id):
        entry = get_budget_entry_by_id(entry_id)

        if not entry:
            flash("Запись не найдена.")
            return redirect(url_for("budget"))

        if request.method == "POST":
            entry_type = request.form.get("entry_type", "").strip()
            month_name = request.form.get("month_name", "").strip()
            category = request.form.get("category", "").strip()
            amount = request.form.get("amount", "").strip()

            if not entry_type or not month_name or not category or not amount:
                flash("Заполни все обязательные поля.")
                return redirect(url_for("budget_edit", entry_id=entry_id))

            try:
                amount = float(amount)
            except ValueError:
                flash("Сумма должна быть числом.")
                return redirect(url_for("budget_edit", entry_id=entry_id))

            update_budget_entry(
                entry_id=entry_id,
                entry_type=entry_type,
                month_name=month_name,
                category=category,
                amount=amount
            )

            flash("Запись успешно обновлена.")
            return redirect(url_for("budget"))

        return render_template(
            "budget_edit.html",
            entry=entry,
            months=months,
            categories=categories
        )

    @app.route("/budget/delete/<int:entry_id>", methods=["POST"])
    @login_required
    def budget_delete(entry_id):
        delete_budget_entry(entry_id)
        flash("Запись успешно удалена.")
        return redirect(url_for("budget"))

    @app.route("/budget/export")
    @login_required
    def budget_export():
        current_month = month_map[datetime.now().month]

        selected_month = request.args.get("month", current_month)
        type_filter = request.args.get("type_filter", "")
        category_filter = request.args.get("category_filter", "")
        sort_by = request.args.get("sort_by", "newest")

        entries = get_all_budget_entries(
            month_filter=selected_month,
            type_filter=type_filter,
            category_filter=category_filter,
            sort_by=sort_by
        )

        summary = get_budget_summary(selected_month)
        current_balance = get_current_balance()

        excel_file = build_budget_excel(
            entries=entries,
            summary=summary,
            current_balance=current_balance,
            selected_month=selected_month
        )

        return send_file(
            excel_file,
            as_attachment=True,
            download_name="budget.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    @app.route("/car", methods=["GET", "POST"])
    @login_required
    def car():
        if request.method == "POST":
            form_type = request.form.get("form_type", "").strip()

            if form_type == "done_service":
                service_name = request.form.get("service_name", "").strip()
                service_cost = request.form.get("service_cost", "").strip()
                mileage = request.form.get("mileage", "").strip()
                service_date = request.form.get("service_date", "").strip()
                brand = request.form.get("brand", "").strip()
                note = request.form.get("note", "").strip()

                if not service_name or not service_cost or not mileage or not service_date:
                    flash("Заполни обязательные поля выполненной работы.")
                    return redirect(url_for("car"))

                try:
                    service_cost = float(service_cost)
                    mileage = int(mileage)
                except ValueError:
                    flash("Стоимость должна быть числом, а пробег — целым числом.")
                    return redirect(url_for("car"))

                create_car_done_service(
                    service_name=service_name,
                    service_cost=service_cost,
                    mileage=mileage,
                    service_date=service_date,
                    brand=brand,
                    note=note
                )

                flash("Выполненная работа добавлена.")
                return redirect(url_for("car"))

            if form_type == "planned_service":
                service_name = request.form.get("service_name", "").strip()
                planned_cost = request.form.get("planned_cost", "").strip()
                priority = request.form.get("priority", "").strip()
                note = request.form.get("note", "").strip()

                if not service_name or not planned_cost:
                    flash("Заполни обязательные поля планируемой работы.")
                    return redirect(url_for("car"))

                try:
                    planned_cost = float(planned_cost)
                except ValueError:
                    flash("Планируемая стоимость должна быть числом.")
                    return redirect(url_for("car"))

                create_car_planned_service(
                    service_name=service_name,
                    planned_cost=planned_cost,
                    priority=priority,
                    note=note
                )

                flash("Планируемая работа добавлена.")
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
            last_mileage=last_mileage
        )        
    @app.route("/car/notifications", methods=["GET", "POST"])
    @login_required
    def car_notifications():
        if request.method == "POST":
            service_name = request.form.get("service_name", "").strip()
            period_value = request.form.get("period_value", "").strip()
            last_service_date = request.form.get("last_service_date", "").strip()
            mileage_at_service = request.form.get("mileage_at_service", "").strip()
            brand = request.form.get("brand", "").strip()
            status = request.form.get("status", "").strip()

            if not service_name or not period_value or not last_service_date or not mileage_at_service or not status:
                flash("Заполни все обязательные поля уведомления.")
                return redirect(url_for("car_notifications"))

            try:
                mileage_at_service = int(mileage_at_service)
            except ValueError:
                flash("Пробег должен быть целым числом.")
                return redirect(url_for("car_notifications"))

            create_car_notification(
                service_name=service_name,
                period_value=period_value,
                last_service_date=last_service_date,
                mileage_at_service=mileage_at_service,
                brand=brand,
                status=status
            )

            flash("Уведомление добавлено.")
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
                    next_date = f"{base_date.year + 1:04d}-{base_date.month:02d}-{base_date.day:02d}"

            except Exception:
                next_date = "Ошибка даты"

            prepared_notifications.append({
                "id": item["id"],
                "service_name": item["service_name"],
                "period_value": item["period_value"],
                "last_service_date": item["last_service_date"],
                "mileage_at_service": item["mileage_at_service"],
                "brand": item["brand"],
                "status": item["status"],
                "next_date": next_date
            })

        return render_template(
            "car_notifications.html",
            notifications=prepared_notifications
        )        