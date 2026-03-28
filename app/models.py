from datetime import date, datetime
from app.database import get_connection


# =========================================================
# COMMON
# =========================================================

def get_current_year():
    """
    Возвращает текущий год.
    """
    return datetime.now().year


# =========================================================
# USERS
# =========================================================

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


# =========================================================
# BUDGET
# =========================================================

def create_budget_entry(entry_type, month_name, category, amount):
    """
    Создаёт новую запись бюджета.
    Год сохраняется автоматически.
    """
    year_value = get_current_year()

    conn = get_connection()
    conn.execute("""
        INSERT INTO budget_entries (
            entry_type,
            month_name,
            year_value,
            category,
            amount
        )
        VALUES (?, ?, ?, ?, ?)
    """, (entry_type, month_name, year_value, category, amount))
    conn.commit()
    conn.close()


def get_all_budget_entries(
    month_filter="",
    type_filter="",
    category_filter="",
    sort_by="newest",
):
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
        "year_value": current_year,
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
        SET entry_type = ?,
            month_name = ?,
            year_value = ?,
            category = ?,
            amount = ?
        WHERE id = ?
    """, (entry_type, month_name, current_year, category, amount, entry_id))
    conn.commit()
    conn.close()


def get_current_balance():
    conn = get_connection()
    row = conn.execute(
        "SELECT current_balance FROM budget_settings WHERE id = 1"
    ).fetchone()
    conn.close()
    return row["current_balance"] if row else 0


def set_current_balance(value):
    conn = get_connection()
    conn.execute(
        "UPDATE budget_settings SET current_balance = ? WHERE id = 1",
        (value,)
    )
    conn.commit()
    conn.close()


# =========================================================
# BUDGET BALANCE HISTORY
# =========================================================

def save_balance_history(month_name, balance_value, year_value=None):
    """
    Сохраняет одно последнее значение баланса на месяц.
    Если запись за месяц уже есть — обновляет её.
    """
    if year_value is None:
        year_value = get_current_year()

    conn = get_connection()

    existing = conn.execute("""
        SELECT id
        FROM budget_balance_history
        WHERE month_name = ? AND year_value = ?
    """, (month_name, year_value)).fetchone()

    if existing:
        conn.execute("""
            UPDATE budget_balance_history
            SET balance_value = ?,
                created_at = CURRENT_TIMESTAMP
            WHERE month_name = ? AND year_value = ?
        """, (balance_value, month_name, year_value))
    else:
        conn.execute("""
            INSERT INTO budget_balance_history (
                month_name,
                year_value,
                balance_value
            )
            VALUES (?, ?, ?)
        """, (month_name, year_value, balance_value))

    conn.commit()
    conn.close()


def get_balance_history(year_value=None):
    """
    Возвращает историю баланса по месяцам за год.
    """
    if year_value is None:
        year_value = get_current_year()

    conn = get_connection()
    rows = conn.execute("""
        SELECT month_name, year_value, balance_value
        FROM budget_balance_history
        WHERE year_value = ?
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
            END
    """, (year_value,)).fetchall()
    conn.close()
    return rows


def get_balance_for_month(month_name, year_value=None):
    """
    Возвращает баланс за конкретный месяц.
    """
    if year_value is None:
        year_value = get_current_year()

    conn = get_connection()
    row = conn.execute("""
        SELECT balance_value
        FROM budget_balance_history
        WHERE month_name = ? AND year_value = ?
        LIMIT 1
    """, (month_name, year_value)).fetchone()
    conn.close()

    if row:
        return row["balance_value"]

    return None


# =========================================================
# CAR - CREATE
# =========================================================

def create_car_done_service(
    service_name,
    service_cost,
    mileage,
    service_date,
    detail_description,
    work_kind,
    period_type,
):
    """
    Создаёт выполненную работу.
    По умолчанию статус всегда 'Выполнено'.
    """
    conn = get_connection()
    conn.execute("""
        INSERT INTO car_done_services (
            service_name,
            service_cost,
            mileage,
            service_date,
            detail_description,
            work_kind,
            period_type,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        service_name,
        service_cost,
        mileage,
        service_date,
        detail_description,
        work_kind,
        period_type,
        "Выполнено",
    ))
    conn.commit()
    conn.close()


