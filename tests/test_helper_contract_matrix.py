import unittest
from datetime import date, datetime, time

from app import format_money
from app.access_control import section_for_endpoint
from app.routes import (
    _add_months,
    _collect_budget_categories,
    _extract_key_values,
    _format_shooting_date,
    _format_shooting_time,
    _get_period_months,
    _get_shooting_form_data,
    _humanize_log_line,
    _is_valid_contact_value,
    _is_valid_phone_number,
    _normalize_excel_header,
    _parse_datetime_local,
    _parse_excel_date,
    _parse_excel_full_date,
    _parse_excel_number,
    _parse_excel_time,
    _parse_log_line,
    _parse_non_negative_number,
    _parse_selected_ids,
    _prepare_shooting_row,
    _resolve_budget_category,
)


OTHER_CATEGORY = "\u0414\u0440\u0443\u0433\u043e\u0435"
CAR_CATEGORY = "\u0410\u0432\u0442\u043e"
FOOD_CATEGORY = "\u0415\u0434\u0430"
SIX_MONTHS = "6 \u043c\u0435\u0441"
TWELVE_MONTHS = "12 \u043c\u0435\u0441"


class HelperContractMatrixTests(unittest.TestCase):
    pass


GENERATED_TEST_LIMIT = 100
generated_test_count = 0


def _safe_name(value):
    text = "".join(ch if ch.isalnum() else "_" for ch in str(value).lower())
    return "_".join(part for part in text.split("_") if part)[:80] or "empty"


def _add_case(name, assertion):
    global generated_test_count
    if generated_test_count >= GENERATED_TEST_LIMIT:
        return

    def test_method(self):
        assertion(self)

    setattr(HelperContractMatrixTests, f"test_{name}", test_method)
    generated_test_count += 1


def _assert_equal_case(callable_, expected):
    def assertion(test_case):
        test_case.assertEqual(callable_(), expected)

    return assertion


def _assert_true_case(callable_):
    def assertion(test_case):
        test_case.assertTrue(callable_())

    return assertion


def _assert_false_case(callable_):
    def assertion(test_case):
        test_case.assertFalse(callable_())

    return assertion


case_count = 0

FORMAT_MONEY_CASES = [
    ("none", None, "0 \u0420"),
    ("empty_string", "", "0 \u0420"),
    ("text", "not-money", "0 \u0420"),
    ("zero", 0, "0 \u0420"),
    ("small_integer", 42, "42 \u0420"),
    ("rounds_down", 42.4, "42 \u0420"),
    ("rounds_up", 42.6, "43 \u0420"),
    ("negative", -12.2, "-12 \u0420"),
    ("thousands", 1234567, "1 234 567 \u0420"),
    ("numeric_string", "999.6", "1 000 \u0420"),
    ("comma_string_is_rejected", "12,5", "0 \u0420"),
    ("boolean_true", True, "1 \u0420"),
]
for label, value, expected in FORMAT_MONEY_CASES:
    _add_case(
        f"format_money_{label}",
        _assert_equal_case(lambda value=value: format_money(value), expected),
    )
    case_count += 1


PERIOD_CASES = [
    ("six_months", SIX_MONTHS, 6),
    ("twelve_months", TWELVE_MONTHS, 12),
    ("empty", "", 0),
    ("unknown", "24 months", 0),
]
for label, value, expected in PERIOD_CASES:
    _add_case(
        f"period_months_{label}",
        _assert_equal_case(lambda value=value: _get_period_months(value), expected),
    )
    case_count += 1


ADD_MONTHS_CASES = [
    ("same_month_when_zero", datetime(2026, 1, 20), 0, datetime(2026, 1, 1)),
    ("simple_increment", datetime(2026, 1, 20), 1, datetime(2026, 2, 1)),
    ("crosses_year", datetime(2026, 11, 30), 3, datetime(2027, 2, 1)),
    ("december_to_january", datetime(2026, 12, 1), 1, datetime(2027, 1, 1)),
    ("large_period", datetime(2026, 5, 9), 24, datetime(2028, 5, 1)),
    ("negative_period", datetime(2026, 5, 9), -1, datetime(2026, 4, 1)),
]
for label, base_date, months, expected in ADD_MONTHS_CASES:
    _add_case(
        f"add_months_{label}",
        _assert_equal_case(lambda base_date=base_date, months=months: _add_months(base_date, months), expected),
    )
    case_count += 1


