from __future__ import annotations

import csv
import math
import random
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(r"C:\Users\Владимир\Desktop\Сайты\Shans")
ARTIFACT_ROOT = ROOT / ".codex_artifacts" / "shans_montage_pack_v2"
PACKAGE = ARTIFACT_ROOT / "package"
GRAPHICS = PACKAGE / "03_Графика"
SCREENS_DESKTOP = PACKAGE / "04_Экраны" / "desktop"
SCREENS_MOBILE = PACKAGE / "04_Экраны" / "mobile"
SFX = PACKAGE / "05_SFX"
PREVIEW = PACKAGE / "06_Превью"
SCENARIO = PACKAGE / "01_Сценарий"
EDIT = PACKAGE / "02_Монтаж"
REFERENCE = PACKAGE / "07_Референс"

W, H = 1920, 1080
FPS = 25
BG = "#F5F7FC"
INK = "#111526"
MUTED = "#667085"
BLUE = "#2F63F1"
VIOLET = "#6941C6"
TEAL = "#20B6A5"
CORAL = "#F05D5E"
WHITE = "#FFFFFF"
FRAME = "#20232C"

FONT_REG = r"C:\Windows\Fonts\segoeui.ttf"
FONT_SEMI = r"C:\Windows\Fonts\seguisb.ttf"
FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"


SCENES = [
    (1, "00:00-00:10", 10, "Shans: ключевые процессы", "Вводный кадр, логотип и карта модулей", "title_open.png"),
    (2, "00:10-00:20", 10, "Разработчик проекта", "Владимир Худовердиев, интерфейс на втором плане", "lower_third_developer.png"),
    (3, "00:20-00:30", 10, "Работа на компьютере", "Календарь, проекты, финансы и автомобиль", "chapter_01_desktop.png"),
    (4, "00:30-00:42", 12, "Мобильное расписание", "PWA, создание и отметка задачи", "chapter_02_mobile.png"),
    (5, "00:42-00:53", 11, "Push и события", "Уведомление, центр событий, переход в раздел", "chapter_03_push.png"),
    (6, "00:53-01:04", 11, "Питание", "Быстрый ввод, поиск, калории и БЖУ", "chapter_04_nutrition.png"),
    (7, "01:04-01:15", 11, "Тренировки и обучение", "План, результат, урок и тест", "chapter_05_progress.png"),
    (8, "01:15-01:22", 7, "Отчеты", "Центр отчетов, бюджет и Excel", "chapter_06_reports.png"),
    (9, "01:22-01:27", 5, "Защита данных", "Настройки аккаунта, 2FA и push", "chapter_07_security.png"),
    (10, "01:27-01:30", 3, "Финал", "Логотип и нейтральная итоговая строка", "title_end.png"),
]


def font(size: int, bold: bool = False, semi: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_SEMI if semi else FONT_REG
    return ImageFont.truetype(path, size)


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    color = hex_color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return mask


def paste_contain(canvas: Image.Image, source: Path, box: tuple[int, int, int, int], radius: int = 0) -> None:
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    with Image.open(source) as src:
        img = src.convert("RGB")
        scale = min(bw / img.width, bh / img.height)
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.Resampling.LANCZOS)
    holder = Image.new("RGB", (bw, bh), WHITE)
    holder.paste(img, ((bw - img.width) // 2, (bh - img.height) // 2))
    if radius:
        canvas.paste(holder, (x1, y1), rounded_mask((bw, bh), radius))
    else:
        canvas.paste(holder, (x1, y1))


def draw_text_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt: ImageFont.FreeTypeFont,
                      fill: str, max_width: int, spacing: int = 8) -> int:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    x, y = xy
    line_h = draw.textbbox((0, 0), "Ag", font=fnt)[3]
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_h + spacing
    return y


def logo_icon(size: int) -> Image.Image:
    src = ROOT / "app" / "static" / "logo.png"
    with Image.open(src) as im:
        icon = im.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
    return icon


def background() -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle((0, 0, W, H), fill=(245, 247, 252, 255))
    for x, y, r, color in [
        (-120, 120, 300, BLUE),
        (1840, 180, 250, VIOLET),
        (1700, 960, 360, TEAL),
        (240, 1040, 260, VIOLET),
    ]:
        for offset, alpha in [(0, 34), (32, 24), (64, 14)]:
            d.ellipse((x - r - offset, y - r - offset, x + r + offset, y + r + offset), outline=rgba(color, alpha), width=2)
    for x in range(120, W, 240):
        d.line((x, 0, x, H), fill=(47, 99, 241, 10), width=1)
    for y in range(120, H, 240):
        d.line((0, y, W, y), fill=(105, 65, 198, 8), width=1)
    d.rounded_rectangle((1638, 74, 1798, 86), 6, fill=rgba(BLUE, 180))
    d.ellipse((1812, 72, 1828, 88), fill=rgba(TEAL, 220))
    return im


def add_wordmark(im: Image.Image, x: int, y: int, compact: bool = False) -> None:
    d = ImageDraw.Draw(im)
    size = 56 if compact else 78
    icon = logo_icon(size)
    im.paste(icon, (x, y), rounded_mask((size, size), 15))
    d.text((x + size + 18, y - 2), "SHANS", font=font(38 if compact else 54, bold=True), fill=INK)
    if not compact:
        d.text((x + size + 21, y + 61), "personal CRM", font=font(18, semi=True), fill=MUTED)


def add_browser(im: Image.Image, screenshot: Path, box=(220, 145, 1700, 930)) -> None:
    x1, y1, x2, y2 = box
    d = ImageDraw.Draw(im, "RGBA")
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x1 + 16, y1 + 28, x2 + 16, y2 + 28), 38, fill=(17, 21, 38, 48))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    im.paste(shadow, (0, 0), shadow)
    d.rounded_rectangle((x1, y1, x2, y2), 36, fill=rgba(FRAME))
    d.rounded_rectangle((x1 + 26, y1 + 64, x2 - 26, y2 - 26), 18, fill=rgba(WHITE))
    for i, c in enumerate((CORAL, "#F7B955", TEAL)):
        d.ellipse((x1 + 28 + i * 28, y1 + 25, x1 + 42 + i * 28, y1 + 39), fill=rgba(c))
    d.rounded_rectangle((x1 + 150, y1 + 18, x2 - 150, y1 + 48), 15, fill=(255, 255, 255, 32))
    paste_contain(im, screenshot, (x1 + 28, y1 + 66, x2 - 28, y2 - 28), 16)