def create_car_planned_service(
    service_name,
    detail_description,
    work_kind,
    period_type,
):
    conn = get_connection()
    conn.execute("""
        INSERT INTO car_planned_services (
            service_name,
            planned_cost,
            mileage,
            detail_description,
            work_kind,
            period_type,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        service_name,
        0,
        0,
        detail_description,
        work_kind,
        period_type,
        "Планируется",
    ))
    conn.commit()
    conn.close()

def delete_archived_car_notification(notification_key):
    conn = get_connection()
    conn.execute(
        "DELETE FROM car_notification_archive WHERE notification_key = ?",
        (notification_key,)
    )
    conn.commit()
    conn.close()
    
def create_car_planned_service_from_notification(
    service_name,
    detail_description,
    work_kind,
    period_type,
):
    """
    Создаёт планируемую работу из уведомления.
    Если такая активная работа уже есть, новую запись не создаём.
    """
    conn = get_connection()

    existing = conn.execute(
        """
        SELECT id
        FROM car_planned_services
        WHERE service_name = ?
          AND COALESCE(detail_description, '') = ?
          AND COALESCE(work_kind, 'Разовая') = ?
          AND COALESCE(period_type, '') = ?
          AND status = 'В работе'
        LIMIT 1
        """,
        (
            service_name,
            detail_description or "",
            work_kind or "Разовая",
            period_type or "",
        ),
    ).fetchone()

    if existing:
        conn.close()
        return False

    conn.execute(
        """
        INSERT INTO car_planned_services (
            service_name,
            planned_cost,
            mileage,
            detail_description,
            work_kind,
            period_type,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            service_name,
            0,
            0,
            detail_description,
            work_kind,
            period_type,
            'В работе',
        ),
    )
    conn.commit()
    conn.close()
    return True


# =========================================================
# CAR - GET
# =========================================================

def get_car_done_services(sort_by="default"):
    conn = get_connection()

    query = """
        SELECT *
        FROM car_done_services
    """

    if sort_by == "name_asc":
        query += " ORDER BY service_name COLLATE NOCASE ASC, id DESC"
    else:
        query += " ORDER BY mileage DESC, id DESC"

    rows = conn.execute(query).fetchall()
    conn.close()
    return rows


def get_car_planned_services(sort_by="default"):
    conn = get_connection()

    query = """
        SELECT *
        FROM car_planned_services
    """

    if sort_by == "name_asc":
        query += " ORDER BY service_name COLLATE NOCASE ASC, id DESC"
    else:
        query += " ORDER BY id DESC"

    rows = conn.execute(query).fetchall()
    conn.close()
    return rows


def get_car_done_service_by_id(service_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM car_done_services WHERE id = ?",
        (service_id,)
    ).fetchone()
    conn.close()
    return row


def get_car_planned_service_by_id(service_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM car_planned_services WHERE id = ?",
        (service_id,)
    ).fetchone()
    conn.close()
    return row


def get_car_total_spent():
    """
    Общие затраты считаем только по выполненным работам.
    """
    conn = get_connection()
    total = conn.execute("""
        SELECT COALESCE(SUM(service_cost), 0) AS total
        FROM car_done_services
    """).fetchone()["total"]
    conn.close()
    return total


def get_car_last_mileage():
    """
    Возвращает самый большой и самый последний пробег
    из выполненных работ.
    """
    conn = get_connection()
    row = conn.execute("""
        SELECT mileage
        FROM car_done_services
        ORDER BY mileage DESC, id DESC
        LIMIT 1
    """).fetchone()
    conn.close()
    return row["mileage"] if row else 0


# =========================================================
# CAR - UPDATE
# =========================================================

