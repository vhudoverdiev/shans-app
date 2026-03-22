from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def build_budget_excel(entries, summary, current_balance, selected_month):
    wb = Workbook()
    ws = wb.active
    ws.title = "Бюджет"

    title_fill = PatternFill("solid", fgColor="2563EB")
    section_fill = PatternFill("solid", fgColor="EEF2FF")
    header_fill = PatternFill("solid", fgColor="E2E8F0")
    income_fill = PatternFill("solid", fgColor="ECFDF3")
    expense_fill = PatternFill("solid", fgColor="FEF2F2")

    white_font = Font(color="FFFFFF", bold=True, size=14)
    title_font = Font(bold=True, size=16)
    bold_font = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Заголовок
    ws.merge_cells("A1:D1")
    ws["A1"] = f"Бюджет за месяц: {selected_month}"
    ws["A1"].font = title_font
    ws["A1"].alignment = center
    ws["A1"].fill = title_fill
    ws["A1"].font = white_font

    # Сводка
    ws.merge_cells("A3:D3")
    ws["A3"] = "Сводка"
    ws["A3"].font = bold_font
    ws["A3"].fill = section_fill
    ws["A3"].alignment = left

    summary_rows = [
        ("Доход за месяц", summary["income"]),
        ("Расход за месяц", summary["expense"]),
        ("Баланс за месяц", summary["balance"]),
        ("Текущий баланс", current_balance),
    ]

    row = 4
    for label, value in summary_rows:
        ws[f"A{row}"] = label
        ws[f"B{row}"] = int(round(value))
        ws[f"A{row}"].font = bold_font
        ws[f"A{row}"].border = border
        ws[f"B{row}"].border = border
        ws[f"B{row}"].number_format = '# ##0 "Р"'
        row += 1

    # Таблица операций
    table_start = row + 2
    ws.merge_cells(f"A{table_start}:D{table_start}")
    ws[f"A{table_start}"] = "Операции"
    ws[f"A{table_start}"].font = bold_font
    ws[f"A{table_start}"].fill = section_fill
    ws[f"A{table_start}"].alignment = left

    headers_row = table_start + 1
    headers = ["Месяц", "Тип", "Категория", "Сумма"]

    for col_index, header in enumerate(headers, start=1):
        cell = ws.cell(row=headers_row, column=col_index)
        cell.value = header
        cell.font = bold_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border

    data_row = headers_row + 1
    for entry in entries:
        ws.cell(row=data_row, column=1, value=entry["month_name"])
        ws.cell(row=data_row, column=2, value=entry["entry_type"])
        ws.cell(row=data_row, column=3, value=entry["category"])

        amount_cell = ws.cell(row=data_row, column=4, value=int(round(entry["amount"])))
        amount_cell.number_format = '# ##0 "Р"'

        for col in range(1, 5):
            cell = ws.cell(row=data_row, column=col)
            cell.border = border
            cell.alignment = left

        if entry["entry_type"] == "Доход":
            for col in range(1, 5):
                ws.cell(row=data_row, column=col).fill = income_fill
        else:
            for col in range(1, 5):
                ws.cell(row=data_row, column=col).fill = expense_fill

        data_row += 1

    # Ширина колонок
    widths = {
        1: 18,
        2: 16,
        3: 28,
        4: 16,
    }

    for col_index, width in widths.items():
        ws.column_dimensions[get_column_letter(col_index)].width = width

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output