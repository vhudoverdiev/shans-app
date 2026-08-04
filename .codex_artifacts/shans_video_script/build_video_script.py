from pathlib import Path
import re
import zipfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

PROJECT = Path(r"C:\Users\Владимир\Desktop\Сайты\Shans")
REFERENCE = Path(r"C:\Users\Владимир\Desktop\Сайты\Передача\Презентация Peredacha\Раб.файлы для видео\Сценарий_видеопрезентации_CRM_Передача.docx")
OUTPUT = PROJECT / "Сценарий_видеообзора_CRM_Shans_90сек.docx"
LOGO = PROJECT / "app" / "static" / "logo.png"

BLUE = "2F63F1"
VIOLET = "6941C6"
DARK = "111827"
TEXT = "1F2937"
GRAY = "667085"


def clear_content(paragraph):
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)


def style_run(run, size, color=TEXT, bold=False, italic=False):
    run.font.name = "Calibri"
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:ascii"), "Calibri")
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), "Calibri")
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), "Calibri")
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold
    run.italic = italic
    return run


def set_plain(paragraph, text, size=10, color=TEXT, bold=False, italic=False):
    clear_content(paragraph)
    style_run(paragraph.add_run(text), size, color, bold, italic)


def set_stage(paragraph, text):
    set_plain(paragraph, text, 9, BLUE, True)


def set_heading(paragraph, text):
    set_plain(paragraph, text, 16, BLUE, True)


def set_lead(paragraph, text):
    set_plain(paragraph, text, 10.5, GRAY)


def set_segment(paragraph, timecode, title):
    clear_content(paragraph)
    style_run(paragraph.add_run(f"{timecode}   "), 13, BLUE, True)
    style_run(paragraph.add_run(title), 13, DARK, True)


def set_action(paragraph, text):
    clear_content(paragraph)
    label = style_run(paragraph.add_run("ДЕЙСТВИЯ НА ЭКРАНЕ"), 8.5, BLUE, True)
    label.add_break()
    style_run(paragraph.add_run(text), 10, TEXT)


def set_voice(paragraph, text):
    clear_content(paragraph)
    label = style_run(paragraph.add_run("ТЕКСТ ДИКТОРА"), 8.5, BLUE, True)
    label.add_break()
    style_run(paragraph.add_run(f"«{text}»"), 10, DARK, italic=True)


def set_callout(paragraph, text):
    set_plain(paragraph, text, 12, DARK, True)


doc = Document(REFERENCE)
paras = doc.paragraphs

set_plain(paras[1], "CRM SHANS", 9, BLUE, True)
set_plain(paras[2], "Сценарий видеообзора\nCRM Shans", 30, DARK, True)
set_plain(
    paras[3],
    "Готовый дикторский текст, экранные действия и монтажный лист для видео 1:30. Ровно 45 секунд отведено мобильной версии.",
    12,
    GRAY,
)
set_plain(paras[4], "ЦЕЛЬ ВИДЕООБЗОРА", 9, BLUE, True)
set_plain(
    paras[5],
    "Показать Shans как единую CRM для личных процессов: быстро обозначить возможности на компьютере, уделить половину времени смартфону и завершить сервисами платформы.",
    12,
    DARK,
    True,
)

timeline = doc.tables[0]
times = ["0:00", "0:30", "1:15", "1:30"]
phases = ["Обзор и автор", "Мобильная версия", "Сервисы", "Финальный кадр"]
for column, value in enumerate(times):
    p = timeline.cell(0, column).paragraphs[0]
    set_plain(p, value, 12, BLUE, True)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
for column, value in enumerate(phases):
    p = timeline.cell(1, column).paragraphs[0]
    set_plain(p, value, 9, DARK, True)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

set_stage(paras[7], "ЭТАП 01")
set_heading(paras[8], "Контекст, разработчик и desktop-обзор")
set_lead(paras[9], "За первые 30 секунд объясните назначение Shans, назовите разработчика и покажите главные разделы на большом экране.")