SELECTED_IDS_CASES = [
    ("empty", "", []),
    ("none", None, []),
    ("single", "7", [7]),
    ("trims_spaces", " 1 , 2 ", [1, 2]),
    ("ignores_words", "1,two,3", [1, 3]),
    ("ignores_negative", "-1,2", [2]),
    ("keeps_zero", "0,5", [0, 5]),
    ("ignores_decimal", "1.5,2", [2]),
]
for label, raw_value, expected in SELECTED_IDS_CASES:
    _add_case(
        f"parse_selected_ids_{label}",
        _assert_equal_case(lambda raw_value=raw_value: _parse_selected_ids(raw_value), expected),
    )
    case_count += 1


PHONE_VALID_CASES = [
    ("empty", ""),
    ("russian_plus", "+79991234567"),
    ("russian_spaces", "+7 999 123 45 67"),
    ("parentheses_and_dash", "+7 (999) 123-45-67"),
    ("seven_digits", "1234567"),
    ("fifteen_digits", "123456789012345"),
]
for label, phone_value in PHONE_VALID_CASES:
    _add_case(
        f"phone_accepts_{label}",
        _assert_true_case(lambda phone_value=phone_value: _is_valid_phone_number(phone_value)),
    )
    case_count += 1


PHONE_INVALID_CASES = [
    ("too_short", "123456"),
    ("too_long", "1234567890123456"),
    ("letters", "+7999abc4567"),
    ("email", "client@example.com"),
    ("url", "https://example.com"),
    ("double_plus", "++79991234567"),
]
for label, phone_value in PHONE_INVALID_CASES:
    _add_case(
        f"phone_rejects_{label}",
        _assert_false_case(lambda phone_value=phone_value: _is_valid_phone_number(phone_value)),
    )
    case_count += 1


CONTACT_VALID_CASES = [
    ("empty", ""),
    ("phone", "+79991234567"),
    ("https_url", "https://example.com/client"),
    ("http_url", "http://example.com/client"),
    ("www_url", "www.example.com/client"),
    ("telegram_link", "t.me/client_name"),
    ("telegram_handle", "@client_name"),
    ("email", "client.name@example.com"),
]
for label, contact_value in CONTACT_VALID_CASES:
    _add_case(
        f"contact_accepts_{label}",
        _assert_true_case(lambda contact_value=contact_value: _is_valid_contact_value(contact_value)),
    )
    case_count += 1


CONTACT_INVALID_CASES = [
    ("too_short_handle", "@ab"),
    ("plain_text", "just a contact"),
    ("ftp_url", "ftp://example.com"),
    ("bad_email", "client@example"),
    ("bad_phone_with_letter", "+7999x123456"),
    ("too_long", "a" * 256),
]
for label, contact_value in CONTACT_INVALID_CASES:
    _add_case(
        f"contact_rejects_{label}",
        _assert_false_case(lambda contact_value=contact_value: _is_valid_contact_value(contact_value)),
    )
    case_count += 1


NON_NEGATIVE_NUMBER_CASES = [
    ("none", None, (None, None)),
    ("empty", "", (None, None)),
    ("zero", "0", (0.0, None)),
    ("integer", "15", (15.0, None)),
    ("float", "15.5", (15.5, None)),
    ("spaces", " 7 ", (7.0, None)),
]
for label, value, expected in NON_NEGATIVE_NUMBER_CASES:
    _add_case(
        f"non_negative_number_{label}",
        _assert_equal_case(lambda value=value: _parse_non_negative_number(value, "Amount"), expected),
    )
    case_count += 1


NON_NEGATIVE_ERROR_CASES = [
    ("negative", "-1", "Amount"),
    ("text", "abc", "Amount"),
]
for label, value, expected_fragment in NON_NEGATIVE_ERROR_CASES:
    def assertion(test_case, value=value, expected_fragment=expected_fragment):
        parsed_value, error = _parse_non_negative_number(value, "Amount")
        test_case.assertIsNone(parsed_value)
        test_case.assertIn(expected_fragment, error)

    _add_case(f"non_negative_number_rejects_{label}", assertion)
    case_count += 1


