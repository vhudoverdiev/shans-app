from datetime import datetime

from app.database import get_connection


def get_current_year():
    """
    Возвращает текущий год.
    """
    return datetime.now().year


def get_user_by_username(username):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    return user


def create_budget_entry(entry_type, month_name, category, amount):
    """
    Создаёт новую запись бюджета.
    Год сохраняется автоматически.
    """
    year_value = get_current_year()

    conn = get_connection()
    conn.execute("""
        INSERT INTO budget_entries (entry_type, month_name, year_value, category, amount)
        VALUES (?, ?, ?, ?, ?)
    """, (entry_type, month_name, year_value, category, amount))
    conn.commit()
    conn.close()


def get_all_budget_entries(month_filter="", type_filter="", category_filter="", sort_by="newest"):
    """
    Возвращает список записей бюджета за текущий год.
    """
    current_year = get_current_year()

    conn = get_connection()

    query = "SELECT * FROM budget_entries WHERE year_value = ?"
    params = [current_year]

    if month_filter:
        query += " AND month_name = ?"
        params.append(month_filter)

    if type_filter:
        query += " AND entry_type = ?"
        params.append(type_filter)

    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)

    if sort_by == "month":
        query += """
            ORDER BY
            CASE month_name
                WHEN 'Январь' THEN 1
                WHEN 'Февраль' THEN 2
                WHEN 'Март' THEN 3
                WHEN 'Апрель' THEN 4
                WHEN 'Май' THEN 5
                WHEN 'Июнь' THEN 6
                WHEN 'Июль' THEN 7
                WHEN 'Август' THEN 8
                WHEN 'Сентябрь' THEN 9
                WHEN 'Октябрь' THEN 10
                WHEN 'Ноябрь' THEN 11
                WHEN 'Декабрь' THEN 12
                ELSE 99
            END ASC,
            id DESC
        """
    elif sort_by == "income_first":
        query += """
            ORDER BY
            CASE WHEN entry_type = 'Доход' THEN 0 ELSE 1 END,
            id DESC
        """
    elif sort_by == "expense_first":
        query += """
            ORDER BY
            CASE WHEN entry_type = 'Расход' THEN 0 ELSE 1 END,
            id DESC
        """
    elif sort_by == "category":
        query += " ORDER BY category ASC, id DESC"
    else:
        query += " ORDER BY id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_budget_summary(month_name):
    """
    Возвращает сводку за выбранный месяц текущего года.
    """
    current_year = get_current_year()
    conn = get_connection()

    income = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM budget_entries
        WHERE entry_type = 'Доход'
          AND month_name = ?
          AND year_value = ?
    """, (month_name, current_year)).fetchone()["total"]

    expense = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM budget_entries
        WHERE entry_type = 'Расход'
          AND month_name = ?
          AND year_value = ?
    """, (month_name, current_year)).fetchone()["total"]

    conn.close()

    balance = income - expense

    return {
        "income": income,
        "expense": expense,
        "balance": balance,
        "year_value": current_year
    }


def delete_budget_entry(entry_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM budget_entries WHERE id = ?",
        (entry_id,)
    )
    conn.commit()
    conn.close()


def get_budget_entry_by_id(entry_id):
    conn = get_connection()
    entry = conn.execute(
        "SELECT * FROM budget_entries WHERE id = ?",
        (entry_id,)
    ).fetchone()
    conn.close()
    return entry


def update_budget_entry(entry_id, entry_type, month_name, category, amount):
    """
    Обновляет запись бюджета.
    Год оставляем текущим.
    """
    current_year = get_current_year()

    conn = get_connection()
    conn.execute("""
        UPDATE budget_entries
        SET entry_type = ?, month_name = ?, year_value = ?, category = ?, amount = ?
        WHERE id = ?
    """, (entry_type, month_name, current_year, category, amount, entry_id))
    conn.commit()
    conn.close()


def get_current_balance():
    conn = get_connection()
    row = conn.execute("SELECT current_balance FROM budget_settings LIMIT 1").fetchone()
    conn.close()
    return row["current_balance"] if row else 0


def set_current_balance(value):
    conn = get_connection()
    conn.execute("UPDATE budget_settings SET current_balance = ? WHERE id = 1", (value,))
    conn.commit()
    conn.close()
    
def create_car_done_service(service_name, service_cost, mileage, service_date, brand, note):
    conn = get_connection()
    conn.execute("""
        INSERT INTO car_done_services (
            service_name, service_cost, mileage, service_date, brand, note
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (service_name, service_cost, mileage, service_date, brand, note))
    conn.commit()
    conn.close()


def create_car_planned_service(service_name, planned_cost, priority, note):
    conn = get_connection()
    conn.execute("""
        INSERT INTO car_planned_services (
            service_name, planned_cost, priority, note
        )
        VALUES (?, ?, ?, ?)
    """, (service_name, planned_cost, priority, note))
    conn.commit()
    conn.close()


def get_car_done_services():
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM car_done_services
        ORDER BY service_date DESC, id DESC
    """).fetchall()
    conn.close()
    return rows


def get_car_planned_services():
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM car_planned_services
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return rows


def get_car_total_spent():
    conn = get_connection()
    total = conn.execute("""
        SELECT COALESCE(SUM(service_cost), 0) AS total
        FROM car_done_services
    """).fetchone()["total"]
    conn.close()
    return total


def get_car_last_mileage():
    conn = get_connection()
    row = conn.execute("""
        SELECT mileage
        FROM car_done_services
        ORDER BY service_date DESC, id DESC
        LIMIT 1
    """).fetchone()
    conn.close()
    return row["mileage"] if row else 0    
def create_car_notification(service_name, period_value, last_service_date, mileage_at_service, brand, status):
    conn = get_connection()
    conn.execute("""
        INSERT INTO car_notifications (
            service_name, period_value, last_service_date, mileage_at_service, brand, status
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (service_name, period_value, last_service_date, mileage_at_service, brand, status))
    conn.commit()
    conn.close()


def get_car_notifications():
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM car_notifications
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return rows