def add_phone(im: Image.Image, screenshot: Path, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    d = ImageDraw.Draw(im, "RGBA")
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x1 + 18, y1 + 24, x2 + 18, y2 + 24), 64, fill=(17, 21, 38, 55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    im.paste(shadow, (0, 0), shadow)
    d.rounded_rectangle((x1, y1, x2, y2), 62, fill=rgba(FRAME))
    d.rounded_rectangle((x1 + 18, y1 + 22, x2 - 18, y2 - 22), 48, fill=rgba(WHITE))
    d.rounded_rectangle(((x1 + x2) // 2 - 58, y1 + 31, (x1 + x2) // 2 + 58, y1 + 43), 6, fill=rgba(FRAME))
    paste_contain(im, screenshot, (x1 + 22, y1 + 50, x2 - 22, y2 - 50), 36)


def add_chapter(im: Image.Image, number: str, title: str, subtitle: str, y: int = 860) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    x1, x2 = 120, 1120
    d.rounded_rectangle((x1, y, x2, y + 118), 24, fill=(255, 255, 255, 242), outline=rgba(BLUE, 80), width=2)
    d.rounded_rectangle((x1, y, x1 + 16, y + 118), 8, fill=rgba(BLUE))
    d.ellipse((x1 + 38, y + 24, x1 + 100, y + 86), fill=rgba(VIOLET))
    d.text((x1 + 56, y + 35), number, font=font(20, bold=True), fill=WHITE, anchor="mm")
    d.text((x1 + 126, y + 17), title, font=font(31, bold=True), fill=INK)
    d.text((x1 + 126, y + 62), subtitle, font=font(20), fill=MUTED)


def scene_open() -> Image.Image:
    im = background(); d = ImageDraw.Draw(im)
    add_wordmark(im, 120, 98)
    d.text((120, 270), "Ключевые процессы", font=font(72, bold=True), fill=INK)
    d.text((120, 355), "в одной системе", font=font(72, bold=True), fill=INK)
    d.rounded_rectangle((120, 480, 680, 536), 18, fill=BLUE)
    d.text((150, 492), "CRM для личного управления", font=font(25, semi=True), fill=WHITE)
    modules = [
        ("Планирование", BLUE), ("Финансы", VIOLET), ("Проекты", TEAL),
        ("Автомобиль", CORAL), ("Обучение", VIOLET), ("Спорт и питание", BLUE),
    ]
    for i, (label, color) in enumerate(modules):
        x = 120 + (i % 3) * 300; y = 620 + (i // 3) * 108
        d.rounded_rectangle((x, y, x + 268, y + 78), 18, fill=WHITE, outline=rgba(color, 100), width=2)
        d.ellipse((x + 24, y + 25, x + 52, y + 53), fill=color)
        d.text((x + 70, y + 23), label, font=font(22, semi=True), fill=INK)
    icon = logo_icon(500)
    im.paste(icon, (1300, 290), rounded_mask((500, 500), 110))
    return im


def scene_developer() -> Image.Image:
    im = background(); add_wordmark(im, 120, 72, compact=True)
    add_browser(im, ROOT / "_codex_chat_files" / "calendar-small-desktop.png", (650, 170, 1780, 815))
    d = ImageDraw.Draw(im)
    d.text((120, 285), "Разработчик", font=font(30, semi=True), fill=BLUE)
    d.text((120, 340), "Владимир", font=font(64, bold=True), fill=INK)
    d.text((120, 415), "Худовердиев", font=font(64, bold=True), fill=INK)
    draw_text_wrapped(d, (120, 535), "Модульная система, в которой задачи, данные и уведомления работают в единой логике.", font(25), MUTED, 430, 9)
    add_chapter(im, "00", "Разработчик проекта", "Владимир Худовердиев", 865)
    return im


def scene_desktop() -> Image.Image:
    im = background(); add_wordmark(im, 120, 70, compact=True)
    add_browser(im, ROOT / "_codex_chat_files" / "calendar-small-desktop.png", (250, 130, 1700, 900))
    add_chapter(im, "01", "Работа на компьютере", "Планирование • Финансы • Проекты • Автомобиль", 870)
    return im


def mobile_scene(screenshot: Path, number: str, title: str, subtitle: str, second: Path | None = None) -> Image.Image:
    im = background(); d = ImageDraw.Draw(im); add_wordmark(im, 120, 72, compact=True)
    d.text((120, 250), title, font=font(56, bold=True), fill=INK)
    draw_text_wrapped(d, (120, 335), subtitle, font(27), MUTED, 600, 10)
    d.rounded_rectangle((120, 520, 510, 576), 18, fill=VIOLET)
    d.text((150, 531), "МОБИЛЬНАЯ ВЕРСИЯ", font=font(22, bold=True), fill=WHITE)
    if second:
        add_phone(im, screenshot, (1030, 110, 1395, 940))
        add_phone(im, second, (1430, 185, 1765, 940))
    else:
        add_phone(im, screenshot, (1200, 95, 1635, 955))
    add_chapter(im, number, title, subtitle, 872)
    return im


def report_mockup() -> Image.Image:
    im = Image.new("RGB", (1400, 720), WHITE); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 240, 720), fill="#151926")
    d.text((40, 48), "SHANS", font=font(34, bold=True), fill=WHITE)
    for i, label in enumerate(["Обзор", "Бюджет", "Баланс", "Отчеты", "Экспорт"]):
        y = 140 + i * 72
        if label == "Отчеты": d.rounded_rectangle((24, y - 10, 216, y + 46), 12, fill=BLUE)
        d.text((50, y), label, font=font(22, semi=True), fill=WHITE if label == "Отчеты" else "#B9C0D0")
    d.text((290, 58), "Центр отчетов", font=font(38, bold=True), fill=INK)
    cards = [(290, 140, 560, 270, "Бюджет", "124 800 ₽", BLUE), (590, 140, 860, 270, "Баланс", "+18 400 ₽", TEAL), (890, 140, 1160, 270, "Период", "Август", VIOLET)]
    for x1, y1, x2, y2, label, value, color in cards:
        d.rounded_rectangle((x1, y1, x2, y2), 18, fill="#F7F8FC", outline="#E4E7EC")
        d.text((x1 + 20, y1 + 18), label, font=font(18), fill=MUTED)
        d.text((x1 + 20, y1 + 60), value, font=font(31, bold=True), fill=color)
    d.rounded_rectangle((290, 320, 1160, 645), 18, fill="#FAFBFD", outline="#E4E7EC")
    pts = [(330, 570), (430, 520), (530, 548), (630, 430), (730, 470), (830, 360), (930, 390), (1080, 340)]
    d.line(pts, fill=BLUE, width=8, joint="curve")
    for x, y in pts: d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=VIOLET)
    d.rounded_rectangle((1190, 140, 1350, 200), 16, fill=BLUE)
    d.text((1220, 157), "Excel", font=font(22, bold=True), fill=WHITE)
    return im


def scene_reports() -> Image.Image:
    im = background(); add_wordmark(im, 120, 72, compact=True)
    tmp = report_mockup(); tmp_path = ARTIFACT_ROOT / "report_mockup.png"; tmp.save(tmp_path)
    add_browser(im, tmp_path, (235, 125, 1715, 920))
    add_chapter(im, "06", "Отчеты и Excel", "Бюджет, баланс, проверка и экспорт данных", 872)
    return im


def scene_security() -> Image.Image:
    im = background(); add_wordmark(im, 120, 72, compact=True)
    add_browser(im, ROOT / "_codex_chat_files" / "desktop-push-settings.png", (255, 130, 1690, 910))
    add_chapter(im, "07", "Защита данных", "Авторизация • 2FA • настройки push", 872)
    return im


def scene_end() -> Image.Image:
    im = Image.new("RGB", (W, H), INK); d = ImageDraw.Draw(im, "RGBA")
    for x, y, r, c in [(250, 200, 360, BLUE), (1700, 180, 310, VIOLET), (1550, 1000, 450, TEAL)]:
        d.ellipse((x-r, y-r, x+r, y+r), outline=rgba(c, 50), width=2)
    icon = logo_icon(250); im.paste(icon, (835, 250), rounded_mask((250, 250), 56))
    d.text((960, 575), "SHANS", font=font(86, bold=True), fill=WHITE, anchor="mm")
    d.text((960, 690), "Ключевые процессы в одной системе", font=font(34, semi=True), fill="#C8CEDC", anchor="mm")
    return im


def save_graphic_assets() -> None:
    bg = background(); bg.save(GRAPHICS / "background_shans_1920x1080.png")
    # Logo bug.
    bug = Image.new("RGBA", (560, 130), (0, 0, 0, 0)); bd = ImageDraw.Draw(bug)
    bd.rounded_rectangle((0, 0, 550, 120), 22, fill=(255, 255, 255, 236), outline=rgba(BLUE, 80), width=2)
    icon = logo_icon(86); bug.paste(icon.convert("RGBA"), (18, 17), rounded_mask((86, 86), 18))
    bd.text((126, 16), "SHANS", font=font(40, bold=True), fill=INK)
    bd.text((127, 67), "personal CRM", font=font(19, semi=True), fill=MUTED)
    bug.save(GRAPHICS / "logo_bug.png")
    # Developer lower third.
    lt = Image.new("RGBA", (980, 170), (0, 0, 0, 0)); ld = ImageDraw.Draw(lt)
    ld.rounded_rectangle((0, 0, 970, 160), 28, fill=(255, 255, 255, 244), outline=rgba(BLUE, 90), width=2)
    ld.rounded_rectangle((0, 0, 18, 160), 9, fill=rgba(BLUE))
    ld.text((52, 24), "Владимир Худовердиев", font=font(36, bold=True), fill=INK)
    ld.text((52, 83), "Разработчик проекта Shans", font=font(24, semi=True), fill=MUTED)
    lt.save(GRAPHICS / "lower_third_developer.png")
    chapters = [
        ("01", "Работа на компьютере", "Планирование • Финансы • Проекты • Автомобиль", "chapter_01_desktop.png"),
        ("02", "Мобильное расписание", "PWA • задачи • календарь", "chapter_02_mobile.png"),
        ("03", "Push и события", "Уведомления • центр событий • Telegram", "chapter_03_push.png"),
        ("04", "Питание", "Быстрый ввод • поиск • калории и БЖУ", "chapter_04_nutrition.png"),
        ("05", "Тренировки и обучение", "Планы • результаты • уроки • тесты", "chapter_05_progress.png"),
        ("06", "Отчеты и Excel", "Бюджет • баланс • экспорт", "chapter_06_reports.png"),
        ("07", "Защита данных", "Авторизация • 2FA • push", "chapter_07_security.png"),
    ]
    for number, title, subtitle, name in chapters:
        card = Image.new("RGBA", (1260, 140), (0, 0, 0, 0)); cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, 1248, 132), 24, fill=(255, 255, 255, 244), outline=rgba(BLUE, 90), width=2)
        cd.rounded_rectangle((0, 0, 16, 132), 8, fill=rgba(BLUE))
        cd.ellipse((38, 33, 104, 99), fill=rgba(VIOLET))
        cd.text((71, 65), number, font=font(20, bold=True), fill=WHITE, anchor="mm")
        cd.text((132, 18), title, font=font(31, bold=True), fill=INK)
        cd.text((132, 72), subtitle, font=font(21), fill=MUTED)
        card.save(GRAPHICS / name)
    # Browser and phone transparent framing overlays.
    browser = Image.new("RGBA", (1720, 950), (0, 0, 0, 0)); br = ImageDraw.Draw(browser)
    br.rounded_rectangle((0, 0, 1719, 949), 42, fill=rgba(FRAME))
    br.rounded_rectangle((28, 70, 1691, 921), 20, fill=(0, 0, 0, 0))
    for i, c in enumerate((CORAL, "#F7B955", TEAL)):
        br.ellipse((30 + i * 30, 26, 46 + i * 30, 42), fill=rgba(c))
    br.rounded_rectangle((170, 18, 1540, 50), 16, fill=(255, 255, 255, 34))
    browser.save(GRAPHICS / "browser_frame_overlay.png")
    phone = Image.new("RGBA", (520, 1010), (0, 0, 0, 0)); pd = ImageDraw.Draw(phone)
    pd.rounded_rectangle((0, 0, 519, 1009), 72, fill=rgba(FRAME))
    pd.rounded_rectangle((20, 24, 499, 985), 56, fill=(0, 0, 0, 0))
    pd.rounded_rectangle((198, 31, 322, 45), 7, fill=rgba(FRAME))
    phone.save(GRAPHICS / "phone_frame_overlay.png")
    safe = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(safe)
    sd.rectangle((154, 86, W - 154, H - 86), outline=(240, 93, 94, 175), width=3)
    sd.rectangle((96, 54, W - 96, H - 54), outline=(47, 99, 241, 130), width=2)
    sd.text((170, 95), "TITLE SAFE 8%", font=font(20, semi=True), fill=CORAL)
    safe.save(GRAPHICS / "safe_area_overlay.png")