HEADER_CASES = [
    ("none", None, ""),
    ("empty", "", ""),
    ("trims", "  Amount  ", "amount"),
    ("lowercase", "Service_Name", "service_name"),
    ("number", 123, "123"),
]
for label, value, expected in HEADER_CASES:
    _add_case(
        f"normalize_excel_header_{label}",
        _assert_equal_case(lambda value=value: _normalize_excel_header(value), expected),
    )
    case_count += 1


EXCEL_NUMBER_CASES = [
    ("none", None, 0),
    ("empty", "", 0),
    ("integer", 12, 12),
    ("float", 12.5, 12.5),
    ("comma_decimal", "12,5", 12.5),
    ("spaces", " 8.25 ", 8.25),
    ("invalid", "oops", 0),
]
for label, value, expected in EXCEL_NUMBER_CASES:
    _add_case(
        f"parse_excel_number_{label}",
        _assert_equal_case(lambda value=value: _parse_excel_number(value), expected),
    )
    case_count += 1


EXCEL_DATE_CASES = [
    ("none", None, ""),
    ("datetime", datetime(2099, 8, 5, 14, 30), "2099-08"),
    ("date", date(2099, 8, 5), "2099-08"),
    ("year_month", "2099-08", "2099-08"),
    ("full_date", "2099-08-05", "2099-08"),
    ("russian_date", "05.08.2099", "2099-08"),
    ("month_year", "08.2099", "2099-08"),
    ("unknown_text", "August 2099", "August 2099"),
]
for label, value, expected in EXCEL_DATE_CASES:
    _add_case(
        f"parse_excel_date_{label}",
        _assert_equal_case(lambda value=value: _parse_excel_date(value), expected),
    )
    case_count += 1


EXCEL_FULL_DATE_CASES = [
    ("none", None, ""),
    ("datetime", datetime(2099, 8, 5, 14, 30), "2099-08-05"),
    ("date", date(2099, 8, 5), "2099-08-05"),
    ("year_month", "2099-08", "2099-08-01"),
    ("month_year", "08.2099", "2099-08-01"),
    ("russian_date", "05.08.2099", "2099-08-05"),
    ("unknown_text", "tomorrow", "tomorrow"),
]
for label, value, expected in EXCEL_FULL_DATE_CASES:
    _add_case(
        f"parse_excel_full_date_{label}",
        _assert_equal_case(lambda value=value: _parse_excel_full_date(value), expected),
    )
    case_count += 1


EXCEL_TIME_CASES = [
    ("none", None, ""),
    ("empty", "", ""),
    ("datetime", datetime(2099, 8, 5, 14, 30), "14:30"),
    ("time", time(9, 5), "09:05"),
    ("date_is_not_time", date(2099, 8, 5), ""),
    ("hour_minute", "8:05", "08:05"),
    ("hour_minute_second", "08:05:30", "08:05"),
    ("unknown_text", "morning", "morning"),
]
for label, value, expected in EXCEL_TIME_CASES:
    _add_case(
        f"parse_excel_time_{label}",
        _assert_equal_case(lambda value=value: _parse_excel_time(value), expected),
    )
    case_count += 1


DATETIME_LOCAL_CASES = [
    ("empty", "", None),
    ("minute_precision", "2099-08-05T14:30", datetime(2099, 8, 5, 14, 30)),
    ("second_precision", "2099-08-05T14:30:59", datetime(2099, 8, 5, 14, 30, 59)),
    ("space_separator_rejected", "2099-08-05 14:30", None),
]
for label, value, expected in DATETIME_LOCAL_CASES:
    _add_case(
        f"parse_datetime_local_{label}",
        _assert_equal_case(lambda value=value: _parse_datetime_local(value), expected),
    )
    case_count += 1


def _shooting_form_assertion(expected):
    def assertion(test_case):
        form = {
            "client_name": "  Anna  ",
            "project_name": " Wedding ",
            "shooting_date": " 2099-08-05 ",
            "shooting_time": " 14:30 ",
            "location": " Studio ",
            "package_name": " Full ",
            "status": " ",
            "phone": " +79991234567 ",
            "price": " 50000 ",
            "prepayment": " 10000 ",
            "notes": " Bring dress ",
        }
        test_case.assertEqual(_get_shooting_form_data(form)[expected[0]], expected[1])

    return assertion