set_segment(paras[10], "0:00-0:10", "Shans в одном предложении")
set_action(paras[11], "Откройте главный экран в desktop-режиме. За первые две секунды покажите логотип, затем дайте быстрый монтаж из расписания, бюджета и проектов.")
set_voice(paras[12], "Shans - это CRM для управления личными процессами. В одном приложении собраны расписание, проекты, финансы, автомобиль, обучение, спорт и питание.")

set_segment(paras[13], "0:10-0:20", "Разработчик проекта")
set_action(paras[14], "На спокойном темном фоне покажите логотип Shans, титр «Разработчик проекта» и имя «Владимир Худовердиев». Не используйте случайный портрет: без согласованной фотографии оставьте типографический кадр.")
set_voice(paras[15], "Разработчик проекта - Владимир Худовердиев. Он собрал Shans как модульную систему, где задачи, данные и уведомления работают в единой логике.")

set_segment(paras[16], "0:20-0:30", "Ключевые разделы на компьютере")
set_action(paras[17], "Последовательно покажите день в календаре, баланс бюджета, уведомления по автомобилю, фото-проекты и центр отчетов. На каждый экран отведите полторы-две секунды.")
set_voice(paras[18], "На компьютере удобно планировать день, вести съемки и проекты, контролировать бюджет, обслуживание автомобиля, отчеты и экспорт данных в Excel.")

set_stage(paras[20], "ЭТАП 02")
set_heading(paras[21], "Мобильная версия: задачи, уведомления и питание")
set_lead(paras[22], "С 0:30 начинается мобильный блок. Запись смартфона занимает 45 секунд суммарно и остается главным визуальным акцентом видео.")

set_segment(paras[23], "0:30-0:42", "PWA и расписание на смартфоне")
set_action(paras[24], "Перейдите на вертикальную запись 9:16. Запустите Shans с иконки на домашнем экране, откройте календарь и покажите создание, перенос и отметку задачи.")
set_voice(paras[25], "Половину обзора уделим мобильной версии. Shans устанавливается как PWA и открывает расписание без лишних переходов. Задачу можно создать, перенести или отметить выполненной.")

set_segment(paras[26], "0:42-0:53", "Push и центр уведомлений")
set_action(paras[27], "Покажите системное push-уведомление, затем откройте встроенный центр уведомлений. Коснитесь события, чтобы перейти к связанной задаче или разделу.")
set_voice(paras[28], "Push-уведомления напоминают о делах, тренировках и обучении. Встроенный центр уведомлений сохраняет события, а Telegram может передавать важные сообщения в CRM.")

set_segment(paras[29], "0:53-1:04", "Питание и быстрый ввод")
set_action(paras[30], "Откройте питание, добавьте продукт через быстрый ввод, покажите поиск по каталогу и итоговые показатели дня. Используйте заранее подготовленные демонстрационные данные.")
set_voice(paras[31], "В разделе питания быстро добавляются продукты и приемы пищи, работает поиск по каталогу, сохраняются калории, белки, жиры, углеводы и динамика веса.")

set_stage(paras[33], "ЭТАП 03")
set_heading(paras[34], "Завершить мобильный блок и показать сервисы")
set_lead(paras[35], "Первые 11 секунд страницы завершают мобильную половину ролика; затем вернитесь к desktop-кадрам для отчетов, безопасности и финала.")

set_segment(paras[36], "1:04-1:15", "Тренировки и обучение на смартфоне")
set_action(paras[37], "Сделайте два коротких вертикальных плана: откройте тренировочный план и результат, затем курс, урок и тест. Переход между разделами - быстрый сдвиг или match cut.")
set_voice(paras[38], "Мобильный раздел тренировок хранит планы и результаты, а обучение - уроки, тесты и прогресс по курсам английского и информационных технологий.")

set_segment(paras[39], "1:15-1:22", "Отчеты и Excel-экспорт")
set_action(paras[40], "Вернитесь к горизонтальной записи. Откройте центр отчетов, затем бюджетный отчет и кнопку экспорта. Подчеркните переход от обзора к проверяемым данным.")
set_voice(paras[41], "На финальном экране покажите отчеты и Excel-экспорт: данные остаются доступными для проверки и анализа.")