def write_wav(path: Path, samples: list[float], sample_rate: int = 48000) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            value = max(-1.0, min(1.0, sample))
            packed = struct.pack("<h", int(value * 32767))
            frames.extend(packed); frames.extend(packed)
        wav.writeframes(bytes(frames))


def make_sfx() -> None:
    sr = 48000
    random.seed(37)
    click = []
    for i in range(int(sr * 0.09)):
        t = i / sr; env = math.exp(-55 * t)
        click.append((0.48 * math.sin(2 * math.pi * 1250 * t) + 0.18 * (random.random() * 2 - 1)) * env)
    write_wav(SFX / "ui_click.wav", click)
    pop = []
    for i in range(int(sr * 0.22)):
        t = i / sr; env = math.exp(-18 * t); freq = 520 + 900 * t
        pop.append(0.38 * math.sin(2 * math.pi * freq * t) * env)
    write_wav(SFX / "soft_pop.wav", pop)
    ping = []
    for i in range(int(sr * 0.70)):
        t = i / sr; env = math.exp(-5.5 * t)
        ping.append((0.23 * math.sin(2 * math.pi * 880 * t) + 0.13 * math.sin(2 * math.pi * 1320 * t)) * env)
    write_wav(SFX / "notification_ping.wav", ping)
    whoosh = []
    lp = 0.0
    for i in range(int(sr * 0.72)):
        t = i / sr; phase = t / 0.72; env = math.sin(math.pi * phase) ** 1.6
        noise = random.random() * 2 - 1; lp = 0.90 * lp + 0.10 * noise
        tone = math.sin(2 * math.pi * (150 + 600 * phase) * t)
        whoosh.append((0.23 * lp + 0.08 * tone) * env)
    write_wav(SFX / "soft_whoosh.wav", whoosh)


