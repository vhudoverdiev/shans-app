from __future__ import annotations

import os
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas

content_spec = importlib.util.spec_from_file_location(
    "it_course_content_for_presentations", ROOT / "app" / "it_course_content.py"
)
if content_spec is None or content_spec.loader is None:
    raise RuntimeError("Cannot load IT course content")
content_module = importlib.util.module_from_spec(content_spec)
content_spec.loader.exec_module(content_module)
IT_LESSONS = content_module.IT_LESSONS


OUT_DIR = ROOT / "app" / "static" / "presentations" / "python-basics"
FONT_PATH = Path(os.environ.get("IT_PRESENTATION_FONT", r"C:\Windows\Fonts\arial.ttf"))
PAGE_SIZE = landscape((960, 540))
BLUE = colors.HexColor("#2563eb")
DARK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
SOFT = colors.HexColor("#eff6ff")
GREEN = colors.HexColor("#16a34a")
VIOLET = colors.HexColor("#7c3aed")
TOTAL_SLIDES = 30


def _safe(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_code(code: str, start: int = 0, count: int = 7) -> str:
    lines = (code or "").splitlines()
    selected = lines[start:start + count]
    if not selected:
        selected = ["# Небольшой пример по теме появится здесь"]
    return "<br/>".join(_safe(line) or "&nbsp;" for line in selected)


def _wrap(canvas_obj, text, x, y, width, style, max_height=None):
    paragraph = Paragraph(_safe(text), style)
    available_height = max_height or 420
    paragraph_width, paragraph_height = paragraph.wrap(width, available_height)
    paragraph.drawOn(canvas_obj, x, y - paragraph_height)
    return y - paragraph_height


def _bullet_list(canvas_obj, items, x, y, width, style, gap=8):
    current_y = y
    for item in items:
        current_y = _wrap(canvas_obj, f"• {item}", x, current_y, width, style)
        current_y -= gap
    return current_y


def _start_slide(canvas_obj, lesson, number, label):
    canvas_obj.setFillColor(SOFT)
    canvas_obj.rect(0, 0, PAGE_SIZE[0], PAGE_SIZE[1], fill=1, stroke=0)
    canvas_obj.setFillColor(colors.white)
    canvas_obj.roundRect(34, 28, PAGE_SIZE[0] - 68, PAGE_SIZE[1] - 56, 18, fill=1, stroke=0)
    canvas_obj.setFillColor(BLUE)
    canvas_obj.setFont("Arial-Bold", 12)
    canvas_obj.drawString(58, 486, f"Понятия для новичка - день {lesson['day']} из 30")
    canvas_obj.setFillColor(MUTED)
    canvas_obj.setFont("Arial", 10)
    canvas_obj.drawRightString(902, 486, f"{number:02d} / {TOTAL_SLIDES} · {label}")


def _finish(canvas_obj):
    canvas_obj.setFillColor(MUTED)
    canvas_obj.setFont("Arial", 9)
    canvas_obj.drawRightString(902, 48, "50% теория · 50% практика")
    canvas_obj.showPage()


def _title(canvas_obj, text, y=430, size=30, color=DARK):
    canvas_obj.setFillColor(color)
    canvas_obj.setFont("Arial-Bold", size)
    canvas_obj.drawString(58, y, text)


def _draw_card(canvas_obj, x, y, w, h, color=SOFT, stroke=colors.HexColor("#dbeafe")):
    canvas_obj.setFillColor(color)
    canvas_obj.setStrokeColor(stroke)
    canvas_obj.roundRect(x, y, w, h, 14, fill=1, stroke=1)


def build_deck(lesson):
    path = OUT_DIR / f"python_day{lesson['day']:02d}_simple_readable.pdf"
    c = canvas.Canvas(str(path), pagesize=PAGE_SIZE)
    body = ParagraphStyle("body", fontName="Arial", fontSize=18, leading=25, textColor=DARK)
    small = ParagraphStyle("small", fontName="Arial", fontSize=15, leading=21, textColor=DARK)
    task_style = ParagraphStyle("task", fontName="Arial", fontSize=17, leading=24, textColor=DARK)
    solution_style = ParagraphStyle("solution", fontName="Arial", fontSize=17, leading=24, textColor=DARK)
    code_style = ParagraphStyle("code", fontName="Courier", fontSize=13, leading=18, textColor=colors.HexColor("#e2e8f0"))

    slides = []
    slides.append(("intro", lambda n: (
        _start_slide(c, lesson, n, "старт"),
        _title(c, lesson["title"], 410, 32),
        _wrap(c, lesson["summary"], 58, 356, 760, body),
        _draw_card(c, 58, 135, 390, 120),
        _wrap(c, "Цель: понять идею темы и сразу применить её в маленькой задаче.", 82, 220, 330, small),
        _draw_card(c, 480, 135, 390, 120),
        _wrap(c, "Формат: короткая теория, задача, затем следующий слайд с разбором.", 504, 220, 330, small),
        _finish(c),
    )))
    slides.append(("map", lambda n: (
        _start_slide(c, lesson, n, "карта урока"),
        _title(c, "Маршрут на 30 минут", 420, 30),
        _draw_card(c, 58, 240, 380, 130),
        _wrap(c, "50% теория: понять термины, увидеть связи и проговорить тему простыми словами.", 82, 330, 320, small),
        _draw_card(c, 490, 240, 380, 130),
        _wrap(c, "50% практика: решить мини-задачи, свериться с разбором и исправить слабое место.", 514, 330, 320, small),
        _finish(c),
    )))
    slides.append(("theory1", lambda n: (
        _start_slide(c, lesson, n, "теория"),
        _title(c, "Теория: базовая идея", 420, 30),
        _draw_card(c, 58, 245, 400, 130),
        _bullet_list(c, lesson["lecture"][:2], 76, 350, 360, small, 4),
        c.setFillColor(colors.HexColor("#0f172a")), c.roundRect(480, 125, 390, 250, 12, fill=1, stroke=0),
        _wrap(c, _safe_code(lesson.get("code", ""), 7), 500, 345, 350, code_style),
        _finish(c),
    )))
    slides.append(("theory2", lambda n: (
        _start_slide(c, lesson, n, "теория"),
        _title(c, "Теория: как это работает", 420, 30),
        _draw_card(c, 58, 245, 400, 130),
        _bullet_list(c, lesson["lecture"][2:4], 76, 350, 360, small, 4),
        c.setFillColor(colors.HexColor("#0f172a")), c.roundRect(480, 125, 390, 250, 12, fill=1, stroke=0),
        _wrap(c, _safe_code(lesson.get("code", ""), 14), 500, 345, 350, code_style),
        _finish(c),
    )))
    slides.append(("theory3", lambda n: (
        _start_slide(c, lesson, n, "теория"),
        _title(c, "Теория: где применять", 420, 30),
        _draw_card(c, 58, 245, 400, 130),
        _bullet_list(c, lesson["lecture"][4:5] + (lesson["summary"],), 76, 350, 360, small, 4),
        c.setFillColor(colors.HexColor("#0f172a")), c.roundRect(480, 125, 390, 250, 12, fill=1, stroke=0),
        _wrap(c, _safe_code(lesson.get("code", ""), 21), 500, 345, 350, code_style),
        _finish(c),
    )))
    slides.append(("terms", lambda n: (
        _start_slide(c, lesson, n, "словарь"),
        _title(c, "10 терминов дня", 420, 30),
        _bullet_list(c, [f"{term} - {definition}" for term, definition in lesson["terms"][:5]], 74, 360, 790, small, 5),
        _finish(c),
    )))
    slides.append(("terms2", lambda n: (
        _start_slide(c, lesson, n, "словарь"),
        _title(c, "Ещё 5 терминов", 420, 30),
        _bullet_list(c, [f"{term} - {definition}" for term, definition in lesson["terms"][5:]], 74, 360, 790, small, 5),
        _finish(c),
    )))
    slides.append(("bridge", lambda n: (
        _start_slide(c, lesson, n, "переход к практике"),
        _title(c, "Как думать на практике", 420, 30),
        _bullet_list(c, [
            "Сначала назовите входные данные: что дано в задаче.",
            "Потом выберите действие: что нужно проверить, найти или сравнить.",
            "В конце сформулируйте результат и возможную ошибку.",
        ], 78, 350, 760, body),
        _finish(c),
    )))
    slides.append(("practice-rules", lambda n: (
        _start_slide(c, lesson, n, "правила практики"),
        _title(c, "Правила мини-задач", 420, 30),
        _bullet_list(c, [
            "Не смотрите разбор до попытки: сначала запишите свой ответ.",
            "В разборе ищите не только правильность, но и ход мысли.",
            "Если ошиблись, перепишите решение в 3 коротких шага.",
        ], 78, 350, 760, body),
        _finish(c),
    )))

    task_pairs = list(lesson["mini_tasks"]) + [
        {
            "title": "Словарь на практике",
            "task": f"Составьте 4 предложения с терминами: {lesson['terms'][0][0]}, {lesson['terms'][1][0]}, {lesson['terms'][2][0]}, {lesson['terms'][3][0]}. Каждое предложение должно быть про рабочую ситуацию.",
            "solution": "Разбор: хорошее предложение связывает термин с действием. Например: кто использует объект, зачем он нужен, что изменится после действия.",
        },
        {
            "title": "Найти лишнее",
            "task": f"Из списка выберите термин, который хуже всего связан с темой дня: {lesson['terms'][4][0]}, {lesson['terms'][5][0]}, {lesson['terms'][6][0]}, {lesson['terms'][7][0]}. Объясните выбор.",
            "solution": "Разбор: лишний термин выбирается не по незнакомости, а по связи с задачей. Сначала назовите общий признак трёх терминов, затем покажите отличие четвёртого.",
        },
        {
            "title": "План из 3 шагов",
            "task": f"Разбейте практику дня на 3 шага так, чтобы её мог выполнить человек без опыта: {lesson['practice']}",
            "solution": "Разбор: шаги должны идти от подготовки к проверке результата: открыть/найти данные, выполнить действие, зафиксировать вывод и ошибку.",
        },
        {
            "title": "Ошибка новичка",
            "task": "Придумайте одну типичную ошибку новичка по теме дня и напишите, как её быстро заметить.",
            "solution": "Разбор: ошибка должна быть проверяемой. Хороший ответ содержит симптом, причину и действие: что увидеть, почему случилось, как исправить.",
        },
        {
            "title": "Мини-объяснение",
            "task": f"Объясните тему «{lesson['title']}» за 40 секунд без сложных слов. Используйте минимум 2 термина дня.",
            "solution": "Разбор: сильное объяснение короткое: что это, зачем нужно, где применяется. Термины должны помогать, а не усложнять ответ.",
        },
        {
            "title": "Связь с проектом",
            "task": "Найдите, где эта тема могла бы встретиться в личном веб-проекте: интерфейс, сервер, база, тесты, безопасность или деплой.",
            "solution": "Разбор: выберите один слой проекта и опишите реальное действие. Например: сохранить данные, проверить запрос, оформить страницу, написать тест.",
        },
    ]
    task_pairs.append({
        "title": "Практика дня",
        "task": lesson["practice"],
        "solution": "Разбор: выполнить задание маленькими шагами, записать результат и объяснить, какие термины дня использованы в решении.",
    })
    task_pairs.append({
        "title": "Вопрос на закрепление",
        "task": lesson["checkpoint"]["prompt"],
        "solution": f"Правильный ответ: {lesson['checkpoint']['options'][lesson['checkpoint']['correct_index']]}. {lesson['checkpoint']['explanation']}",
    })
    task_pairs = task_pairs[:10]

    for pair_index, pair in enumerate(task_pairs, start=1):
        slides.append((f"task{pair_index}", lambda n, pair=pair, pair_index=pair_index: (
            _start_slide(c, lesson, n, "задача"),
            _title(c, f"Задача {pair_index}: {pair['title']}", 420, 29, VIOLET),
            _draw_card(c, 58, 115, 840, 250, colors.HexColor("#f5f3ff"), colors.HexColor("#ddd6fe")),
            _wrap(c, pair["task"], 86, 326, 780, task_style),
            _finish(c),
        )))
        slides.append((f"solution{pair_index}", lambda n, pair=pair, pair_index=pair_index: (
            _start_slide(c, lesson, n, "разбор"),
            _title(c, f"Разбор {pair_index}", 420, 30, GREEN),
            _draw_card(c, 58, 115, 840, 250, colors.HexColor("#ecfdf5"), colors.HexColor("#bbf7d0")),
            _wrap(c, pair["solution"], 86, 326, 780, solution_style),
            _finish(c),
        )))

    slides.append(("final", lambda n: (
        _start_slide(c, lesson, n, "итог"),
        _title(c, "Итог урока", 420, 32),
        _bullet_list(c, [
            "Повторите термины дня своими словами.",
            "Выполните мини-задачи без подсказок.",
            "Сверьте решение с разбором и исправьте одно слабое место.",
            "После этого переходите к тесту дня.",
        ], 78, 350, 760, body),
        _finish(c),
    )))

    if len(slides) != TOTAL_SLIDES:
        raise RuntimeError(f"Expected {TOTAL_SLIDES} slides, got {len(slides)}")
    for index, (_name, draw) in enumerate(slides, start=1):
        draw(index)
    c.save()
    return path


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not FONT_PATH.is_file():
        raise FileNotFoundError(f"Font not found: {FONT_PATH}")
    pdfmetrics.registerFont(TTFont("Arial", str(FONT_PATH)))
    pdfmetrics.registerFont(TTFont("Arial-Bold", str(FONT_PATH)))
    for lesson in IT_LESSONS:
        build_deck(lesson)


if __name__ == "__main__":
    main()