set_segment(paras[42], "1:22-1:27", "Безопасность доступа")
set_action(paras[43], "Покажите настройки аккаунта: двухфакторную защиту и управление push-уведомлениями. Не задерживайтесь на QR-кодах, ключах или личных данных.")
set_voice(paras[44], "Авторизация и двухфакторная проверка защищают доступ к данным.")

set_segment(paras[45], "1:27-1:30", "Финальный кадр")
set_action(paras[46], "Затемните интерфейс, выведите логотип Shans по центру и короткий финальный титр. Музыка поднимается на два децибела после последней фразы.")
set_voice(paras[47], "Shans - ключевые процессы в одной системе.")

set_stage(paras[49], "ЭТАП 04")
set_heading(paras[50], "Монтажный пакет")
set_lead(paras[51], "Пакет рассчитан на горизонтальный мастер 16:9 с вертикальными мобильными кадрами внутри аккуратной рамки смартфона.")
set_plain(paras[52], "КЛЮЧЕВОЙ ТИТР", 9, BLUE, True)
set_callout(paras[53], "Shans - ключевые процессы в одной системе.")
set_heading(paras[54], "В пакет входят")

checklist = [
    "сценарий с таймингами, экранными действиями и готовым текстом диктора;",
    "SRT-субтитры и отдельный файл с экранными титрами;",
    "монтажный лист CSV с форматом кадра, переходами и звуковыми акцентами;",
    "логотип и отобранные desktop/mobile-скриншоты из локальных материалов Shans;",
    "техническое задание: 1920x1080, 25 или 30 fps, без личных данных и системных секретов.",
]
for index, text in enumerate(checklist, start=55):
    set_plain(paras[index], text, 11, TEXT)

set_plain(paras[60], "ТЕХНИЧЕСКИЕ ПАРАМЕТРЫ", 9, BLUE, True)
set_callout(
    paras[61],
    "Мобильная версия занимает ровно 0:30-1:15. Вертикальный экран размещайте по центру или справа, занимая 38-42% ширины кадра. Субтитры держите в безопасной зоне, музыку - примерно на -24 dB под голосом, интерфейсные клики - на -18 dB. Перед записью замените персональные данные демонстрационными.",
)

header = doc.sections[0].header.paragraphs[0]
set_plain(header, "SHANS  ·  СЦЕНАРИЙ ВИДЕООБЗОРА", 8.5, GRAY, True)
footer = doc.sections[0].footer.paragraphs[0]
if footer.runs:
    footer.runs[0].text = "CRM Shans"

doc.core_properties.title = "Сценарий видеообзора CRM Shans на 90 секунд"
doc.core_properties.subject = "Сценарий, монтажный лист и мобильный блок"
doc.core_properties.author = "Владимир Худовердиев"
doc.core_properties.keywords = "Shans, CRM, видеообзор, мобильная версия, монтаж"

doc.save(OUTPUT)

with zipfile.ZipFile(OUTPUT, "r") as archive:
    parts = {name: archive.read(name) for name in archive.namelist()}

for name, data in list(parts.items()):
    if name.endswith(".xml"):
        text = data.decode("utf-8")
        text = re.sub("568F12", BLUE, text, flags=re.IGNORECASE)
        text = re.sub("8DD62C", BLUE, text, flags=re.IGNORECASE)
        text = re.sub("F3FAE9", "EDF4FF", text, flags=re.IGNORECASE)
        text = re.sub("DDE7D2", "C7D7FE", text, flags=re.IGNORECASE)
        parts[name] = text.encode("utf-8")

if "word/media/image1.png" not in parts:
    raise RuntimeError("Reference logo image part was not preserved")
parts["word/media/image1.png"] = LOGO.read_bytes()

with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name, data in parts.items():
        archive.writestr(name, data)

print(OUTPUT)