def tc(seconds: int) -> str:
    return f"00:{seconds // 60:02d}:{seconds % 60:02d}:00"


def write_edit_files() -> None:
    # Premiere marker CSV.
    with (EDIT / "Premiere_markers_Shans_90sec.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Marker Name", "Description", "In", "Out", "Marker Type"])
        cursor = 0
        for number, _, duration, title, action, _ in SCENES:
            w.writerow([f"{number:02d} {title}", action, tc(cursor), tc(cursor + duration), "Comment"])
            cursor += duration
    # CMX3600 guide EDL.
    lines = ["TITLE: SHANS_90SEC_GUIDE", "FCM: NON-DROP FRAME", ""]
    cursor = 0
    for number, _, duration, title, _, _ in SCENES:
        lines.append(f"{number:03d}  SCENE{number:02d} V     C        00:00:00:00  {tc(duration)}  {tc(cursor)}  {tc(cursor + duration)}")
        lines.append(f"* FROM CLIP NAME: SCENE_{number:02d}_{title.upper()}")
        lines.append("")
        cursor += duration
    (EDIT / "Shans_90sec_guide.edl").write_text("\n".join(lines), encoding="utf-8-sig")
    # Recording plan.
    rows = [
        ["Время", "Экран", "Действие", "Формат записи", "Примечание"],
        ["00:20-00:30", "Desktop", "Календарь → проект → бюджет → автомобиль", "1920×1080, курсор 100%, 25/30 fps", "По 2-3 секунды на раздел"],
        ["00:30-00:42", "Mobile", "Открыть PWA, создать и завершить задачу", "Вертикально 1080×1920", "Тапы спокойные, без прокрутки рывками"],
        ["00:42-00:53", "Mobile", "Получить push, открыть центр уведомлений", "Вертикально 1080×1920", "Снять отдельным дублем push"],
        ["00:53-01:04", "Mobile", "Добавить продукт, открыть поиск и БЖУ", "Вертикально 1080×1920", "Заполнить демонстрационные данные"],
        ["01:04-01:15", "Mobile", "Открыть тренировку, затем урок и тест", "Вертикально 1080×1920", "Смена раздела по whoosh"],
        ["01:15-01:22", "Desktop", "/reports → /budget/report → Excel", "1920×1080", "Экспорт записать до появления файла"],
        ["01:22-01:27", "Desktop", "Аккаунт, 2FA и настройки push", "1920×1080", "Не показывать секреты и QR-код крупно"],
    ]
    with (EDIT / "План_записи_интерфейса.csv").open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerows(rows)


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), fill); tc_pr.append(shd)