def update_car_done_service(
    service_id,
    service_name,
    service_cost,
    mileage,
    service_date,
    detail_description,
    work_kind,
    period_type,
    status,
):
    conn = get_connection()
    conn.execute("""
        UPDATE car_done_services
        SET service_name = ?,
            service_cost = ?,
            mileage = ?,
            service_date = ?,
            detail_description = ?,
            work_kind = ?,
            period_type = ?,
            status = ?
        WHERE id = ?
    """, (
        service_name,
        service_cost,
        mileage,
        service_date,
        detail_description,
        work_kind,
        period_type,
        status,
        service_id,
    ))
    conn.commit()
    conn.close()


def update_car_planned_service(
    service_id,
    service_name,
    planned_cost,
    mileage,
    detail_description,
    work_kind,
    period_type,
    status,
):
    conn = get_connection()
    conn.execute("""
        UPDATE car_planned_services
        SET service_name = ?,
            planned_cost = ?,
            mileage = ?,
            detail_description = ?,
            work_kind = ?,
            period_type = ?,
            status = ?
        WHERE id = ?
    """, (
        service_name,
        planned_cost,
        mileage,
        detail_description,
        work_kind,
        period_type,
        status,
        service_id,
    ))
    conn.commit()
    conn.close()


def update_car_done_service_status(service_id, status):
    conn = get_connection()
    conn.execute("""
        UPDATE car_done_services
        SET status = ?
        WHERE id = ?
    """, (status, service_id))
    conn.commit()
    conn.close()


def update_car_planned_service_status(service_id, status):
    conn = get_connection()
    conn.execute("""
        UPDATE car_planned_services
        SET status = ?
        WHERE id = ?
    """, (status, service_id))
    conn.commit()
    conn.close()


# =========================================================
# CAR - DELETE
# =========================================================

def delete_car_done_service(service_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM car_done_services WHERE id = ?",
        (service_id,)
    )
    conn.commit()
    conn.close()


def delete_car_planned_service(service_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM car_planned_services WHERE id = ?",
        (service_id,)
    )
    conn.commit()
    conn.close()


def replace_car_services(done_services, planned_services):
    """
    Полностью заменяет данные в разделах выполненных и планируемых работ.
    Используется для массового импорта из Excel.
    """
    conn = get_connection()

    conn.execute("DELETE FROM car_done_services")
    conn.execute("DELETE FROM car_planned_services")

    if done_services:
        conn.executemany(
            """
            INSERT INTO car_done_services (
                service_name,
                service_cost,
                mileage,
                service_date,
                detail_description,
                work_kind,
                period_type,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.get("service_name", ""),
                    item.get("service_cost", 0),
                    item.get("mileage", 0),
                    item.get("service_date", ""),
                    item.get("detail_description", ""),
                    item.get("work_kind", ""),
                    item.get("period_type", ""),
                    item.get("status", "Выполнено"),
                )
                for item in done_services
            ],
        )

    if planned_services:
        conn.executemany(
            """
            INSERT INTO car_planned_services (
                service_name,
                planned_cost,
                mileage,
                detail_description,
                work_kind,
                period_type,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.get("service_name", ""),
                    item.get("planned_cost", 0),
                    item.get("mileage", 0),
                    item.get("detail_description", ""),
                    item.get("work_kind", ""),
                    item.get("period_type", ""),
                    item.get("status", "Планируется"),
                )
                for item in planned_services
            ],
        )

    conn.commit()
    conn.close()


# =========================================================
# CAR - MOVE BETWEEN SECTIONS
# =========================================================

