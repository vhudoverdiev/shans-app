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
    create_car_planned_service,
    delete_budget_entry,
    delete_car_done_service,
    delete_car_planned_service,
    get_all_budget_entries,
    get_balance_for_month,
    get_balance_history,
    get_budget_entry_by_id,
    get_budget_summary,
    get_car_done_service_by_id,
    get_car_done_services,
    get_car_last_mileage,
    get_car_planned_service_by_id,
    get_car_planned_services,
    get_car_total_spent,
    get_current_balance,
    get_periodic_services_for_notifications,
    hide_car_notification,
    is_car_notification_hidden,
    move_planned_to_done,
    save_balance_history,
    set_current_balance,
    update_budget_entry,
    update_car_done_service,
    update_car_planned_service,
    create_car_planned_service_from_notification,
    create_car_planned_service,
    hide_car_notification,
    get_hidden_notification_keys,
    archive_car_notification,
    get_archived_car_notifications,
    delete_archived_car_notification,
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


def _get_period_months(period_type: str) -> int:
    if period_type == "6 мес":
        return 6
    if period_type == "12 мес":
        return 12
    return 0


def _add_months(base_date: datetime, months: int) -> datetime:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    return datetime(year, month, 1)


def _build_car_notifications():
    periodic_planned, periodic_done = get_periodic_services_for_notifications()
    hidden_keys = set(get_hidden_notification_keys())
    archived_rows = get_archived_car_notifications()
    notifications = []
    today = datetime.now().replace(day=1)

    month_names = {
        "01": "январь",
        "02": "февраль",
        "03": "март",
        "04": "апрель",
        "05": "май",
        "06": "июнь",
        "07": "июль",
        "08": "август",
        "09": "сентябрь",
        "10": "октябрь",
        "11": "ноябрь",
        "12": "декабрь",
    }

    for item in periodic_planned:
        notification_key = f"planned:{item['id']}"
        if notification_key in hidden_keys:
            continue

        notifications.append({
            "notification_key": notification_key,
            "title": item["service_name"],
            "status": "Скоро",
            "period_type": item["period_type"],
            "detail_description": item["detail_description"] or "—",
            "last_service_date_text": "—",
            "work_kind": item["work_kind"] if "work_kind" in item.keys() and item["work_kind"] else "",
        })

    for item in periodic_done:
        period_months = _get_period_months(item["period_type"])
        if not period_months or not item["service_date"]:
            continue

        try:
            last_date = datetime.strptime(item["service_date"], "%Y-%m")
        except ValueError:
            continue

        next_service_date = _add_months(last_date, period_months)
        status = "Нужна замена" if today >= next_service_date else "Скоро"
        last_service_date_text = f"{month_names[last_date.strftime('%m')]} {last_date.year}"

        notification_key = f"done:{item['id']}:{item['service_date']}"
        if notification_key in hidden_keys:
            continue

        notifications.append({
            "notification_key": notification_key,
            "title": item["service_name"],
            "status": status,
            "period_type": item["period_type"],
            "detail_description": item["detail_description"] or "—",
            "last_service_date_text": last_service_date_text,
            "work_kind": item["work_kind"] if "work_kind" in item.keys() and item["work_kind"] else "",
        })

    for item in archived_rows:
        notifications.append({
            "notification_key": item["notification_key"],
            "title": item["title"],
            "status": "Архив",
            "period_type": item["period_type"] or "—",
            "detail_description": item["detail_description"] or "—",
            "last_service_date_text": item["last_service_date_text"] or "—",
            "work_kind": item["work_kind"] or "",
        })

    status_priority = {
        "Нужна замена": 0,
        "Скоро": 1,
        "Архив": 2,
    }

    notifications.sort(
        key=lambda item: (
            status_priority.get(item["status"], 9),
            item["title"].lower(),
        )
    )

    return notifications


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
        category = entry["category"].strip()
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

    # =========================================================
    # BUDGET
    # =========================================================

    @app.route("/budget")
    @login_required
    def budget():
        current_month = _get_current_month_name()
        summary = get_budget_summary(current_month)

        current_balance = get_balance_for_month(current_month)
        if current_balance is None:
            current_balance = get_current_balance()

        return render_template(
            "budget.html",
            current_month=current_month,
            summary=summary,
            current_balance=current_balance,
        )

    @app.route("/budget/balance")
    @login_required
    def budget_balance():
        history = get_balance_history()

        return render_template(
            "budget_balance.html",
            history=history,
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

                if amount_value < 0:
                    flash("Сумма не может быть отрицательной.", "warning")
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

                if balance_value < 0:
                    flash("Баланс не может быть отрицательным.", "warning")
                    return redirect(url_for("budget_manage"))

                current_month = _get_current_month_name()

                set_current_balance(balance_value)
                save_balance_history(current_month, balance_value)

                flash("Текущий баланс обновлён.", "success")
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

        current_month = _get_current_month_name()
        current_balance = get_balance_for_month(current_month)
        if current_balance is None:
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

            if amount_value < 0:
                flash("Сумма не может быть отрицательной.", "warning")
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

        current_balance = get_balance_for_month(selected_month)
        if current_balance is None:
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

    # =========================================================
    # OTHER SECTIONS
    # =========================================================

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

    # =========================================================
    # CAR
    # =========================================================

    @app.route("/car")
    @login_required
    def car():
        active_tab = request.args.get("tab", "planned")

        done_services = get_car_done_services()
        planned_services = get_car_planned_services()

        month_names = {
            "01": "январь",
            "02": "февраль",
            "03": "март",
            "04": "апрель",
            "05": "май",
            "06": "июнь",
            "07": "июль",
            "08": "август",
            "09": "сентябрь",
            "10": "октябрь",
            "11": "ноябрь",
            "12": "декабрь",
        }

        total_cost = 0
        max_mileage = 0

        prepared_done_services = []
        for item in done_services:
            row = dict(item)

            service_date = row.get("service_date")
            if service_date and "-" in str(service_date):
                parts = str(service_date).split("-")
                if len(parts) >= 2:
                    year = parts[0]
                    month = parts[1]
                    row["service_date_display"] = f"{month_names.get(month, month)} {year}"
                else:
                    row["service_date_display"] = service_date
            else:
                row["service_date_display"] = service_date or "—"

            cost_value = row.get("service_cost")
            mileage_value = row.get("mileage")

            try:
                if cost_value not in (None, ""):
                    total_cost += float(cost_value)
            except (ValueError, TypeError):
                pass

            try:
                if mileage_value not in (None, ""):
                    mileage_number = int(float(mileage_value))
                    if mileage_number > max_mileage:
                        max_mileage = mileage_number
            except (ValueError, TypeError):
                pass

            prepared_done_services.append(row)

        prepared_planned_services = [dict(item) for item in planned_services]

        return render_template(
            "car.html",
            active_tab=active_tab,
            done_services=prepared_done_services,
            planned_services=prepared_planned_services,
            total_cost=total_cost,
            max_mileage=max_mileage,
            planned_count=len(prepared_planned_services),
            done_count=len(prepared_done_services),
        )

    @app.route("/car/manage", methods=["GET", "POST"])
    @login_required
    def car_manage():
        if request.method == "POST":
            service_name = request.form.get("service_name", "").strip()
            detail_description = request.form.get("detail_description", "").strip()
            work_kind = ""
            status = request.form.get("status", "").strip()
            period_type = request.form.get("period_type", "").strip()

            if not service_name:
                flash("Укажите наименование работы.", "error")
                return redirect(url_for("car_manage"))

            if status == "Выполнено":
                service_date = request.form.get("service_date", "").strip()
                mileage = request.form.get("mileage", "").strip()
                cost = request.form.get("cost", "").strip()

                create_car_done_service(
                    service_name=service_name,
                    service_cost=cost,
                    mileage=mileage,
                    service_date=service_date,
                    detail_description=detail_description,
                    work_kind=work_kind,
                    period_type=period_type,
                )
                flash("Выполненная работа добавлена.", "success")
            else:
                create_car_planned_service(
                    service_name=service_name,
                    detail_description=detail_description,
                    work_kind=work_kind,
                    period_type=period_type,
                )
                flash("Планируемая работа добавлена.", "success")

            return redirect(url_for("car"))

        return render_template("car_manage.html")

    @app.route("/car/done/edit/<int:service_id>", methods=["GET", "POST"])
    @login_required
    def car_done_edit(service_id):
        service = get_car_done_service_by_id(service_id)
        if not service:
            flash("Выполненная работа не найдена.", "error")
            return redirect(url_for("car", tab="done"))

        if request.method == "POST":
            service_name = request.form.get("service_name", "").strip()
            detail_description = request.form.get("detail_description", "").strip()
            work_kind = request.form.get("work_kind", "").strip()
            service_date = request.form.get("service_date", "").strip()
            mileage = request.form.get("mileage", "").strip()
            cost = request.form.get("cost", "").strip()
            period_type = request.form.get("period_type", "").strip()

            if not service_name:
                flash("Укажите наименование работы.", "error")
                return redirect(url_for("car_done_edit", service_id=service_id))

            update_car_done_service(
                service_id=service_id,
                service_name=service_name,
                service_cost=cost,
                mileage=mileage,
                service_date=service_date,
                detail_description=detail_description,
                work_kind=work_kind,
                period_type=period_type,
                status="Выполнено",
            )

            flash("Выполненная работа обновлена.", "success")
            return redirect(url_for("car", tab="done"))

        return render_template("car_done_edit.html", service=service)

    @app.route("/car/planned/complete/<int:service_id>", methods=["GET", "POST"])
    @login_required
    def car_planned_complete(service_id):
        service = get_car_planned_service_by_id(service_id)
        if not service:
            flash("Планируемая работа не найдена.", "error")
            return redirect(url_for("car", tab="planned"))

        if request.method == "POST":
            service_date = request.form.get("service_date", "").strip()
            mileage = request.form.get("mileage", "").strip()
            cost = request.form.get("cost", "").strip()

            if not service_date:
                flash("Укажите дату выполнения.", "error")
                return redirect(url_for("car_planned_complete", service_id=service_id))

            create_car_done_service(
                service_name=service["service_name"],
                service_cost=cost,
                mileage=mileage,
                service_date=service_date,
                detail_description=service["detail_description"],
                work_kind=service["work_kind"],
                period_type=service["period_type"],
            )

            delete_car_planned_service(service_id)
            flash("Работа перенесена в выполненные.", "success")
            return redirect(url_for("car", tab="done"))

        return render_template("car_planned_complete.html", service=service)

    @app.route("/car/planned/edit/<int:service_id>", methods=["GET", "POST"])
    @login_required
    def car_planned_edit(service_id):
        service = get_car_planned_service_by_id(service_id)
        if not service:
            flash("Планируемая работа не найдена.", "error")
            return redirect(url_for("car"))

        if request.method == "POST":
            service_name = request.form.get("service_name", "").strip()
            detail_description = request.form.get("detail_description", "").strip()
            work_kind = request.form.get("work_kind", "").strip()
            period_type = request.form.get("period_type", "").strip()

            if not service_name:
                flash("Укажите наименование работы.", "error")
                return redirect(url_for("car_planned_edit", service_id=service_id))

            update_car_planned_service(
                service_id=service_id,
                service_name=service_name,
                detail_description=detail_description,
                work_kind=work_kind,
                period_type=period_type,
            )

            flash("Планируемая работа обновлена.", "success")
            return redirect(url_for("car"))

        return render_template("car_planned_edit.html", service=service)

    @app.route("/car/done/delete/<int:service_id>", methods=["POST"])
    @login_required
    def car_done_delete(service_id):
        delete_car_done_service(service_id)
        flash("Выполненная работа удалена.", "success")
        return redirect(url_for("car"))

    @app.route("/car/planned/delete/<int:service_id>", methods=["POST"])
    @login_required
    def car_planned_delete(service_id):
        delete_car_planned_service(service_id)
        flash("Планируемая работа удалена.", "success")
        return redirect(url_for("car"))

    @app.route("/car/notifications/archive/delete", methods=["POST"])
    @login_required
    def car_notification_archive_delete():
        notification_key = request.form.get("notification_key", "").strip()

        if not notification_key:
            flash("Не удалось удалить уведомление из архива.", "error")
            return redirect(url_for("car_notifications", filter="archive"))

        delete_archived_car_notification(notification_key)
        flash("Уведомление удалено из архива.", "success")
        return redirect(url_for("car_notifications", filter="archive"))

    @app.route("/car/notifications")
    @login_required
    def car_notifications():
        active_filter = request.args.get("filter", "need")
        notifications = _build_car_notifications()

        need_notifications = [item for item in notifications if item["status"] == "Нужна замена"]
        soon_notifications = [item for item in notifications if item["status"] == "Скоро"]
        archived_notifications = [item for item in notifications if item["status"] == "Архив"]

        if active_filter == "soon":
            filtered_notifications = soon_notifications
        elif active_filter == "archive":
            filtered_notifications = archived_notifications
        else:
            active_filter = "need"
            filtered_notifications = need_notifications

        return render_template(
            "car_notifications.html",
            notifications=filtered_notifications,
            active_filter=active_filter,
            need_replacement_count=len(need_notifications),
            soon_count=len(soon_notifications),
            archive_count=len(archived_notifications),
        )
        
    @app.route("/car/notifications/to-work", methods=["POST"])
    @login_required
    def car_notification_to_work():
        service_name = request.form.get("service_name", "").strip()
        detail_description = request.form.get("detail_description", "").strip()
        period_type = request.form.get("period_type", "").strip()
        work_kind = request.form.get("work_kind", "").strip()
        notification_key = request.form.get("notification_key", "").strip()
        notification_status = request.form.get("notification_status", "").strip()
        last_service_date_text = request.form.get("last_service_date_text", "").strip()

        if not service_name:
            flash("Не удалось перенести уведомление в работу.", "error")
            return redirect(url_for("car_notifications"))

        create_car_planned_service(
            service_name=service_name,
            detail_description=detail_description,
            work_kind=work_kind,
            period_type=period_type,
        )

        if notification_key:
            archive_car_notification(
                notification_key=notification_key,
                title=service_name,
                status=notification_status,
                period_type=period_type,
                detail_description=detail_description,
                last_service_date_text=last_service_date_text,
                work_kind=work_kind,
            )
            hide_car_notification(notification_key)

        flash("Уведомление перенесено в планируемые работы.", "success")
        return redirect(url_for("car_notifications"))

    @app.route("/car/notifications/hide", methods=["POST"])
    @login_required
    def car_notification_hide():
        notification_key = request.form.get("notification_key", "").strip()

        if not notification_key:
            flash("Не удалось скрыть уведомление.", "error")
            return redirect(url_for("car_notifications"))

        hide_car_notification(notification_key)
        flash("Уведомление скрыто.", "success")
        return redirect(url_for("car_notifications"))    