def set_cell_margins(cell, top=80, start=100, bottom=80, end=100) -> None:
    tc = cell._tc; tc_pr = tc.get_or_add_tcPr(); margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar"); tc_pr.append(margins)
    for tag, val in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{tag}"))
        if node is None: node = OxmlElement(f"w:{tag}"); margins.append(node)
        node.set(qn("w:w"), str(val)); node.set(qn("w:type"), "dxa")


def add_doc_title(doc: Document, text: str, subtitle: str | None = None) -> None:
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(7)
    r = p.add_run(text); r.bold = True; r.font.name = "Segoe UI"; r.font.size = Pt(24); r.font.color.rgb = RGBColor(17, 21, 38)
    if subtitle:
        p2 = doc.add_paragraph(); p2.paragraph_format.space_after = Pt(12)
        r2 = p2.add_run(subtitle); r2.font.name = "Segoe UI"; r2.font.size = Pt(10.5); r2.font.color.rgb = RGBColor(102, 112, 133)


def build_brief_docx() -> None:
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(1.5); sec.bottom_margin = Cm(1.4); sec.left_margin = Cm(1.7); sec.right_margin = Cm(1.7)
    styles = doc.styles
    styles["Normal"].font.name = "Segoe UI"; styles["Normal"].font.size = Pt(9.5); styles["Normal"].font.color.rgb = RGBColor(17, 21, 38)
    header = sec.header.paragraphs[0]; header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hr = header.add_run("SHANS  |  МОНТАЖНЫЙ ПАКЕТ  |  90 СЕКУНД"); hr.font.name = "Segoe UI"; hr.font.size = Pt(8); hr.font.color.rgb = RGBColor(47, 99, 241)
    footer = sec.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = footer.add_run("CRM Shans • Владимир Худовердиев • версия 04.08.2026"); fr.font.name = "Segoe UI"; fr.font.size = Pt(8); fr.font.color.rgb = RGBColor(102, 112, 133)
    # Cover.
    doc.add_paragraph().paragraph_format.space_after = Pt(42)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run("SHANS"); r.bold = True; r.font.name = "Segoe UI"; r.font.size = Pt(56); r.font.color.rgb = RGBColor(47, 99, 241)
    p2 = doc.add_paragraph(); p2.paragraph_format.space_after = Pt(8)
    r2 = p2.add_run("МОНТАЖНЫЙ ПАКЕТ"); r2.bold = True; r2.font.name = "Segoe UI"; r2.font.size = Pt(28); r2.font.color.rgb = RGBColor(17, 21, 38)
    p3 = doc.add_paragraph(); r3 = p3.add_run("Видеообзор CRM • 1:30 • 1920×1080 • 25 fps"); r3.font.name = "Segoe UI"; r3.font.size = Pt(14); r3.font.color.rgb = RGBColor(102, 112, 133)
    doc.add_paragraph()
    table = doc.add_table(rows=4, cols=2); table.alignment = WD_TABLE_ALIGNMENT.LEFT; table.autofit = False
    cover_data = [("Хронометраж", "90 секунд"), ("Мобильная версия", "45 секунд / 50% ролика"), ("Разработчик", "Владимир Худовердиев"), ("Референс", "Ритм и подача ролика «Передача», графика в стиле Shans")]
    for row, (label, value) in zip(table.rows, cover_data):
        row.cells[0].width = Cm(4.5); row.cells[1].width = Cm(12)
        shade_cell(row.cells[0], "2F63F1"); shade_cell(row.cells[1], "F1F4FA")
        for c in row.cells: set_cell_margins(c, 120, 140, 120, 140); c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        a = row.cells[0].paragraphs[0].add_run(label); a.bold = True; a.font.name = "Segoe UI"; a.font.size = Pt(9); a.font.color.rgb = RGBColor(255,255,255)
        b = row.cells[1].paragraphs[0].add_run(value); b.font.name = "Segoe UI"; b.font.size = Pt(10); b.font.color.rgb = RGBColor(17,21,38)
    doc.add_paragraph()
    p4 = doc.add_paragraph(); p4.paragraph_format.space_before = Pt(18)
    x = p4.add_run("Задача пакета"); x.bold = True; x.font.name = "Segoe UI"; x.font.size = Pt(15); x.font.color.rgb = RGBColor(105,65,198)
    doc.add_paragraph("Дать монтажеру готовую структуру ролика, фирменные PNG-оверлеи, таймлайн, субтитры, звуковые акценты и визуальный аниматик. Подача информационная: без рекламных обещаний и призывов к покупке.")
    doc.add_page_break()
    # Reference logic.
    add_doc_title(doc, "Монтажная логика референса", "Что берем из ролика «Передача» и как адаптируем для Shans")
    bullets = [
        ("Светлая среда", "Интерфейс расположен на спокойном фирменном фоне, а не занимает весь кадр."),
        ("Рамка устройства", "Desktop показывается в темной браузерной рамке; mobile в отдельном корпусе смартфона."),
        ("Нумерация блоков", "Ключевые функции получают короткие нижние плашки с номером и пояснением."),
        ("Ритм", "Основные склейки каждые 2-4 секунды; внутри длинного блока используется плавное приближение 100-103%."),
        ("Минимум эффектов", "Жесткая склейка, dissolve 6-8 кадров, мягкий push и короткий whoosh."),
        ("Адаптация Shans", "Зеленый заменен на синий, фиолетовый и бирюзовый. Мобильный блок увеличен до 45 секунд."),
    ]
    for title, body in bullets:
        p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(8)
        a = p.add_run(title + ". "); a.bold = True; a.font.color.rgb = RGBColor(47,99,241)
        p.add_run(body)
    doc.add_paragraph()
    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(10)
    r = p.add_run("Монтажный ритм"); r.bold = True; r.font.size = Pt(15); r.font.color.rgb = RGBColor(105,65,198)
    rhythm = doc.add_table(rows=1, cols=4); rhythm.alignment = WD_TABLE_ALIGNMENT.LEFT
    for cell, text in zip(rhythm.rows[0].cells, ["0:00-0:30\nDesktop", "0:30-1:15\nMobile", "1:15-1:27\nОтчеты и защита", "1:27-1:30\nФинал"]):
        shade_cell(cell, "F1F4FA"); set_cell_margins(cell, 180, 100, 180, 100)
        rr = cell.paragraphs[0].add_run(text); rr.bold = True; rr.font.name = "Segoe UI"; rr.font.size = Pt(10); rr.font.color.rgb = RGBColor(17,21,38)
    doc.add_page_break()
    # Timeline.
    add_doc_title(doc, "Таймлайн 90 секунд", "Плашки и точки смены сцен уже подготовлены в пакете")
    table = doc.add_table(rows=1, cols=5); table.alignment = WD_TABLE_ALIGNMENT.CENTER; table.autofit = False
    widths = [Cm(0.8), Cm(2.3), Cm(3.7), Cm(7.6), Cm(2.4)]
    for cell, label, width in zip(table.rows[0].cells, ["№", "Время", "Блок", "Кадр и действие", "Графика"], widths):
        cell.width = width; shade_cell(cell, "111526"); set_cell_margins(cell)
        rr = cell.paragraphs[0].add_run(label); rr.bold = True; rr.font.name = "Segoe UI"; rr.font.size = Pt(8); rr.font.color.rgb = RGBColor(255,255,255)
    for number, timecode, _, title, action, graphic in SCENES:
        cells = table.add_row().cells
        values = [f"{number:02d}", timecode, title, action, graphic]
        for idx, (cell, value, width) in enumerate(zip(cells, values, widths)):
            cell.width = width; set_cell_margins(cell, 70, 80, 70, 80); shade_cell(cell, "F6F8FC" if number % 2 else "EEF2F8")
            rr = cell.paragraphs[0].add_run(value); rr.font.name = "Segoe UI"; rr.font.size = Pt(7.4 if idx >= 3 else 8); rr.font.color.rgb = RGBColor(17,21,38)
            if idx == 0: rr.bold = True; rr.font.color.rgb = RGBColor(47,99,241)
    doc.add_page_break()
    # Visual system.
    add_doc_title(doc, "Визуальная система Shans", "Спокойная технологичная графика без рекламной стилистики")
    colors = doc.add_table(rows=1, cols=5); colors.alignment = WD_TABLE_ALIGNMENT.LEFT
    for cell, label, fill in zip(colors.rows[0].cells, ["Ink\n#111526", "Blue\n#2F63F1", "Violet\n#6941C6", "Teal\n#20B6A5", "Paper\n#F5F7FC"], ["111526","2F63F1","6941C6","20B6A5","F5F7FC"]):
        shade_cell(cell, fill); set_cell_margins(cell, 220, 80, 220, 80)
        rr = cell.paragraphs[0].add_run(label); rr.bold = True; rr.font.name = "Segoe UI"; rr.font.size = Pt(9); rr.font.color.rgb = RGBColor(17,21,38) if fill == "F5F7FC" else RGBColor(255,255,255)
    doc.add_paragraph()
    rules = [
        "Шрифт: Segoe UI / Inter. Заголовок 54-72 px, плашка 31 px, подпись 20-24 px.",
        "Поля безопасности: 8% для текста, 5% для декоративной графики.",
        "Browser frame: 1480-1600 px по ширине; скругление 36 px; тень 20-24 px с прозрачностью 15-20%.",
        "Mobile frame: один телефон 435×860 px или два телефона 335-365 px по ширине.",
        "Курсор: стандартный, без подсветки. Увеличение допустимо только на целевом действии.",
        "Переходы: hard cut, dissolve 6-8 кадров, push 6 кадров. Не использовать glitch, 3D-spin и пружины.",
        "Музыка: нейтральная electronic/corporate без вокала, 95-110 BPM, под диктором около -24 LUFS short-term.",
    ]
    for item in rules:
        p = doc.add_paragraph(style=None); p.style = doc.styles["Normal"]; p.paragraph_format.left_indent = Cm(0.4); p.paragraph_format.first_line_indent = Cm(-0.4); p.paragraph_format.space_after = Pt(6)
        a = p.add_run("• "); a.bold = True; a.font.color.rgb = RGBColor(47,99,241); p.add_run(item)
    doc.add_paragraph()
    p = doc.add_paragraph(); r = p.add_run("Звук"); r.bold = True; r.font.size = Pt(15); r.font.color.rgb = RGBColor(105,65,198)
    doc.add_paragraph("В папке 05_SFX лежат оригинальные короткие звуки: click, pop, notification ping и whoosh. Использовать точечно, не чаще одного акцента на 3-5 секунд.")
    doc.add_page_break()
    # Delivery spec.
    add_doc_title(doc, "Сборка и экспорт", "Финальная проверка перед выпуском")
    checklist = [
        "Секвенция: 1920×1080, 25 fps, progressive, Rec.709.",
        "Основной голос: пики до -6 dBFS, средняя интегральная громкость около -16 LUFS.",
        "Музыка под голосом: ориентир -24 dB; автоматическое приглушение 4-6 dB.",
        "Субтитры: импортировать Shans_90sec_subtitles.srt; проверить переносы на мобильных кадрах.",
        "Экспорт master: H.264 High Profile, VBR 2-pass, target 16 Mbps, max 24 Mbps, AAC 320 kbps.",
        "Не показывать реальные пароли, TOTP-секреты, QR-коды, токены, персональные уведомления и финансовые реквизиты.",
        "Перед финалом заменить статические ориентиры на чистые записи интерфейса по Плану_записи_интерфейса.csv.",
    ]
    for idx, item in enumerate(checklist, 1):
        p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(7)
        a = p.add_run(f"{idx:02d}  "); a.bold = True; a.font.color.rgb = RGBColor(47,99,241)
        p.add_run(item)
    doc.add_paragraph()
    p = doc.add_paragraph(); r = p.add_run("Содержимое пакета"); r.bold = True; r.font.size = Pt(15); r.font.color.rgb = RGBColor(105,65,198)
    for line in [
        "01_Сценарий: сценарий DOCX, текст диктора, SRT и экранные титры.",
        "02_Монтаж: подробный CSV, EDL, Premiere markers и план записи интерфейса.",
        "03_Графика: прозрачные PNG-оверлеи, титры, рамки и фон.",
        "04_Экраны: отобранные desktop/mobile ориентиры.",
        "05_SFX: четыре оригинальных WAV 48 kHz stereo.",
        "06_Превью: аниматик и раскадровка.",
    ]:
        doc.add_paragraph(line)
    path = EDIT / "Монтажное_ТЗ_CRM_Shans_90сек.docx"
    doc.save(path)