def move_planned_to_done(service_id, service_date):
    """
    Переносит работу из планируемых в выполненные
    и возвращает id новой записи.
    """

    conn = get_connection()

    item = conn.execute("""
        SELECT *
        FROM car_planned_services
        WHERE id = ?
    """, (service_id,)).fetchone()

    if not item:
        conn.close()
        return None

    cursor = conn.execute("""
        INSERT INTO car_done_services (
            service_name,
            service_cost,
            mileage,
            service_date,
            detail_description,
            work_kind,
            period_type,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item["service_name"],
        0,
        0,
        service_date,
        item["detail_description"],
        item["work_kind"],
        item["period_type"],
        "Выполнено",
    ))

    done_service_id = cursor.lastrowid

    conn.execute(
        "DELETE FROM car_planned_services WHERE id = ?",
        (service_id,)
    )

    conn.commit()
    conn.close()

    return done_service_id

# =========================================================
# CAR - PERIODIC WORKS / NOTIFICATIONS
# =========================================================
def init_car_notification_archive():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS car_notification_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_key TEXT NOT NULL UNIQUE,
            title TEXT,
            status TEXT,
            period_type TEXT,
            detail_description TEXT,
            last_service_date_text TEXT,
            work_kind TEXT,
            archived_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    
def archive_car_notification(
    notification_key,
    title="",
    status="",
    period_type="",
    detail_description="",
    last_service_date_text="",
    work_kind=""
):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO car_notification_archive (
            notification_key,
            title,
            status,
            period_type,
            detail_description,
            last_service_date_text,
            work_kind,
            archived_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        notification_key,
        title,
        status,
        period_type,
        detail_description,
        last_service_date_text,
        work_kind,
    ))
    conn.commit()
    conn.close()
    
def get_archived_car_notifications():
    conn = get_connection()
    rows = conn.execute("""
        SELECT *
        FROM car_notification_archive
        ORDER BY archived_at DESC
    """).fetchall()
    conn.close()
    return rows  
  
def init_car_hidden_notifications_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS car_hidden_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_key TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()
    conn.close()   
     
def hide_car_notification(notification_key):
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO car_hidden_notifications (notification_key)
        VALUES (?)
    """, (notification_key,))
    conn.commit()
    conn.close()


def is_car_notification_hidden(notification_key):
    conn = get_connection()
    item = conn.execute("""
        SELECT id
        FROM car_notification_hidden
        WHERE notification_key = ?
    """, (notification_key,)).fetchone()
    conn.close()
    return item is not None


def get_hidden_notification_keys():
    conn = get_connection()
    rows = conn.execute("""
        SELECT notification_key
        FROM car_hidden_notifications
    """).fetchall()
    conn.close()
    return [row["notification_key"] for row in rows]

def get_periodic_services_for_notifications():
    conn = get_connection()

    done = conn.execute("""
        SELECT
            id,
            service_name,
            mileage,
            detail_description,
            work_kind,
            period_type,
            status,
            service_date,
            'done' AS source_type
        FROM car_done_services
        WHERE period_type IN ('6 мес', '12 мес')
    """).fetchall()

    conn.close()
    return [], done


# =========================================================
# LEGACY CAR NOTIFICATIONS
# =========================================================

