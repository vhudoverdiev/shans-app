from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter


from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from io import BytesIO


def build_budget_excel(entries, summary=None, current_balance=None, selected_month=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Бюджет"

    # ======================
    # Заголовок
    # ======================
    title = f"Бюджет за {selected_month}" if selected_month else "Бюджет"
    ws["A1"] = title
    ws["A1"].font = Font(size=14, bold=True)

    # ======================
    # Сводка
    # ======================
    row = 3

    if summary:
        ws[f"A{row}"] = "Доход"
        ws[f"B{row}"] = summary.get("income", 0)

        ws[f"A{row+1}"] = "Расход"
        ws[f"B{row+1}"] = summary.get("expense", 0)

        ws[f"A{row+2}"] = "Баланс"
        ws[f"B{row+2}"] = summary.get("balance", 0)

        if current_balance is not None:
            ws[f"A{row+3}"] = "Текущий баланс"
            ws[f"B{row+3}"] = current_balance

        row += 5

    # ======================
    # Заголовки таблицы
    # ======================
    headers = ["Месяц", "Тип", "Категория", "Сумма"]

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col_num)
        cell.value = header
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    row += 1

    # ======================
    # Данные
    # ======================
    for entry in entries:
        ws.cell(row=row, column=1).value = entry["month_name"]
        ws.cell(row=row, column=2).value = entry["entry_type"]
        ws.cell(row=row, column=3).value = entry["category"]
        ws.cell(row=row, column=4).value = entry["amount"]
        row += 1

    # ======================
    # Автоширина колонок
    # ======================
    column_widths = {
        "A": 15,
        "B": 15,
        "C": 20,
        "D": 15,
    }

    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width

    # ======================
    # Сохранение в память
    # ======================
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return output