def write_text_files() -> None:
    voice = """ТЕКСТ ДИКТОРА — CRM SHANS — 1:30

00:00-00:10
Shans — это CRM для управления личными процессами. В одном приложении собраны расписание, проекты, финансы, автомобиль, обучение, спорт и питание.

00:10-00:20
Разработчик проекта — Владимир Худовердиев. Он собрал Shans как модульную систему, где задачи, данные и уведомления работают в единой логике.

00:20-00:30
На компьютере удобно планировать день, вести съемки и проекты, контролировать бюджет, обслуживание автомобиля, отчеты и экспорт данных в Excel.

00:30-00:42
Половину обзора уделим мобильной версии. Shans устанавливается как PWA и открывает расписание без лишних переходов. Задачу можно создать, перенести или отметить выполненной.

00:42-00:53
Push-уведомления напоминают о делах, тренировках и обучении. Центр уведомлений сохраняет события, а Telegram может передавать важные сообщения в CRM.

00:53-01:04
В разделе питания быстро добавляются продукты и приемы пищи, работает поиск по каталогу, сохраняются калории, белки, жиры, углеводы и динамика веса.

01:04-01:15
Мобильный раздел тренировок хранит планы и результаты, а обучение — уроки, тесты и прогресс по курсам английского и информационных технологий.

01:15-01:22
На финальном экране покажите отчеты и Excel-экспорт: данные остаются доступными для проверки и анализа.

01:22-01:27
Авторизация и двухфакторная проверка защищают доступ к данным.

01:27-01:30
Shans — ключевые процессы в одной системе.
"""
    (SCENARIO / "Текст_диктора_CRM_Shans_90сек.txt").write_text(voice, encoding="utf-8-sig")
    readme = """МОНТАЖНЫЙ ПАКЕТ CRM SHANS — 90 СЕКУНД

Начать с файла 02_Монтаж/Монтажное_ТЗ_CRM_Shans_90сек.pdf.

Что готово:
- сценарий и текст диктора на 1:30;
- 45 секунд мобильной версии;
- SRT, монтажный CSV, EDL и маркеры Premiere;
- фирменные PNG-оверлеи Shans;
- оригинальные SFX 48 kHz;
- аниматик без озвучки и раскадровка;
- план записи недостающих чистых экранов.

Аниматик показывает композицию и темп. Статические экраны в нем являются монтажными ориентирами. Для финальной версии следует записать действия интерфейса по файлу 02_Монтаж/План_записи_интерфейса.csv.

Финальный формат: 1920×1080, 25 fps, H.264, Rec.709.
"""
    (PACKAGE / "00_README_Сначала.txt").write_text(readme, encoding="utf-8-sig")
    analysis = """АНАЛИЗ РЕФЕРЕНСА «ПЕРЕДАЧА»

Исходник: 2:44, 1920×1080, около 15 fps.

Монтажные приемы:
1. Светлый фирменный фон с тонкой линейной графикой.
2. Основной интерфейс помещен в темную браузерную рамку.
3. Ключевые этапы обозначены нижними нумерованными плашками.
4. Имя разработчика показывается отдельным lower third.
5. Используются жесткие склейки, короткие dissolve и плавное приближение.
6. Мобильный интерфейс показан в корпусе смартфона.
7. Финал короткий, без длинного призыва к действию.

Адаптация Shans:
- зеленая палитра заменена на #2F63F1, #6941C6 и #20B6A5;
- мобильный блок занимает 00:30-01:15, ровно 45 секунд;
- рекламные обещания исключены;
- акцент сделан на функциях и связности модулей.
"""
    (REFERENCE / "Анализ_референса_Передача.txt").write_text(analysis, encoding="utf-8-sig")


