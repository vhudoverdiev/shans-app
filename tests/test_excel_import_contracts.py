import unittest
from datetime import date, datetime, time
from io import BytesIO

from openpyxl import Workbook

from app.routes import (
    _parse_budget_excel,
    _parse_car_excel,
    _parse_excel_full_date,
    _parse_excel_number,
    _parse_excel_time,
    _parse_schedule_excel,
    _parse_shootings_excel,
)


class MemoryUpload:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload


def make_workbook(rows):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return MemoryUpload(output.getvalue())


class ExcelImportContractTests(unittest.TestCase):
    def test_low_level_excel_parsers_normalize_numbers_dates_and_times(self):
        self.assertEqual(_parse_excel_number("12,75"), 12.75)
        self.assertEqual(_parse_excel_number("bad input"), 0)
        self.assertEqual(_parse_excel_full_date("05.08.2099"), "2099-08-05")
        self.assertEqual(_parse_excel_full_date("08.2099"), "2099-08-01")
        self.assertEqual(_parse_excel_full_date(date(2099, 8, 6)), "2099-08-06")
        self.assertEqual(_parse_excel_time(datetime(2099, 8, 5, 14, 30)), "14:30")
        self.assertEqual(_parse_excel_time(time(9, 5)), "09:05")
        self.assertEqual(_parse_excel_time(date(2099, 8, 5)), "")

    def test_budget_import_parses_rows_skips_empty_rows_and_requires_complete_records(self):
        upload = make_workbook(
            [
                ["month_name", "entry_type", "category", "amount"],
                ["January", "Income", "Salary", "100000,90"],
                [None, None, None, None],
                ["January", "Expense", "Rent", 45000.2],
            ]
        )

        entries = _parse_budget_excel(upload)

        self.assertEqual(entries, [
            {
                "month_name": "January",
                "entry_type": "Income",
                "category": "Salary",
                "amount": 100000,
            },
            {
                "month_name": "January",
                "entry_type": "Expense",
                "category": "Rent",
                "amount": 45000,
            },
        ])

        with self.assertRaises(ValueError):
            _parse_budget_excel(make_workbook([["month_name", "entry_type", "category"], ["January", "Income", "Salary"]]))

        with self.assertRaises(ValueError):
            _parse_budget_excel(make_workbook([["month_name", "entry_type", "category", "amount"], ["January", "", "Salary", 1]]))

    def test_car_import_splits_done_and_planned_services_without_losing_details(self):
        upload = make_workbook(
            [
                ["service_name", "detail_description", "period_type", "status", "service_date", "mileage", "service_cost"],
                ["Oil change", "Engine oil", "6 months", "", "2026-02-15", "12000", "3500,5"],
                ["Brake inspection", "Pads", "12 months", "planned", "", 15000, 0],
                ["", "ignored", "", "", "", "", ""],
            ]
        )

        done_services, planned_services = _parse_car_excel(upload)

        self.assertEqual(len(done_services), 1)
        self.assertEqual(done_services[0]["service_name"], "Oil change")
        self.assertEqual(done_services[0]["service_date"], "2026-02")
        self.assertEqual(done_services[0]["mileage"], 12000.0)
        self.assertEqual(done_services[0]["service_cost"], 3500.5)
        self.assertEqual(done_services[0]["detail_description"], "Engine oil")
        self.assertEqual(len(planned_services), 1)
        self.assertEqual(planned_services[0]["service_name"], "Brake inspection")
        self.assertEqual(planned_services[0]["planned_cost"], 0)
        self.assertEqual(planned_services[0]["mileage"], 15000)

    def test_car_import_rejects_file_without_service_name_header(self):
        with self.assertRaises(ValueError):
            _parse_car_excel(make_workbook([["description", "mileage"], ["Oil", 1000]]))

    def test_shootings_import_normalizes_optional_fields_and_rejects_partial_rows(self):
        upload = make_workbook(
            [
                [
                    "project_name",
                    "client_name",
                    "shooting_date",
                    "shooting_time",
                    "duration_hours",
                    "phone",
                    "price",
                    "prepayment",
                    "notes",
                ],
                ["Wedding", "Anna", "10.08.2099", time(14, 30), "", "+70000000000", "50000,5", 10000, "Outdoor"],
                [None, None, None, None, None, None, None, None, None],
            ]
        )

        shootings = _parse_shootings_excel(upload)

        self.assertEqual(len(shootings), 1)
        self.assertEqual(shootings[0]["project_name"], "Wedding")
        self.assertEqual(shootings[0]["client_name"], "Anna")
        self.assertEqual(shootings[0]["shooting_date"], "2099-08-10")
        self.assertEqual(shootings[0]["shooting_time"], "14:30")
        self.assertEqual(shootings[0]["duration_hours"], 1)
        self.assertEqual(shootings[0]["price"], 50000.5)
        self.assertEqual(shootings[0]["prepayment"], 10000)

        with self.assertRaises(ValueError):
            _parse_shootings_excel(make_workbook([["project_name", "client_name", "shooting_date"], ["Wedding", "", "2099-08-10"]]))

    def test_schedule_import_normalizes_dates_flags_statuses_and_defaults_type(self):
        upload = make_workbook(
            [
                ["title", "task_date", "start_time", "description", "is_important", "range_end_date", "status", "task_type"],
                ["Prepare location", "12.08.2099", time(9, 15), "Checklist", "yes", "2099-08", "done", ""],
                ["Cancel booking", date(2099, 8, 13), "", "", "no", "", "cancelled", "Work"],
            ]
        )

        tasks = _parse_schedule_excel(upload)

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["title"], "Prepare location")
        self.assertEqual(tasks[0]["task_date"], "2099-08-12")
        self.assertEqual(tasks[0]["start_time"], "09:15")
        self.assertEqual(tasks[0]["description"], "Checklist")
        self.assertEqual(tasks[0]["is_important"], 1)
        self.assertEqual(tasks[0]["range_end_date"], "2099-08-01")
        self.assertEqual(tasks[0]["status"], "done")
        self.assertTrue(tasks[0]["task_type"])
        self.assertEqual(tasks[1]["task_date"], "2099-08-13")
        self.assertEqual(tasks[1]["status"], "cancelled")
        self.assertEqual(tasks[1]["task_type"], "Work")

    def test_schedule_import_rejects_missing_headers_and_incomplete_task_rows(self):
        with self.assertRaises(ValueError):
            _parse_schedule_excel(make_workbook([["title"], ["Task"]]))

        with self.assertRaises(ValueError):
            _parse_schedule_excel(make_workbook([["title", "task_date"], ["Task without date", ""]]))


if __name__ == "__main__":
    unittest.main()
