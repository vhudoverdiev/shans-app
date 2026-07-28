from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


OUT = Path("Shans_presentation_light_3_slides.pdf").resolve()
WORK = Path(".codex_artifacts")
LOGO = Path("app/static/logo.png")
PHOTO = WORK / "developer.jpg"
W, H = 1280, 720

INK = "#111827"
SOFT = "#334155"
MUTED = "#64748b"
BLUE = "#2563eb"
PURPLE = "#7c3aed"
PAPER = "#f6f8fc"
LINE = "#dbe3ef"


def register_fonts():
    regular = Path("C:/Windows/Fonts/arial.ttf")
    bold = Path("C:/Windows/Fonts/arialbd.ttf")
    if regular.exists():
        pdfmetrics.registerFont(TTFont("Arial", str(regular)))
    if bold.exists():
        pdfmetrics.registerFont(TTFont("Arial-Bold", str(bold)))


def c(value):
    return colors.HexColor(value)


def para(pdf, text, x, y, w, h, size=18, color=INK, bold=False, leading=None, align="LEFT"):
    style = ParagraphStyle(
        "p",
        fontName="Arial-Bold" if bold else "Arial",
        fontSize=size,
        leading=leading or size * 1.18,
        textColor=c(color),
        alignment={"LEFT": 0, "CENTER": 1, "RIGHT": 2}[align],
        spaceAfter=0,
    )
    p = Paragraph(text.replace("\n", "<br/>"), style)
    _, ah = p.wrapOn(pdf, w, h)
    p.drawOn(pdf, x, H - y - ah)


def rect(pdf, x, y, w, h, fill, stroke=None, radius=0):
    pdf.setFillColor(c(fill))
    pdf.setStrokeColor(c(stroke or fill))
    pdf.setLineWidth(1 if stroke else 0)
    if radius:
        pdf.roundRect(x, H - y - h, w, h, radius, stroke=1 if stroke else 0, fill=1)
    else:
        pdf.rect(x, H - y - h, w, h, stroke=1 if stroke else 0, fill=1)


def rule(pdf, x, y, w, color=LINE, weight=1):
    pdf.setStrokeColor(c(color))
    pdf.setLineWidth(weight)
    pdf.line(x, H - y, x + w, H - y)


def crop_photo(name, box):
    out = WORK / name
    with Image.open(PHOTO) as im:
        w, h = im.size
        l, t, r, b = box
        crop = im.crop((int(w * l), int(h * t), int(w * (1 - r)), int(h * (1 - b))))
        crop.save(out, quality=92)
    return out


def top_mark(pdf):
    pdf.drawImage(str(LOGO), 72, H - 86, 42, 42, preserveAspectRatio=True, mask="auto")
    para(pdf, "SHANS", 130, 46, 110, 22, 16, INK, True)
    para(pdf, "personal management system", 130, 68, 220, 18, 11, MUTED)


def footer(pdf, n):
    rule(pdf, 72, 652, 1136, LINE)
    para(pdf, f"0{n}", 72, 670, 42, 20, 12, MUTED, True)
    para(pdf, "Shans · project presentation", 1058, 670, 150, 20, 11, MUTED, align="RIGHT")


def chip(pdf, label, x, y, fill="#ffffff", stroke=LINE, color=BLUE):
    rect(pdf, x, y, 132, 34, fill, stroke, 17)
    para(pdf, label, x, y + 8, 132, 18, 12, color, True, align="CENTER")


def metric(pdf, n, title, body, left, top):
    para(pdf, n, left, top + 2, 40, 22, 13, BLUE, True)
    para(pdf, title, left + 48, top, 250, 24, 19, INK, True)
    para(pdf, body, left + 48, top + 32, 265, 42, 14, MUTED)


def slide1(pdf):
    photo = crop_photo("developer_pdf_cover.jpg", (0.03, 0.15, 0.25, 0.01))
    rect(pdf, 0, 0, W, H, "#ffffff")
    rect(pdf, 804, 82, 372, 522, "#f8fbff", LINE, 30)
    top_mark(pdf)
    para(pdf, "Shans помогает держать порядок", 72, 164, 560, 124, 54, INK, True)
    para(pdf, "Личная система для графика, проектов, финансов, авто, обучения и здоровья в одном аккуратном веб-приложении.", 72, 318, 560, 76, 22, SOFT)
    for i, label in enumerate(["PWA", "Push", "2FA", "Excel"]):
        chip(pdf, label, 72 + i * 142, 452)
    pdf.drawImage(str(photo), 828, H - 102 - 474, 296, 474)
    rect(pdf, 780, 552, 234, 74, "#ffffff", "#dde5f0", 22)
    para(pdf, "1 интерфейс", 802, 572, 190, 22, 22, INK, True)
    para(pdf, "для ежедневных процессов", 802, 600, 190, 18, 12, MUTED)
    footer(pdf, 1)