def create_car_notification(
    service_name,
    period_value,
    last_service_date,
    mileage_at_service,
    brand,
    status,
):
    """
    Старый отдельный механизм уведомлений.
    Оставлен для совместимости с текущими маршрутами.
    """
    conn = get_connection()
    conn.execute("""
        INSERT INTO car_notifications (
            service_name,
            period_value,
            last_service_date,
            mileage_at_service,
            brand,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        service_name,
        period_value,
        last_service_date,
        mileage_at_service,
        brand,
        status,
    ))
    conn.commit()
    conn.close()


def get_car_notifications():
    conn = get_connection()
    rows = conn.execute("""
        SELECT *
        FROM car_notifications
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return rows

# =========================================================
# SHOOTINGS
# =========================================================

def _format_date_display(date_string):
    if not date_string:
        return ""

    months = {
        "01": "января",
        "02": "февраля",
        "03": "марта",
        "04": "апреля",
        "05": "мая",
        "06": "июня",
        "07": "июля",
        "08": "августа",
        "09": "сентября",
        "10": "октября",
        "11": "ноября",
        "12": "декабря",
    }

    try:
        parsed = datetime.strptime(date_string, "%Y-%m-%d")
        day = parsed.day
        month = months[parsed.strftime("%m")]
        year = parsed.year
        return f"{day} {month} {year}"
    except ValueError:
        return date_string

def _format_money(value):
    value = float(value or 0)
    if value.is_integer():
        return int(value)
    return value


def _prepare_shooting(row):
    if not row:
        return None

    shooting = dict(row)

    price = float(shooting.get("price") or 0)
    prepayment = float(shooting.get("prepayment") or 0)
    remaining_payment = max(price - prepayment, 0)
    duration_hours = float(shooting.get("duration_hours") or 0)

    shooting["price"] = _format_money(price)
    shooting["prepayment"] = _format_money(prepayment)
    shooting["remaining_payment"] = _format_money(remaining_payment)

    if duration_hours.is_integer():
        shooting["duration_hours"] = int(duration_hours)
    else:
        shooting["duration_hours"] = duration_hours

    shooting["price_display"] = _format_money(price)
    shooting["prepayment_display"] = _format_money(prepayment)
    shooting["remaining_display"] = _format_money(remaining_payment)

    shooting["shooting_date_display"] = _format_date_display(
        shooting.get("shooting_date")
    )
    shooting_date = shooting.get("shooting_date")
    shooting["is_archive"] = bool(shooting_date and shooting_date < date.today().isoformat())

    is_paid_to_budget = shooting.get("is_paid_to_budget", 0)
    shooting["is_paid_to_budget"] = int(is_paid_to_budget or 0)

    return shooting

def create_shooting(
    project_name,
    client_name,
    shooting_date,
    shooting_time,
    duration_hours,
    phone,
    price,
    prepayment,
    notes,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO shootings (
            project_name,
            client_name,
            shooting_date,
            shooting_time,
            duration_hours,
            phone,
            price,
            prepayment,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_name,
        client_name,
        shooting_date,
        shooting_time,
        duration_hours,
        phone,
        price,
        prepayment,
        notes,
    ))

    conn.commit()
    shooting_id = cursor.lastrowid
    conn.close()
    return shooting_id


def get_upcoming_shootings():
    conn = get_connection()
    cursor = conn.cursor()

    today = date.today().isoformat()

    cursor.execute("""
        SELECT *
        FROM shootings
        WHERE shooting_date >= ?
        ORDER BY shooting_date ASC, shooting_time ASC
    """, (today,))

    rows = cursor.fetchall()
    conn.close()

    return [_prepare_shooting(row) for row in rows]


def get_archived_shootings():
    conn = get_connection()
    cursor = conn.cursor()

    today = date.today().isoformat()

    cursor.execute("""
        SELECT *
        FROM shootings
        WHERE shooting_date < ?
        ORDER BY shooting_date DESC, shooting_time DESC
    """, (today,))

    rows = cursor.fetchall()
    conn.close()

    return [_prepare_shooting(row) for row in rows]


def get_nearest_shooting():
    conn = get_connection()
    cursor = conn.cursor()

    today = date.today().isoformat()

    cursor.execute("""
        SELECT *
        FROM shootings
        WHERE shooting_date >= ?
        ORDER BY shooting_date ASC, shooting_time ASC
        LIMIT 1
    """, (today,))

    row = cursor.fetchone()
    conn.close()

    return _prepare_shooting(row)


def get_shootings_count():
    conn = get_connection()
    cursor = conn.cursor()

    today = date.today().isoformat()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM shootings
        WHERE shooting_date >= ?
    """, (today,))

    row = cursor.fetchone()
    conn.close()

    return row["total"] if row else 0


def get_shooting_by_id(shooting_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM shootings
        WHERE id = ?
    """, (shooting_id,))

    row = cursor.fetchone()
    conn.close()

    return _prepare_shooting(row)


def update_shooting(
    shooting_id,
    project_name,
    client_name,
    shooting_date,
    shooting_time,
    duration_hours,
    phone,
    price,
    prepayment,
    notes,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE shootings
        SET
            project_name = ?,
            client_name = ?,
            shooting_date = ?,
            shooting_time = ?,
            duration_hours = ?,
            phone = ?,
            price = ?,
            prepayment = ?,
            notes = ?
        WHERE id = ?
    """, (
        project_name,
        client_name,
        shooting_date,
        shooting_time,
        duration_hours,
        phone,
        price,
        prepayment,
        notes,
        shooting_id,
    ))

    conn.commit()
    conn.close()


def delete_shooting(shooting_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM shootings WHERE id = ?", (shooting_id,))

    conn.commit()
    conn.close()