def make_storyboard(scene_paths: list[Path]) -> None:
    tw, th = 480, 270; label_h = 58; cols = 2
    rows = math.ceil(len(scene_paths) / cols)
    sheet = Image.new("RGB", (cols * tw, rows * (th + label_h)), "#171A22")
    d = ImageDraw.Draw(sheet)
    for i, path in enumerate(scene_paths):
        with Image.open(path) as im:
            frame = im.convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        x = (i % cols) * tw; y = (i // cols) * (th + label_h)
        sheet.paste(frame, (x, y))
        _, timecode, _, title, _, _ = SCENES[i]
        d.text((x + 12, y + th + 8), f"{i+1:02d}  {timecode}  {title}", font=font(17, semi=True), fill=WHITE)
    sheet.save(PREVIEW / "Раскадровка_Shans_90сек.jpg", quality=94)


def build_animatic(scene_paths: list[Path], ffmpeg: Path) -> None:
    clips_dir = ARTIFACT_ROOT / "animatic_clips"; clips_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    for i, (scene, meta) in enumerate(zip(scene_paths, SCENES), 1):
        duration = meta[2]; clip = clips_dir / f"scene_{i:02d}.mp4"
        frames = duration * FPS
        zoom = "min(zoom+0.00008,1.025)" if i not in (1, 10) else "min(zoom+0.00004,1.012)"
        vf = f"scale=2000:1125,zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps={FPS},format=yuv420p"
        subprocess.run([str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(scene), "-vf", vf, "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(clip)], check=True)
        clips.append(clip)
    concat = ARTIFACT_ROOT / "animatic_concat.txt"
    concat.write_text("\n".join(f"file '{p.as_posix()}'" for p in clips), encoding="utf-8")
    output = PREVIEW / "Аниматик_CRM_Shans_90сек_без_озвучки.mp4"
    subprocess.run([str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(output)], check=True)


def copy_sources() -> None:
    old = ROOT / ".codex_artifacts" / "shans_video_script" / "package"
    for src in [
        old / "Сценарий_видеообзора_CRM_Shans_90сек.docx",
        old / "Shans_90sec_subtitles.srt",
        old / "Экранные_титры_CRM_Shans_90сек.txt",
    ]:
        shutil.copy2(src, SCENARIO / src.name)
    shutil.copy2(old / "Монтажный_лист_CRM_Shans_90сек.csv", EDIT / "Монтажный_лист_CRM_Shans_90сек.csv")
    desktop = ["calendar-small-desktop.png", "workouts-weight-open-desktop.png", "push-inbox-desktop.png", "nutrition-search-desktop.png", "desktop-push-settings.png", "account-push-desktop.png"]
    mobile = ["calendar-small-mobile.png", "push-inbox-mobile-viewport.png", "nutrition-quick-entry-mobile-chrome.png", "nutrition-search-mobile.png", "workouts-weight-open-mobile.png", "english-phrase-audio-mobile-touch.png"]
    for name in desktop:
        shutil.copy2(ROOT / "_codex_chat_files" / name, SCREENS_DESKTOP / name)
    for name in mobile:
        shutil.copy2(ROOT / "_codex_chat_files" / name, SCREENS_MOBILE / name)


def main() -> None:
    PACKAGE_RESOLVED = PACKAGE.resolve()
    if ARTIFACT_ROOT.resolve() not in PACKAGE_RESOLVED.parents:
        raise RuntimeError("Unsafe package path")
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    for path in [GRAPHICS, SCREENS_DESKTOP, SCREENS_MOBILE, SFX, PREVIEW, SCENARIO, EDIT, REFERENCE]:
        path.mkdir(parents=True, exist_ok=True)
    copy_sources(); save_graphic_assets(); make_sfx(); write_edit_files(); write_text_files(); build_brief_docx()
    scenes = [
        scene_open(),
        scene_developer(),
        scene_desktop(),
        mobile_scene(ROOT / "_codex_chat_files" / "calendar-small-mobile.png", "02", "Мобильное расписание", "PWA • задачи • календарь"),
        mobile_scene(ROOT / "_codex_chat_files" / "push-inbox-mobile-viewport.png", "03", "Push и события", "Уведомления • центр событий • Telegram"),
        mobile_scene(ROOT / "_codex_chat_files" / "nutrition-quick-entry-mobile-chrome.png", "04", "Питание", "Быстрый ввод • поиск • калории и БЖУ", ROOT / "_codex_chat_files" / "nutrition-search-mobile.png"),
        mobile_scene(ROOT / "_codex_chat_files" / "workouts-weight-open-mobile.png", "05", "Тренировки и обучение", "Планы • результаты • уроки • тесты", ROOT / "_codex_chat_files" / "english-phrase-audio-mobile-touch.png"),
        scene_reports(), scene_security(), scene_end(),
    ]
    scene_paths: list[Path] = []
    for i, scene in enumerate(scenes, 1):
        path = PREVIEW / f"scene_{i:02d}.png"; scene.save(path); scene_paths.append(path)
    # Copy first and final cards into the reusable graphics folder.
    shutil.copy2(scene_paths[0], GRAPHICS / "title_open.png")
    shutil.copy2(scene_paths[-1], GRAPHICS / "title_end.png")
    make_storyboard(scene_paths)
    ffmpeg = next((ROOT / ".codex_artifacts" / "video_tools" / "imageio_ffmpeg" / "binaries").glob("ffmpeg*.exe"))
    build_animatic(scene_paths, ffmpeg)
    print(PACKAGE)


if __name__ == "__main__":
    main()