def slide2(pdf):
    rect(pdf, 0, 0, W, H, PAPER)
    top_mark(pdf)
    para(pdf, "Архитектура продукта", 72, 138, 460, 42, 36, INK, True)
    para(pdf, "Внутри Shans нет случайных разделов. Каждый блок отвечает за конкретный сценарий: запланировать, выполнить, зафиксировать результат и вернуться к данным позже.", 72, 206, 470, 92, 19, SOFT)
    rect(pdf, 670, 116, 424, 416, "#ffffff", LINE, 34)
    rect(pdf, 812, 250, 140, 140, "#eef2ff", None, 34)
    para(pdf, "SHANS", 812, 300, 140, 28, 23, INK, True, align="CENTER")
    para(pdf, "core", 812, 332, 140, 20, 12, BLUE, align="CENTER")
    for label, x, y, color in [
        ("График", 736, 156, BLUE),
        ("Съёмки", 946, 176, PURPLE),
        ("Отчёты", 952, 414, "#15803d"),
        ("Авто", 720, 434, "#d97706"),
        ("Обучение", 636, 296, "#475569"),
        ("Спорт", 1032, 296, "#15803d"),
    ]:
        chip(pdf, label, x, y, "#ffffff", LINE, color)
    rule(pdf, 650, 558, 500, "#cbd5e1")
    para(pdf, "Единая логика: данные не теряются между разделами", 650, 576, 500, 22, 15, MUTED, True, align="CENTER")
    metric(pdf, "01", "Планирование", "Календарь, задачи, статусы и напоминания.", 72, 350)
    metric(pdf, "02", "Учет", "Бюджет, авто, история и экспорт в Excel.", 72, 444)
    metric(pdf, "03", "Развитие", "Курсы, тренировки, питание и прогресс.", 72, 538)
    footer(pdf, 2)


def slide3(pdf):
    photo = crop_photo("developer_pdf_final.jpg", (0.03, 0.17, 0.23, 0.01))
    rect(pdf, 0, 0, W, H, "#ffffff")
    rect(pdf, 72, 92, 372, 520, "#f8fbff", LINE, 28)
    top_mark(pdf)
    para(pdf, "Почему это выглядит цельно", 104, 174, 290, 82, 36, INK, True)
    para(pdf, "Проект собран вокруг реальных ежедневных задач, поэтому его можно расширять без потери логики.", 104, 282, 286, 88, 19, SOFT)
    chip(pdf, "Практичность", 104, 416, "#eef2ff", "#c7d2fe", BLUE)
    chip(pdf, "Мобильность", 104, 466, "#f5f3ff", "#ddd6fe", PURPLE)
    chip(pdf, "Безопасность", 104, 516, "#ecfdf5", "#bbf7d0", "#15803d")
    para(pdf, "Разработчик", 520, 74, 150, 22, 13, BLUE, True)
    para(pdf, "Владимир<br/>Худовердиев", 520, 108, 340, 84, 42, INK, True)
    para(pdf, "Shans - авторский проект, созданный под личные рабочие процессы: от расписания и финансов до проектов, обучения и здоровья.", 520, 218, 430, 82, 20, SOFT)
    rule(pdf, 520, 332, 446, "#bfdbfe", 2)
    para(pdf, "Итоговая ценность", 520, 368, 220, 22, 16, INK, True)
    para(pdf, "Меньше хаоса в повседневных данных. Больше контроля, прозрачности и внимания на важном.", 520, 404, 398, 102, 28, INK, True)
    pdf.drawImage(str(photo), 992, H - 76 - 548, 216, 548)
    footer(pdf, 3)


def main():
    register_fonts()
    WORK.mkdir(exist_ok=True)
    pdf = canvas.Canvas(str(OUT), pagesize=(W, H))
    for fn in (slide1, slide2, slide3):
        fn(pdf)
        pdf.showPage()
    pdf.save()
    print(OUT)


if __name__ == "__main__":
    main()