SHOOTING_FORM_CASES = [
    ("client_name", "Anna"),
    ("project_name", "Wedding"),
    ("shooting_date", "2099-08-05"),
    ("shooting_time", "14:30"),
    ("location", "Studio"),
    ("package_name", "Full"),
    ("phone", "+79991234567"),
    ("price", "50000"),
    ("prepayment", "10000"),
    ("notes", "Bring dress"),
]
for field_name, expected in SHOOTING_FORM_CASES:
    _add_case(
        f"shooting_form_trims_{field_name}",
        _shooting_form_assertion((field_name, expected)),
    )
    case_count += 1


PREPARE_SHOOTING_CASES = [
    ("remaining_payment", {"price": "50000", "prepayment": "10000", "shooting_date": "2099-08-05"}, "remaining_payment", 40000.0),
    ("overpayment_caps_remaining", {"price": "10000", "prepayment": "15000", "shooting_date": "2099-08-05"}, "remaining_payment", 0),
    ("bad_price_defaults_zero", {"price": "bad", "prepayment": "10", "shooting_date": "2099-08-05"}, "price", 0),
    ("bad_prepayment_defaults_zero", {"price": "10", "prepayment": "bad", "shooting_date": "2099-08-05"}, "prepayment", 0),
    ("time_display_missing", {"price": 0, "prepayment": 0, "shooting_date": "2099-08-05", "shooting_time": ""}, "shooting_time_display", "\u0411\u0435\u0437 \u0432\u0440\u0435\u043c\u0435\u043d\u0438"),
]
for label, row, field_name, expected in PREPARE_SHOOTING_CASES:
    _add_case(
        f"prepare_shooting_row_{label}",
        _assert_equal_case(lambda row=row, field_name=field_name: _prepare_shooting_row(row)[field_name], expected),
    )
    case_count += 1


SHOOTING_FORMAT_CASES = [
    ("empty_date", lambda: _format_shooting_date(""), "\u2014"),
    ("invalid_date_passthrough", lambda: _format_shooting_date("not-a-date"), "not-a-date"),
    ("time_value", lambda: _format_shooting_time("14:30"), "14:30"),
    ("empty_time", lambda: _format_shooting_time(""), "\u0411\u0435\u0437 \u0432\u0440\u0435\u043c\u0435\u043d\u0438"),
]
for label, callable_, expected in SHOOTING_FORMAT_CASES:
    _add_case(
        f"shooting_format_{label}",
        _assert_equal_case(callable_, expected),
    )
    case_count += 1


BUDGET_CATEGORY_CASES = [
    ("known_category", {"category": f" {CAR_CATEGORY} ", "custom_category": " Repairs "}, CAR_CATEGORY),
    ("custom_category", {"category": OTHER_CATEGORY, "custom_category": " Repairs "}, "Repairs"),
    ("empty_custom_category", {"category": OTHER_CATEGORY, "custom_category": " "}, ""),
]
for label, form, expected in BUDGET_CATEGORY_CASES:
    _add_case(
        f"budget_category_{label}",
        _assert_equal_case(lambda form=form: _resolve_budget_category(form), expected),
    )
    case_count += 1


def _budget_categories_assertion(index, expected):
    def assertion(test_case):
        categories = _collect_budget_categories(
            [
                {"category": "Travel"},
                {"category": FOOD_CATEGORY},
                {"category": "Travel"},
                {"category": "  "},
            ]
        )
        test_case.assertEqual(categories[index], expected)
        test_case.assertEqual(categories.count("Travel"), 1)

    return assertion


BUDGET_CATEGORIES_CASES = [
    ("base_auto_first", 0, CAR_CATEGORY),
    ("base_food_second", 1, FOOD_CATEGORY),
    ("custom_after_base", 2, "Travel"),
    ("other_last", -1, OTHER_CATEGORY),
]
for label, index, expected in BUDGET_CATEGORIES_CASES:
    _add_case(
        f"budget_categories_{label}",
        _budget_categories_assertion(index, expected),
    )
    case_count += 1


LOG_PARSE_CASES = [
    ("plain_line_level_empty", "unstructured message", "level", ""),
    ("plain_line_message_kept", "unstructured message", "message", "unstructured message"),
    ("structured_timestamp", "2099-08-05 14:30:00,123 INFO [audit] event=user_login user=admin", "timestamp", "2099-08-05 14:30:00,123"),
    ("structured_level", "2099-08-05 14:30:00,123 WARNING [auth] Failed login username=admin", "level", "WARNING"),
    ("structured_logger", "2099-08-05 14:30:00,123 WARNING [auth] Failed login username=admin", "logger", "auth"),
    ("structured_message", "2099-08-05 14:30:00,123 INFO [audit] event=user_login user=admin", "message", "event=user_login user=admin"),
]
for label, raw_line, field_name, expected in LOG_PARSE_CASES:
    _add_case(
        f"log_parse_{label}",
        _assert_equal_case(lambda raw_line=raw_line, field_name=field_name: _parse_log_line(raw_line)[field_name], expected),
    )
    case_count += 1


KEY_VALUE_CASES = [
    ("simple_value", "event=user_login user=admin", "user", "admin"),
    ("quoted_value", "path='/budget/manage' user=admin", "path", "/budget/manage"),
    ("double_quoted_value", 'user_agent="Mozilla Firefox"', "user_agent", "Mozilla Firefox"),
    ("plain_message_removed", "Failed login username=admin ip=127.0.0.1", "short", "Failed login"),
]
for label, message, key, expected in KEY_VALUE_CASES:
    def assertion(test_case, message=message, key=key, expected=expected):
        pairs, short_message = _extract_key_values(message)
        actual = short_message if key == "short" else pairs[key]
        test_case.assertEqual(actual, expected)

    _add_case(f"extract_key_values_{label}", assertion)
    case_count += 1


HUMANIZE_LOG_CASES = [
    ("failed_login", "2099-08-05 14:30:00,123 WARNING [auth] Failed login username=admin", "\u0432\u0445\u043e\u0434"),
    ("rate_limit", "2099-08-05 14:30:00,123 WARNING [auth] Login rate limit triggered username=admin", "\u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u0435"),
    ("suspicious", "2099-08-05 14:30:00,123 WARNING [logging_setup] Suspicious HTTP response status=403", "\u043f\u043e\u0434\u043e\u0437\u0440\u0438\u0442\u0435\u043b"),
    ("generic", "2099-08-05 14:30:00,123 INFO [app] Background job finished duration=1", "Background job finished"),
]
for label, raw_line, expected_fragment in HUMANIZE_LOG_CASES:
    _add_case(
        f"humanize_log_{label}",
        _assert_true_case(lambda raw_line=raw_line, expected_fragment=expected_fragment: expected_fragment in _humanize_log_line(raw_line)),
    )
    case_count += 1


SECTION_ENDPOINT_CASES = [
    ("budget_home", "budget", "budget"),
    ("budget_export", "budget_export", "budget"),
    ("car_manage", "car_manage", "car"),
    ("car_notifications", "car_notifications", "car"),
    ("schedule", "planner.schedule", "schedule"),
    ("schedule_export", "planner.export_schedule", "schedule"),
    ("shootings_add", "shootings_add", "shootings"),
    ("shootings_bulk", "shootings_archive_delete_all", "shootings"),
    ("photo_project_detail", "planner.photo_project_detail", "photo_projects"),
    ("photo_project_booking", "planner.create_photo_project_booking", "photo_projects"),
    ("scenarios", "scenarios", "scenarios"),
    ("scenario_toggle", "scenario_toggle_status", "scenarios"),
    ("study", "learning.study_hub", "study"),
    ("english_day", "learning.english_day", "study"),
    ("workouts", "workouts.index", "workouts"),
    ("workout_result", "workouts.create_result", "workouts"),
    ("weight_plan", "workouts.save_weight_plan", "workouts"),
    ("nutrition", "nutrition.index", "nutrition"),
    ("nutrition_entry", "nutrition.create_entry", "nutrition"),
    ("system_endpoint", "login", None),
    ("unknown_endpoint", "unknown.endpoint", None),
]
for label, endpoint, expected in SECTION_ENDPOINT_CASES:
    _add_case(
        f"section_for_endpoint_{label}",
        _assert_equal_case(lambda endpoint=endpoint: section_for_endpoint(endpoint), expected),
    )
    case_count += 1


assert generated_test_count == 100, f"expected exactly 100 generated tests, got {generated_test_count}"


if __name__ == "__main__":
    unittest.main()
