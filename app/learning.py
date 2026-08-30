from __future__ import annotations

import json
import random
import re
import secrets
import unicodedata

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.database import get_connection
from app.it_course_content import IT_LESSONS
from app.go_course_content import GO_LESSONS
from app.html_course_content import HTML_THEMES
from app.python_course_content import PYTHON_INTERVIEW_SECTIONS, PYTHON_LESSONS
from app.python_video_course_content import PYTHON_VIDEO_LESSONS
from app.python_v2_topics_content import PYTHON_V2_TOPICS


learning_bp = Blueprint("learning", __name__)
DAILY_PASS_SCORE = 16
VIDEO_PASS_SCORE = 16
FINAL_PASS_SCORE = 24
REVIEW_BLOCK_SIZE = 5
REVIEW_QUESTIONS_PER_DAY = 2
REVIEW_PASS_PERCENT = 80
REVIEW_MILESTONES = tuple(range(REVIEW_BLOCK_SIZE, 31, REVIEW_BLOCK_SIZE))
LOCKED_FUTURE_DAYS = tuple(range(31, 61))
@learning_bp.app_template_filter("english_speech")
def _english_speech(value) -> str:
    """Return only Latin-script fragments suitable for English speech synthesis."""
    fragments = re.findall(
        r"[A-Za-z][A-Za-z0-9_+#.'/-]*(?:\s+[A-Za-z][A-Za-z0-9_+#.'/-]*)*",
        str(value or ""),
    )
    cleaned = (fragment.strip(" .-/'") for fragment in fragments)
    return "; ".join(fragment for fragment in cleaned if fragment)
_PROGRESS_TABLES = {
    "english": "english_course_progress",
    "it": "it_course_progress",
    "video": "python_video_progress",
    "python": "python_course_progress",
    "go": "go_course_progress",
    "html": "html_course_progress",
    "python_topics": "python_v2_topic_progress",
}
_FINAL_TABLES = {
    "english": "english_final_results",
    "it": "it_final_results",
    "python": "python_final_results",
    "go": "go_final_results",
    "html": "html_final_results",
    "python_topics": "python_v2_topic_final_results",
}


def _lesson(day, title, focus, words, phrases):
    return {
        "day": day,
        "title": title,
        "focus": focus,
        "words": tuple(words),
        "phrases": tuple(phrases),
    }


ENGLISH_LESSONS = (
    _lesson(
        1,
        "Приветствия и знакомство",
        "Начинаем с самых частых слов. Прочитайте английское слово вслух, затем закройте перевод и попробуйте вспомнить его самостоятельно.",
        (
            ("hello", "привет"),
            ("good morning", "доброе утро"),
            ("goodbye", "до свидания"),
            ("please", "пожалуйста"),
            ("thank you", "спасибо"),
            ("name", "имя"),
        ),
        (
            ("Hello, my name is Alex.", "Привет, меня зовут Алекс."),
            ("Thank you, goodbye!", "Спасибо, до свидания!"),
        ),
    ),
    _lesson(
        2,
        "Местоимения и глагол to be",
        "I, you, he, she, we, they заменяют имена людей. После I используйте am, после he/she — is, после you/we/they — are.",
        (
            ("I", "я"),
            ("you", "ты или вы"),
            ("he", "он"),
            ("she", "она"),
            ("we", "мы"),
            ("they", "они"),
        ),
        (
            ("I am ready.", "Я готов."),
            ("They are at home.", "Они дома."),
        ),
    ),
    _lesson(
        3,
        "Семья и друзья",
        "Учите существительные вместе с простыми фразами: my mother, your friend. Так слово сразу запоминается в полезном контексте.",
        (
            ("mother", "мама"),
            ("father", "папа"),
            ("sister", "сестра"),
            ("brother", "брат"),
            ("family", "семья"),
            ("friend", "друг"),
        ),
        (
            ("This is my family.", "Это моя семья."),
            ("She is my friend.", "Она моя подруга."),
        ),
    ),
    _lesson(
        4,
        "Числа и время",
        "Числа нужны для времени, дат и количества. Произнесите новые слова несколько раз и составьте собственный пример с каждым из них.",
        (
            ("one", "один"),
            ("two", "два"),
            ("ten", "десять"),
            ("today", "сегодня"),
            ("tomorrow", "завтра"),
            ("hour", "час"),
        ),
        (
            ("I have one hour.", "У меня есть один час."),
            ("See you tomorrow.", "Увидимся завтра."),
        ),
    ),
    _lesson(
        5,
        "Обычный день",
        "Глаголы называют действия. Запоминайте их как короткую цепочку своего дня: wake up, eat, work, study, go, sleep.",
        (
            ("wake up", "просыпаться"),
            ("work", "работать"),
            ("study", "учиться"),
            ("eat", "есть"),
            ("go", "идти или ехать"),
            ("sleep", "спать"),
        ),
        (
            ("I work every day.", "Я работаю каждый день."),
            ("I go to sleep at eleven.", "Я ложусь спать в одиннадцать."),
        ),
    ),
    _lesson(
        6,
        "Дом",
        "Связывайте слово с предметом, который видите. Посмотрите на дверь, окно или стол и назовите предмет по-английски.",
        (
            ("house", "дом"),
            ("room", "комната"),
            ("door", "дверь"),
            ("window", "окно"),
            ("table", "стол"),
            ("chair", "стул"),
        ),
        (
            ("The window is open.", "Окно открыто."),
            ("The chair is near the table.", "Стул находится рядом со столом."),
        ),
    ),
    _lesson(
        7,
        "Еда и напитки",
        "Используйте I want для желаний и I like для предпочтений. Эти две конструкции позволяют быстро составлять полезные фразы.",
        (
            ("water", "вода"),
            ("bread", "хлеб"),
            ("milk", "молоко"),
            ("coffee", "кофе"),
            ("breakfast", "завтрак"),
            ("dinner", "ужин"),
        ),
        (
            ("I want coffee, please.", "Я хочу кофе, пожалуйста."),
            ("Breakfast is ready.", "Завтрак готов."),
        ),
    ),
    _lesson(
        8,
        "Места в городе",
        "Для мест используйте конструкцию at the: at the office, at the station. Сначала запомните сами названия, затем добавляйте предлог.",
        (
            ("street", "улица"),
            ("shop", "магазин"),
            ("park", "парк"),
            ("school", "школа"),
            ("office", "офис"),
            ("station", "станция"),
        ),
        (
            ("I am at the office.", "Я в офисе."),
            ("The shop is near the park.", "Магазин находится рядом с парком."),
        ),
    ),
    _lesson(
        9,
        "Направления",
        "Чтобы понять дорогу, достаточно нескольких опорных слов. Where начинает вопрос о месте, а left, right и straight задают направление.",
        (
            ("left", "налево"),
            ("right", "направо"),
            ("straight", "прямо"),
            ("near", "рядом"),
            ("far", "далеко"),
            ("where", "где"),
        ),
        (
            ("Where is the station?", "Где находится станция?"),
            ("Go straight and turn left.", "Идите прямо и поверните налево."),
        ),
    ),
    _lesson(
        10,
        "Путешествие",
        "В поездке важнее всего узнавать ключевые существительные. Прочитайте пару слово–перевод и представьте ситуацию в аэропорту или гостинице.",
        (
            ("ticket", "билет"),
            ("train", "поезд"),
            ("plane", "самолёт"),
            ("hotel", "гостиница"),
            ("passport", "паспорт"),
            ("luggage", "багаж"),
        ),
        (
            ("I have a train ticket.", "У меня есть билет на поезд."),
            ("My luggage is at the hotel.", "Мой багаж находится в гостинице."),
        ),
    ),
    _lesson(
        11,
        "Работа",
        "Деловые слова лучше учить в реальных сочетаниях: client meeting, important task, send an email. Это быстрее переводит их в активную речь.",
        (
            ("job", "работа"),
            ("meeting", "встреча"),
            ("task", "задача"),
            ("client", "клиент"),
            ("email", "электронное письмо"),
            ("deadline", "крайний срок"),
        ),
        (
            ("I have a client meeting.", "У меня встреча с клиентом."),
            ("The deadline is tomorrow.", "Крайний срок — завтра."),
        ),
    ),
    _lesson(
        12,
        "Хобби",
        "После I like можно поставить существительное или действие. Повторяйте примеры и заменяйте одно слово своим любимым занятием.",
        (
            ("read", "читать"),
            ("music", "музыка"),
            ("film", "фильм"),
            ("photo", "фотография"),
            ("sport", "спорт"),
            ("travel", "путешествовать"),
        ),
        (
            ("I like music and films.", "Мне нравятся музыка и фильмы."),
            ("I like to travel.", "Мне нравится путешествовать."),
        ),
    ),
    _lesson(
        13,
        "Погода",
        "Описание погоды обычно начинается с It is: It is warm, It is cold. Для осадков запоминайте отдельные слова rain и snow.",
        (
            ("sun", "солнце"),
            ("rain", "дождь"),
            ("snow", "снег"),
            ("warm", "тепло"),
            ("cold", "холодно"),
            ("weather", "погода"),
        ),
        (
            ("The weather is warm today.", "Сегодня тёплая погода."),
            ("I like snow.", "Мне нравится снег."),
        ),
    ),
    _lesson(
        14,
        "Здоровье",
        "Для боли используйте hurts: My head hurts. Если нужна помощь, полезна конструкция I need a doctor.",
        (
            ("head", "голова"),
            ("hand", "рука"),
            ("doctor", "врач"),
            ("medicine", "лекарство"),
            ("pain", "боль"),
            ("healthy", "здоровый"),
        ),
        (
            ("My head hurts.", "У меня болит голова."),
            ("I need a doctor.", "Мне нужен врач."),
        ),
    ),
    _lesson(
        15,
        "Покупки",
        "How much задаёт вопрос о цене. Прилагательные cheap и expensive помогают быстро оценить стоимость.",
        (
            ("price", "цена"),
            ("money", "деньги"),
            ("buy", "покупать"),
            ("sell", "продавать"),
            ("cheap", "дешёвый"),
            ("expensive", "дорогой"),
        ),
        (
            ("How much is it?", "Сколько это стоит?"),
            ("This ticket is expensive.", "Этот билет дорогой."),
        ),
    ),
    _lesson(
        16,
        "Как часто происходит действие",
        "Слова частоты обычно ставятся перед смысловым глаголом: I usually work, I never drive. Повторите шкалу от always до never.",
        (
            ("usually", "обычно"),
            ("always", "всегда"),
            ("sometimes", "иногда"),
            ("never", "никогда"),
            ("every", "каждый"),
            ("often", "часто"),
        ),
        (
            ("I usually study in the evening.", "Я обычно учусь вечером."),
            ("She never drinks coffee.", "Она никогда не пьёт кофе."),
        ),
    ),
    _lesson(
        17,
        "Прошедшее время",
        "Для вчерашних событий используйте формы was, were, had, did и went. Пока запомните их как готовые маркеры прошлого.",
        (
            ("yesterday", "вчера"),
            ("was", "был или была"),
            ("were", "были"),
            ("had", "имел или было"),
            ("did", "делал"),
            ("went", "пошёл или поехал"),
        ),
        (
            ("I was at home yesterday.", "Вчера я был дома."),
            ("We went to the park.", "Мы ходили в парк."),
        ),
    ),
    _lesson(
        18,
        "Будущее и планы",
        "Will помогает сказать о будущем: I will work. Для планов также полезны слова next, later и soon.",
        (
            ("will", "буду"),
            ("plan", "план"),
            ("later", "позже"),
            ("next", "следующий"),
            ("soon", "скоро"),
            ("maybe", "возможно"),
        ),
        (
            ("I will call you later.", "Я позвоню тебе позже."),
            ("Maybe we will meet tomorrow.", "Возможно, мы встретимся завтра."),
        ),
    ),
    _lesson(
        19,
        "Основные прилагательные",
        "Прилагательное описывает предмет и обычно стоит перед ним: a new phone, a big house. После to be оно ставится отдельно: The house is big.",
        (
            ("big", "большой"),
            ("small", "маленький"),
            ("good", "хороший"),
            ("bad", "плохой"),
            ("new", "новый"),
            ("old", "старый"),
        ),
        (
            ("This is a good film.", "Это хороший фильм."),
            ("My phone is new.", "Мой телефон новый."),
        ),
    ),
    _lesson(
        20,
        "Вопросительные слова",
        "Ставьте вопросительное слово в начало фразы. What спрашивает о предмете, who — о человеке, when — о времени, why — о причине.",
        (
            ("what", "что"),
            ("who", "кто"),
            ("when", "когда"),
            ("why", "почему"),
            ("how", "как"),
            ("which", "который"),
        ),
        (
            ("What is your name?", "Как тебя зовут?"),
            ("When is the meeting?", "Когда встреча?"),
        ),
    ),
    _lesson(
        21,
        "Предлоги места",
        "Предлоги показывают положение предмета. Возьмите любой предмет рядом и проговорите: on the table, under the chair, behind the door.",
        (
            ("in", "внутри"),
            ("on", "на"),
            ("under", "под"),
            ("behind", "за"),
            ("between", "между"),
            ("next to", "рядом с"),
        ),
        (
            ("The phone is on the table.", "Телефон лежит на столе."),
            ("The shop is next to the hotel.", "Магазин находится рядом с гостиницей."),
        ),
    ),
    _lesson(
        22,
        "Транспорт",
        "Используйте by с видом транспорта: by bus, by taxi. Для действий пригодятся drive — управлять машиной и walk — идти пешком.",
        (
            ("car", "машина"),
            ("bus", "автобус"),
            ("taxi", "такси"),
            ("bicycle", "велосипед"),
            ("drive", "водить"),
            ("walk", "идти пешком"),
        ),
        (
            ("I go to work by car.", "Я езжу на работу на машине."),
            ("We can walk to the station.", "Мы можем дойти до станции пешком."),
        ),
    ),
    _lesson(
        23,
        "Технологии",
        "Эти слова встречаются в интерфейсах каждый день. Проговаривайте действие вместе с объектом: open a file, send a message, use a website.",
        (
            ("computer", "компьютер"),
            ("phone", "телефон"),
            ("website", "сайт"),
            ("password", "пароль"),
            ("file", "файл"),
            ("message", "сообщение"),
        ),
        (
            ("Send me the file, please.", "Отправь мне файл, пожалуйста."),
            ("I forgot my password.", "Я забыл свой пароль."),
        ),
    ),
    _lesson(
        24,
        "Общение",
        "Speak описывает речь вообще, say — произнесённые слова, tell — информацию для человека. Ask и answer образуют полезную пару.",
        (
            ("speak", "говорить"),
            ("say", "сказать"),
            ("tell", "рассказать"),
            ("ask", "спросить"),
            ("answer", "ответить"),
            ("understand", "понимать"),
        ),
        (
            ("Please speak slowly.", "Пожалуйста, говорите медленно."),
            ("I understand your question.", "Я понимаю ваш вопрос."),
        ),
    ),
    _lesson(
        25,
        "Сравнение",
        "More и less меняют количество, а better и worse сравнивают качество. Формы faster и slower сравнивают скорость.",
        (
            ("more", "больше"),
            ("less", "меньше"),
            ("better", "лучше"),
            ("worse", "хуже"),
            ("faster", "быстрее"),
            ("slower", "медленнее"),
        ),
        (
            ("This result is better.", "Этот результат лучше."),
            ("Please speak slower.", "Пожалуйста, говорите медленнее."),
        ),
    ),
    _lesson(
        26,
        "Просьбы",
        "Can you — простая просьба, Could you — более вежливая. После них ставьте действие без дополнительных окончаний.",
        (
            ("can", "мочь"),
            ("could", "могли бы"),
            ("help", "помочь"),
            ("need", "нуждаться"),
            ("want", "хотеть"),
            ("wait", "ждать"),
        ),
        (
            ("Could you help me?", "Вы могли бы мне помочь?"),
            ("Please wait one minute.", "Пожалуйста, подождите одну минуту."),
        ),
    ),
    _lesson(
        27,
        "Расписание и встречи",
        "Для договорённостей запоминайте целые блоки: free at five, busy today, early meeting, late appointment.",
        (
            ("appointment", "назначенная встреча"),
            ("schedule", "расписание"),
            ("free", "свободный"),
            ("busy", "занятый"),
            ("early", "рано"),
            ("late", "поздно"),
        ),
        (
            ("I am free after six.", "Я свободен после шести."),
            ("The meeting starts early.", "Встреча начинается рано."),
        ),
    ),
    _lesson(
        28,
        "Последовательный рассказ",
        "Связки first, then и finally задают порядок. Before и after связывают время, because объясняет причину.",
        (
            ("first", "сначала"),
            ("then", "затем"),
            ("after", "после"),
            ("before", "до"),
            ("because", "потому что"),
            ("finally", "наконец"),
        ),
        (
            ("First we work, then we rest.", "Сначала мы работаем, затем отдыхаем."),
            ("I stayed home because it was cold.", "Я остался дома, потому что было холодно."),
        ),
    ),
    _lesson(
        29,
        "Поддержание разговора",
        "Эти глаголы помогают выражать мнение и состояние. Начинайте фразу с I think, I know, I like или I feel.",
        (
            ("think", "думать"),
            ("know", "знать"),
            ("like", "нравиться"),
            ("feel", "чувствовать"),
            ("agree", "соглашаться"),
            ("remember", "помнить"),
        ),
        (
            ("I think this is a good plan.", "Я думаю, что это хороший план."),
            ("I agree with you.", "Я согласен с вами."),
        ),
    ),
    _lesson(
        30,
        "Повторение и подготовка к финалу",
        "Последний день посвящён активному повторению. Ошибка — часть обучения: найдите неверный ответ, повторите перевод и составьте новую фразу.",
        (
            ("learn", "изучать"),
            ("repeat", "повторять"),
            ("practice", "практиковаться"),
            ("mistake", "ошибка"),
            ("correct", "правильный"),
            ("result", "результат"),
        ),
        (
            ("Practice English every day.", "Практикуйте английский каждый день."),
            ("A mistake helps me learn.", "Ошибка помогает мне учиться."),
        ),
    ),
)


def _create_live_quiz_attempts_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_quiz_attempts (
            user_id INTEGER NOT NULL,
            course_key TEXT NOT NULL,
            item_number INTEGER NOT NULL,
            seed INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, course_key, item_number)
        )
        """
    )


def init_learning_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS english_course_progress (
                user_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS english_final_results (
                user_id INTEGER PRIMARY KEY,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS it_course_progress (
                user_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS it_final_results (
                user_id INTEGER PRIMARY KEY,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS python_video_progress (
                user_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS python_course_progress (
                user_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS python_final_results (
                user_id INTEGER PRIMARY KEY,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS python_interview_progress (
                user_id INTEGER NOT NULL,
                section_number INTEGER NOT NULL,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, section_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS go_course_progress (
                user_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS go_final_results (
                user_id INTEGER PRIMARY KEY,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS html_course_progress (
                user_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS html_final_results (
                user_id INTEGER PRIMARY KEY,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS python_v2_topic_progress (
                user_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, day_number)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS python_v2_topic_final_results (
                user_id INTEGER PRIMARY KEY,
                best_score INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _create_live_quiz_attempts_table(conn)
        conn.commit()
    finally:
        conn.close()


def _course_table(course_key: str, table_map: dict[str, str]) -> str:
    try:
        return table_map[course_key]
    except KeyError as exc:
        raise ValueError("Неизвестный учебный курс.") from exc


def _get_course_progress(user_id: int, course_key: str) -> dict[int, dict]:
    table_name = _course_table(course_key, _PROGRESS_TABLES)
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT day_number, best_score, attempts, passed, completed_at
            FROM {table_name}
            WHERE user_id = ?
            ORDER BY day_number
            """,
            (user_id,),
        ).fetchall()
        return {int(row["day_number"]): dict(row) for row in rows}
    finally:
        conn.close()


def _get_course_final_result(user_id: int, course_key: str) -> dict | None:
    table_name = _course_table(course_key, _FINAL_TABLES)
    conn = get_connection()
    try:
        row = conn.execute(
            f"""
            SELECT best_score, attempts, passed, completed_at
            FROM {table_name}
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _save_course_day_result(
    user_id: int,
    day_number: int,
    score: int,
    passed: bool,
    course_key: str,
) -> None:
    table_name = _course_table(course_key, _PROGRESS_TABLES)
    conn = get_connection()
    try:
        conn.execute(
            f"""
            INSERT INTO {table_name} (
                user_id,
                day_number,
                best_score,
                attempts,
                passed,
                completed_at
            ) VALUES (?, ?, ?, 1, ?, CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END)
            ON CONFLICT(user_id, day_number) DO UPDATE SET
                best_score = MAX({table_name}.best_score, excluded.best_score),
                attempts = {table_name}.attempts + 1,
                passed = MAX({table_name}.passed, excluded.passed),
                completed_at = CASE
                    WHEN {table_name}.completed_at IS NOT NULL
                        THEN {table_name}.completed_at
                    WHEN excluded.passed = 1
                        THEN CURRENT_TIMESTAMP
                    ELSE NULL
                END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, day_number, score, int(passed), int(passed)),
        )
        conn.commit()
    finally:
        conn.close()


def _reset_course_day_result(user_id: int, day_number: int, course_key: str) -> None:
    table_name = _course_table(course_key, _PROGRESS_TABLES)
    conn = get_connection()
    try:
        conn.execute(
            f"""
            DELETE FROM {table_name}
            WHERE user_id = ? AND day_number = ?
            """,
            (user_id, day_number),
        )
        conn.commit()
    finally:
        conn.close()


def _save_course_final_result(
    user_id: int,
    score: int,
    passed: bool,
    course_key: str,
) -> None:
    table_name = _course_table(course_key, _FINAL_TABLES)
    conn = get_connection()
    try:
        conn.execute(
            f"""
            INSERT INTO {table_name} (
                user_id,
                best_score,
                attempts,
                passed,
                completed_at
            ) VALUES (?, ?, 1, ?, CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END)
            ON CONFLICT(user_id) DO UPDATE SET
                best_score = MAX({table_name}.best_score, excluded.best_score),
                attempts = {table_name}.attempts + 1,
                passed = MAX({table_name}.passed, excluded.passed),
                completed_at = CASE
                    WHEN {table_name}.completed_at IS NOT NULL
                        THEN {table_name}.completed_at
                    WHEN excluded.passed = 1
                        THEN CURRENT_TIMESTAMP
                    ELSE NULL
                END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, score, int(passed), int(passed)),
        )
        conn.commit()
    finally:
        conn.close()


def _reset_course_final_result(user_id: int, course_key: str) -> None:
    table_name = _course_table(course_key, _FINAL_TABLES)
    conn = get_connection()
    try:
        conn.execute(
            f"""
            DELETE FROM {table_name}
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _get_progress(user_id: int) -> dict[int, dict]:
    return _get_course_progress(user_id, "english")


def _get_final_result(user_id: int) -> dict | None:
    return _get_course_final_result(user_id, "english")


def _save_day_result(user_id: int, day_number: int, score: int, passed: bool) -> None:
    _save_course_day_result(user_id, day_number, score, passed, "english")


def _reset_day_result(user_id: int, day_number: int) -> None:
    _reset_course_day_result(user_id, day_number, "english")


def _save_final_result(user_id: int, score: int, passed: bool) -> None:
    _save_course_final_result(user_id, score, passed, "english")


def _reset_final_result(user_id: int) -> None:
    _reset_course_final_result(user_id, "english")


def _get_it_progress(user_id: int) -> dict[int, dict]:
    return _get_course_progress(user_id, "it")


def _get_it_final_result(user_id: int) -> dict | None:
    return _get_course_final_result(user_id, "it")


def _save_it_day_result(
    user_id: int,
    day_number: int,
    score: int,
    passed: bool,
) -> None:
    _save_course_day_result(user_id, day_number, score, passed, "it")


def _reset_it_day_result(user_id: int, day_number: int) -> None:
    _reset_course_day_result(user_id, day_number, "it")


def _save_it_final_result(user_id: int, score: int, passed: bool) -> None:
    _save_course_final_result(user_id, score, passed, "it")


def _reset_it_final_result(user_id: int) -> None:
    _reset_course_final_result(user_id, "it")


def _rotated_options(correct: str, distractors, seed: int) -> tuple[tuple[str, ...], int]:
    unique_options = [correct]
    for distractor in distractors:
        if distractor not in unique_options:
            unique_options.append(distractor)
        if len(unique_options) == 4:
            break
    if len(unique_options) < 4:
        raise ValueError("Недостаточно вариантов ответа для теста.")
    shift = seed % len(unique_options)
    options = tuple(unique_options[shift:] + unique_options[:shift])
    return options, options.index(correct)


def _text_question(question: dict, answer: str, prompt: str) -> dict:
    return {
        **question,
        "answer_type": "text",
        "prompt": prompt,
        "accepted_answers": (answer,),
        "answer_hint": "Напишите ответ самостоятельно, без вариантов.",
    }


def _multi_pair_question(items, seed: int, noun: str) -> dict:
    """Create a comprehension task with exactly two valid term/value pairs."""
    values = tuple(items)
    first = seed % len(values)
    second = (first + 2) % len(values)
    correct = (
        f"{values[first][0]} — {values[first][1]}",
        f"{values[second][0]} — {values[second][1]}",
    )
    wrong = (
        f"{values[first][0]} — {values[(first + 1) % len(values)][1]}",
        f"{values[second][0]} — {values[(second + 1) % len(values)][1]}",
    )
    options = list(correct + wrong)
    random.Random(seed).shuffle(options)
    return {
        "answer_type": "multiple",
        "prompt": f"Выберите ровно две правильно составленные пары «{noun} — значение».",
        "options": tuple(options),
        "correct_indices": tuple(index for index, option in enumerate(options) if option in correct),
        "explanation": "Правильные пары: " + "; ".join(correct) + ".",
        "answer_hint": "Правильных вариантов два. Лишняя отметка считается ошибкой.",
    }


def shuffle_quiz(questions: list[dict], seed: int) -> list[dict]:
    """Shuffle questions and choices while preserving every answer contract."""
    rng = random.Random(seed)
    shuffled_questions = []
    for original in questions:
        question = dict(original)
        answer_type = question.get("answer_type", "single")
        if answer_type == "single":
            correct_answer = question["options"][question["correct_index"]]
            options = list(question["options"])
            rng.shuffle(options)
            question["options"] = tuple(options)
            question["correct_index"] = options.index(correct_answer)
        elif answer_type == "multiple":
            correct_answers = {
                question["options"][index] for index in question["correct_indices"]
            }
            options = list(question["options"])
            rng.shuffle(options)
            question["options"] = tuple(options)
            question["correct_indices"] = tuple(
                index for index, option in enumerate(options) if option in correct_answers
            )
        shuffled_questions.append(question)
    rng.shuffle(shuffled_questions)
    return shuffled_questions


def build_daily_quiz(day_number: int) -> list[dict]:
    lesson = ENGLISH_LESSONS[day_number - 1]
    words = lesson["words"]
    questions = []
    for question_index, (english, russian) in enumerate(words):
        options, correct_index = _rotated_options(
            russian,
            (item[1] for item in words if item[0] != english),
            day_number + question_index,
        )
        questions.append(
            {
                "prompt": f"Как переводится «{english}»?",
                "options": options,
                "correct_index": correct_index,
                "explanation": f"{english} — {russian}.",
            }
        )

    for question_index, (english, russian) in enumerate(words):
        options, correct_index = _rotated_options(
            english,
            (item[0] for item in words if item[0] != english),
            day_number + 10 + question_index,
        )
        questions.append({
            "prompt": f"Выберите английский перевод: «{russian}».",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"{russian} — {english}.",
        })

    for question_index, (phrase_english, phrase_russian) in enumerate(lesson["phrases"]):
        phrase_distractors = (
            other_lesson["phrases"][question_index % 2][1]
            for other_lesson in ENGLISH_LESSONS
            if other_lesson["day"] != day_number
        )
        options, correct_index = _rotated_options(
            phrase_russian, phrase_distractors, day_number + 20 + question_index
        )
        questions.append({
            "prompt": f"Как переводится предложение «{phrase_english}»?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"{phrase_english} — {phrase_russian}.",
        })
        reverse_options, reverse_correct_index = _rotated_options(
            phrase_english,
            (
                other_lesson["phrases"][question_index % 2][0]
                for other_lesson in ENGLISH_LESSONS
                if other_lesson["day"] != day_number
            ),
            day_number + 30 + question_index,
        )
        questions.append({
            "prompt": f"Выберите английское предложение: «{phrase_russian}».",
            "options": reverse_options,
            "correct_index": reverse_correct_index,
            "explanation": f"{phrase_russian} — {phrase_english}.",
        })

    for question_index, (english, russian) in enumerate(words[:4]):
        correct_pair = f"{english} — {russian}"
        distractors = (
            f"{other_english} — {words[(other_index + 1) % len(words)][1]}"
            for other_index, (other_english, _other_russian) in enumerate(words)
            if other_english != english
        )
        options, correct_index = _rotated_options(
            correct_pair, distractors, day_number + 40 + question_index
        )
        questions.append({
            "prompt": "Какая пара «слово — перевод» составлена верно?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"Верная пара: {correct_pair}.",
        })
    questions[0] = _text_question(questions[0], words[0][1], f"Напишите перевод слова «{words[0][0]}»." )
    questions[1] = _text_question(questions[1], words[1][1], f"Напишите перевод слова «{words[1][0]}»." )
    questions[6] = _text_question(questions[6], words[0][0], f"Напишите по-английски: «{words[0][1]}»." )
    questions[7] = _text_question(questions[7], words[1][0], f"Напишите по-английски: «{words[1][1]}»." )
    questions[12] = _text_question(questions[12], lesson["phrases"][0][1], f"Переведите самостоятельно: «{lesson['phrases'][0][0]}»." )
    questions[13] = _text_question(questions[13], lesson["phrases"][0][0], f"Напишите по-английски: «{lesson['phrases'][0][1]}»." )
    questions[18] = _multi_pair_question(words, day_number + 101, "слово")
    questions[19] = _multi_pair_question(words, day_number + 202, "слово")
    return questions


def build_final_quiz() -> list[dict]:
    questions = []
    for lesson in ENGLISH_LESSONS:
        word_index = (lesson["day"] - 1) % len(lesson["words"])
        english, russian = lesson["words"][word_index]
        distractors = (
            other_lesson["words"][word_index % len(other_lesson["words"])][1]
            for other_lesson in ENGLISH_LESSONS
            if other_lesson["day"] != lesson["day"]
        )
        options, correct_index = _rotated_options(
            russian,
            distractors,
            lesson["day"],
        )
        questions.append(
            {
                "prompt": f"Как переводится «{english}»?",
                "options": options,
                "correct_index": correct_index,
                "explanation": f"{english} — {russian}.",
            }
        )
    return questions


def build_it_daily_quiz(day_number: int) -> list[dict]:
    lesson = IT_LESSONS[day_number - 1]
    terms = lesson["terms"]
    questions = []
    for question_index, (term, definition) in enumerate(terms):
        options, correct_index = _rotated_options(
            definition,
            (item[1] for item in terms if item[0] != term),
            day_number + question_index,
        )
        questions.append(
            {
                "day": lesson["day"],
                "prompt": f"Что означает термин «{term}»?",
                "options": options,
                "correct_index": correct_index,
                "explanation": f"{term} — {definition}.",
            }
        )

    for question_index, (term, definition) in enumerate(terms[:6]):
        options, correct_index = _rotated_options(
            term,
            (item[0] for item in terms if item[0] != term),
            day_number + 10 + question_index,
        )
        questions.append({
            "day": lesson["day"],
            "prompt": f"Какой термин означает «{definition}»?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"{definition} — это {term}.",
        })

    questions.append({"day": lesson["day"], **_multi_pair_question(terms, day_number + 301, "термин")})
    questions.append({"day": lesson["day"], **_multi_pair_question(terms, day_number + 402, "термин")})
    questions.append({"day": lesson["day"], **dict(lesson["checkpoint"])})
    title_options, title_correct_index = _rotated_options(
        lesson["title"],
        (item["title"] for item in IT_LESSONS if item["day"] != day_number),
        day_number + 30,
    )
    questions.append({
        "day": lesson["day"],
        "prompt": f"К какой теме относится описание: «{lesson['summary']}»?",
        "options": title_options,
        "correct_index": title_correct_index,
        "explanation": f"Это описание темы «{lesson['title']}».",
    })
    for index in range(3):
        term, definition = terms[index]
        questions[10 + index] = _text_question(
            questions[10 + index], term, f"Восстановите термин по определению: «{definition}»."
        )
    return questions


def build_go_daily_quiz(day_number: int) -> list[dict]:
    if not 1 <= day_number <= len(GO_LESSONS):
        raise ValueError("Unknown Go lesson")
    lesson = GO_LESSONS[day_number - 1]
    terms = lesson["terms"]
    questions = []
    for index, (term, definition) in enumerate(terms):
        options, correct_index = _rotated_options(
            definition,
            (candidate[1] for candidate in terms if candidate[0] != term),
            day_number * 100 + index,
        )
        questions.append({
            "day": day_number,
            "prompt": f"Что означает «{term}» в Go?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"{term} — {definition}.",
        })
    for index, (term, definition) in enumerate(terms):
        options, correct_index = _rotated_options(
            term,
            (candidate[0] for candidate in terms if candidate[0] != term),
            day_number * 200 + index,
        )
        questions.append({
            "day": day_number,
            "prompt": f"Какое понятие соответствует объяснению: «{definition}»?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"Правильное понятие — {term}.",
        })
    for offset in range(4):
        term, definition = terms[offset]
        options, correct_index = _rotated_options(
            f"{term} — {definition}",
            (f"{other_term} — {other_definition}" for other_term, other_definition in terms if other_term != term),
            day_number * 300 + offset,
        )
        questions.append({
            "day": day_number,
            "prompt": f"Выберите корректную пару из урока «{lesson['title']}».",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"Корректная пара: {term} — {definition}.",
        })
    return questions


def build_html_theme_quiz(theme_number: int) -> list[dict]:
    if not 1 <= theme_number <= len(HTML_THEMES):
        raise ValueError("Unknown HTML theme")
    theme = HTML_THEMES[theme_number - 1]
    terms = theme["terms"]
    questions = []
    for index, (term, definition) in enumerate(terms):
        options, correct_index = _rotated_options(
            definition,
            (candidate[1] for candidate in terms if candidate[0] != term),
            theme_number * 100 + index,
        )
        questions.append({
            "day": theme_number,
            "prompt": f"Что означает «{term}» в теме HTML?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"{term} — {definition}.",
        })
    for index, (term, definition) in enumerate(terms):
        options, correct_index = _rotated_options(
            term,
            (candidate[0] for candidate in terms if candidate[0] != term),
            theme_number * 200 + index,
        )
        questions.append({
            "day": theme_number,
            "prompt": f"Какое понятие соответствует объяснению: «{definition}»?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"Правильное понятие — {term}.",
        })
    for offset in range(4):
        term, definition = terms[offset]
        options, correct_index = _rotated_options(
            f"{term} — {definition}",
            (f"{other_term} — {other_definition}" for other_term, other_definition in terms if other_term != term),
            theme_number * 300 + offset,
        )
        questions.append({
            "day": theme_number,
            "prompt": f"Выберите корректную пару из темы «{theme['title']}».",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"Корректная пара: {term} — {definition}.",
        })
    return questions


def build_python_v2_topic_quiz(topic_number: int) -> list[dict]:
    if not 1 <= topic_number <= len(PYTHON_V2_TOPICS):
        raise ValueError("Unknown Python v2 topic")
    topic = PYTHON_V2_TOPICS[topic_number - 1]
    terms = topic["terms"]
    questions = []
    for index, (term, definition) in enumerate(terms):
        options, correct_index = _rotated_options(
            definition,
            (candidate[1] for candidate in terms if candidate[0] != term),
            topic_number * 100 + index,
        )
        questions.append({"day": topic_number, "prompt": f"Что означает «{term}» в Python?", "options": options,
                          "correct_index": correct_index, "explanation": f"{term} — {definition}."})
    for index, (term, definition) in enumerate(terms):
        options, correct_index = _rotated_options(
            term,
            (candidate[0] for candidate in terms if candidate[0] != term),
            topic_number * 200 + index,
        )
        questions.append({"day": topic_number, "prompt": f"Какое понятие соответствует объяснению: «{definition}»?",
                          "options": options, "correct_index": correct_index,
                          "explanation": f"Правильное понятие — {term}."})
    for offset in range(4):
        term, definition = terms[offset]
        options, correct_index = _rotated_options(
            f"{term} — {definition}",
            (f"{other_term} — {other_definition}" for other_term, other_definition in terms if other_term != term),
            topic_number * 300 + offset,
        )
        questions.append({"day": topic_number, "prompt": f"Выберите корректную пару из темы «{topic['title']}».",
                          "options": options, "correct_index": correct_index,
                          "explanation": f"Корректная пара: {term} — {definition}."})
    return questions


def build_it_final_quiz() -> list[dict]:
    questions = []
    for lesson in IT_LESSONS:
        term_index = (lesson["day"] - 1) % len(lesson["terms"])
        term, definition = lesson["terms"][term_index]
        distractors = (
            other_lesson["terms"][
                term_index % len(other_lesson["terms"])
            ][1]
            for other_lesson in IT_LESSONS
            if other_lesson["day"] != lesson["day"]
        )
        options, correct_index = _rotated_options(
            definition,
            distractors,
            lesson["day"],
        )
        questions.append(
            {
                "day": lesson["day"],
                "prompt": f"Что означает термин «{term}»?",
                "options": options,
                "correct_index": correct_index,
                "explanation": f"{term} — {definition}.",
            }
        )
    return questions


def build_python_daily_quiz(day_number: int) -> list[dict]:
    lesson = PYTHON_LESSONS[day_number - 1]
    terms = lesson["terms"]
    questions = []
    for question_index, (term, definition) in enumerate(terms):
        options, correct_index = _rotated_options(
            definition, (item[1] for item in terms if item[0] != term), day_number + question_index
        )
        questions.append({"day": day_number, "prompt": f"Что означает «{term}»?", "options": options,
                          "correct_index": correct_index, "explanation": f"{term} — {definition}."})
    for question_index, (term, definition) in enumerate(terms):
        options, correct_index = _rotated_options(
            term, (item[0] for item in terms if item[0] != term), day_number + 20 + question_index
        )
        questions.append({"day": day_number, "prompt": f"Какое понятие означает «{definition}»?",
                          "options": options, "correct_index": correct_index,
                          "explanation": f"Это понятие — {term}."})
    questions.append({"day": day_number, **_multi_pair_question(terms, day_number + 501, "понятие")})
    questions.append({"day": day_number, **_multi_pair_question(terms, day_number + 602, "понятие")})
    questions.append({"day": day_number, **dict(lesson["checkpoint"])})
    title_options, title_correct_index = _rotated_options(
        lesson["title"], (item["title"] for item in PYTHON_LESSONS if item["day"] != day_number), day_number + 40
    )
    questions.append({"day": day_number, "prompt": f"К какой теме относится: «{lesson['summary']}»?",
                      "options": title_options, "correct_index": title_correct_index,
                      "explanation": f"Это тема «{lesson['title']}»."})
    for index in range(3):
        term, definition = terms[index]
        questions[10 + index] = _text_question(
            questions[10 + index], term, f"Восстановите понятие: «{definition}»."
        )
    return questions


def build_python_final_quiz() -> list[dict]:
    questions = []
    for lesson in PYTHON_LESSONS:
        term_index = (lesson["day"] - 1) % len(lesson["terms"])
        term, definition = lesson["terms"][term_index]
        distractors = (
            other["terms"][term_index % len(other["terms"])][1]
            for other in PYTHON_LESSONS if other["day"] != lesson["day"]
        )
        options, correct_index = _rotated_options(definition, distractors, lesson["day"] + 900)
        questions.append({"day": lesson["day"], "prompt": f"Что означает «{term}»?", "options": options,
                          "correct_index": correct_index, "explanation": f"{term} — {definition}."})
    return questions


def build_review_quiz(course_key: str, end_day: int, seed: int) -> list[dict]:
    """Build a repeatable shuffled quiz for the five-day block ending at end_day."""
    if course_key not in {"english", "it", "python"} or end_day not in REVIEW_MILESTONES:
        raise ValueError("Некорректный блок повторения.")

    quiz_builder = {"english": build_daily_quiz, "it": build_it_daily_quiz, "python": build_python_daily_quiz}[course_key]
    rng = random.Random(seed)
    questions = []
    first_day = end_day - REVIEW_BLOCK_SIZE + 1
    for day_number in range(first_day, end_day + 1):
        daily_questions = quiz_builder(day_number)
        for question in rng.sample(daily_questions, REVIEW_QUESTIONS_PER_DAY):
            shuffled_question = dict(question)
            if question.get("answer_type", "single") == "single":
                correct_answer = question["options"][question["correct_index"]]
                shuffled_options = list(question["options"])
                rng.shuffle(shuffled_options)
                shuffled_question["options"] = tuple(shuffled_options)
                shuffled_question["correct_index"] = shuffled_options.index(correct_answer)
            shuffled_question["day"] = day_number
            questions.append(shuffled_question)
    rng.shuffle(questions)
    return questions


def build_video_lesson_quiz(lesson_number: int, seed: int) -> list[dict]:
    if lesson_number < 1 or lesson_number > len(PYTHON_VIDEO_LESSONS):
        raise ValueError("Некорректный номер видеоурока.")
    lesson = PYTHON_VIDEO_LESSONS[lesson_number - 1]
    rng = random.Random(seed)
    questions = []
    facts = lesson["facts"]
    for index, (term, definition) in enumerate(facts):
        options, correct_index = _rotated_options(
            definition,
            (item[1] for item in lesson["facts"] if item[0] != term),
            seed + index,
        )
        questions.append(
            {
                "prompt": f"Что в этом уроке означает «{term}»?",
                "options": options,
                "correct_index": correct_index,
                "explanation": f"{term} — {definition}.",
            }
        )
    for index, (term, definition) in enumerate(facts):
        options, correct_index = _rotated_options(
            term,
            (item[0] for item in facts if item[0] != term),
            seed + 10 + index,
        )
        questions.append({
            "prompt": f"Какое понятие означает «{definition}»?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"{definition} — это {term}.",
        })
    for index, (term, definition) in enumerate(facts):
        correct_pair = f"{term} — {definition}"
        distractors = (
            f"{other_term} — {facts[(other_index + 1) % len(facts)][1]}"
            for other_index, (other_term, _other_definition) in enumerate(facts)
            if other_term != term
        )
        options, correct_index = _rotated_options(correct_pair, distractors, seed + 20 + index)
        questions.append({
            "prompt": "Какая пара из видео составлена правильно?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"Верная пара: {correct_pair}.",
        })
    for index, (term, definition) in enumerate(facts):
        correct_statement = f"{term} означает: {definition}"
        distractors = (
            f"{term} означает: {other_definition}"
            for other_term, other_definition in facts
            if other_term != term
        )
        options, correct_index = _rotated_options(correct_statement, distractors, seed + 30 + index)
        questions.append({
            "prompt": f"Какое утверждение о «{term}» верно?",
            "options": options,
            "correct_index": correct_index,
            "explanation": correct_statement + ".",
        })
    correct_pairs = [f"{term} — {definition}" for term, definition in facts]
    for index, (term, _definition) in enumerate(facts):
        wrong_pair = f"{term} — {facts[(index + 1) % len(facts)][1]}"
        options, correct_index = _rotated_options(
            wrong_pair,
            (pair for pair in correct_pairs if not pair.startswith(f"{term} —")),
            seed + 40 + index,
        )
        questions.append({
            "prompt": "Какая пара составлена ошибочно?",
            "options": options,
            "correct_index": correct_index,
            "explanation": f"Ошибочная пара: {wrong_pair}. Правильное значение термина дано в разборе видео.",
        })
    for index in range(3):
        term, definition = facts[index]
        questions[4 + index] = _text_question(
            questions[4 + index], term, f"Без вариантов назовите понятие: «{definition}»."
        )
    questions[10] = _multi_pair_question(facts, seed + 501, "понятие")
    questions[11] = _multi_pair_question(facts, seed + 602, "понятие")
    rng.shuffle(questions)
    return questions


def build_extra_quiz(course_key: str, current_number: int, question_count: int, seed: int) -> list[dict]:
    """Build deterministic remediation questions from the current lesson only."""
    builders = {
        "english": (len(ENGLISH_LESSONS), lambda number: build_daily_quiz(number)),
        "it": (len(IT_LESSONS), lambda number: build_it_daily_quiz(number)),
        "video": (len(PYTHON_VIDEO_LESSONS), lambda number: build_video_lesson_quiz(number, seed + number)),
        "python": (len(PYTHON_LESSONS), lambda number: build_python_daily_quiz(number)),
    }
    if course_key not in builders or question_count < 1:
        raise ValueError("Некорректные параметры дополнительного теста.")
    lesson_count, builder = builders[course_key]
    if not 1 <= current_number <= lesson_count:
        raise ValueError("Некорректный номер урока.")
    pool = [{**question, "source_number": current_number} for question in builder(current_number)]
    rng = random.Random(seed)
    selected = []
    while len(selected) < question_count:
        cycle = list(pool)
        rng.shuffle(cycle)
        selected.extend(dict(question) for question in cycle[: question_count - len(selected)])
    return shuffle_quiz(selected, seed + 7919)


def _extra_quiz_key(course_key: str, item_number: int) -> str:
    return f"extra_quiz:{course_key}:{item_number}"


def _extra_question_count(wrong_count: int) -> int:
    if wrong_count < 1:
        raise ValueError("Дополнительные вопросы нужны только при наличии ошибок.")
    return wrong_count * 2


def _extra_stage_passed(correct_count: int, question_count: int) -> bool:
    """Allow one remediation mistake; two mistakes require a full lesson retry."""
    if question_count < 0 or not 0 <= correct_count <= question_count:
        raise ValueError("Некорректный результат дополнительных вопросов.")
    return question_count - correct_count < 2


def _start_extra_quiz(course_key: str, item_number: int, base_score: int, base_total: int) -> tuple[list[dict], int]:
    wrong_count = base_total - base_score
    extra_count = _extra_question_count(wrong_count)
    seed = secrets.randbelow(2**31)
    session[_extra_quiz_key(course_key, item_number)] = {
        "base_score": base_score,
        "base_total": base_total,
        "extra_count": extra_count,
        "seed": seed,
    }
    return build_extra_quiz(course_key, item_number, extra_count, seed), wrong_count


def _finish_extra_quiz(course_key: str, item_number: int, form) -> tuple[int, int, int, list[dict], bool]:
    state = session.pop(_extra_quiz_key(course_key, item_number), None)
    if not isinstance(state, dict):
        abort(400)
    try:
        base_score = int(state["base_score"])
        base_total = int(state["base_total"])
        extra_count = int(state["extra_count"])
        seed = int(state["seed"])
    except (KeyError, TypeError, ValueError):
        abort(400)
    if base_total != 20 or not 0 <= base_score < base_total or extra_count != _extra_question_count(base_total - base_score):
        abort(400)
    questions = build_extra_quiz(course_key, item_number, extra_count, seed)
    extra_score, feedback = grade_quiz(questions, form)
    total_score = base_score + extra_score
    total_questions = base_total + extra_count
    passed = _extra_stage_passed(extra_score, extra_count)
    pass_score = total_score if passed else total_score + 1
    return total_score, total_questions, pass_score, feedback, passed


def _stored_score(score: int, total_questions: int) -> int:
    """Keep existing progress columns comparable on their established 20-point scale."""
    return round(score / total_questions * 20)


def _live_quiz_key(course_key: str, item_number: int, seed: int) -> str:
    return f"live_quiz:{course_key}:{item_number}:{seed}"


def _live_quiz_seed_key(course_key: str, item_number: int) -> str:
    return f"live_quiz_seed:{course_key}:{item_number}"


def _live_quiz_connection():
    """Open quiz storage and migrate existing per-user databases on first use."""
    conn = get_connection()
    _create_live_quiz_attempts_table(conn)
    return conn


def _load_live_quiz_attempt(user_id: int, course_key: str, item_number: int) -> dict | None:
    conn = _live_quiz_connection()
    try:
        row = conn.execute(
            """
            SELECT seed, state_json FROM learning_quiz_attempts
            WHERE user_id = ? AND course_key = ? AND item_number = ?
            """,
            (user_id, course_key, item_number),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try:
        state = json.loads(row["state_json"])
        seed = int(row["seed"])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if (
        not isinstance(state, dict)
        or not isinstance(state.get("base"), dict)
        or not isinstance(state.get("extra"), dict)
        or not isinstance(state.get("extra_count"), int)
        or not 0 <= state["extra_count"] <= 40
        or not 0 <= seed < 2**31
    ):
        return None
    return {"seed": seed, "state": state}


def _save_live_quiz_attempt(
    user_id: int, course_key: str, item_number: int, seed: int, state: dict
) -> None:
    conn = _live_quiz_connection()
    try:
        conn.execute(
            """
            INSERT INTO learning_quiz_attempts (
                user_id, course_key, item_number, seed, state_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, course_key, item_number) DO UPDATE SET
                seed = excluded.seed,
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, course_key, item_number, seed, json.dumps(state, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_live_quiz_attempt(user_id: int, course_key: str, item_number: int) -> None:
    conn = _live_quiz_connection()
    try:
        conn.execute(
            """
            DELETE FROM learning_quiz_attempts
            WHERE user_id = ? AND course_key = ? AND item_number = ?
            """,
            (user_id, course_key, item_number),
        )
        conn.commit()
    finally:
        conn.close()


def _live_quiz_seed(course_key: str, item_number: int) -> int:
    if getattr(current_user, "is_authenticated", False):
        user_id = int(current_user.id)
        if request.args.get("restart") == "1":
            _delete_live_quiz_attempt(user_id, course_key, item_number)
        attempt = _load_live_quiz_attempt(user_id, course_key, item_number)
        if attempt:
            return int(attempt["seed"])
        seed = secrets.randbelow(2**31)
        _save_live_quiz_attempt(
            user_id, course_key, item_number, seed, {"base": {}, "extra": {}, "extra_count": 0}
        )
        return seed
    key = _live_quiz_seed_key(course_key, item_number)
    seed = session.get(key)
    if not isinstance(seed, int) or not 0 <= seed < 2**31:
        seed = secrets.randbelow(2**31)
        session[key] = seed
    return seed


def _base_quiz_for_attempt(course_key: str, item_number: int, seed: int) -> list[dict]:
    if course_key == "english" and 1 <= item_number <= len(ENGLISH_LESSONS):
        return shuffle_quiz(build_daily_quiz(item_number), seed)
    if course_key == "it" and 1 <= item_number <= len(IT_LESSONS):
        return shuffle_quiz(build_it_daily_quiz(item_number), seed)
    if course_key == "python" and 1 <= item_number <= len(PYTHON_LESSONS):
        return shuffle_quiz(build_python_daily_quiz(item_number), seed)
    if course_key == "video" and 1 <= item_number <= len(PYTHON_VIDEO_LESSONS):
        return build_video_lesson_quiz(item_number, seed)
    abort(404)


def _public_question(question: dict, live_index: int) -> dict:
    return {
        "live_index": live_index,
        "answer_type": question.get("answer_type", "single"),
        "prompt": question["prompt"],
        "options": list(question.get("options", ())),
        "answer_hint": question.get("answer_hint", ""),
        "prompt_speech": _english_speech(question["prompt"]),
        "option_speech": [_english_speech(option) for option in question.get("options", ())],
    }


def _save_live_quiz_result(course_key: str, item_number: int, score: int, total: int, passed: bool) -> None:
    stored_score = _stored_score(score, total)
    user_id = int(current_user.id)
    if course_key == "english":
        _save_day_result(user_id, item_number, stored_score, passed)
    elif course_key == "it":
        _save_it_day_result(user_id, item_number, stored_score, passed)
    elif course_key == "python":
        _save_course_day_result(user_id, item_number, stored_score, passed, "python")
    else:
        _save_course_day_result(user_id, item_number, stored_score, passed, "video")


def _live_quiz_continue_action(course_key: str, item_number: int, passed: bool) -> tuple[str, str]:
    if not passed:
        if course_key == "english":
            retry_url = url_for("learning.english_day_test", day_number=item_number, restart=1)
        elif course_key == "it":
            retry_url = url_for("learning.it_day_test", day_number=item_number, restart=1)
        elif course_key == "python":
            retry_url = url_for("learning.python_day_test", day_number=item_number, restart=1)
        else:
            retry_url = url_for("learning.it_video_lesson", lesson_number=item_number, restart=1)
        return retry_url, "Пройти тест заново"

    user_id = int(current_user.id)
    if course_key == "english":
        _progress, _passed, next_item = _course_state(user_id)
        if next_item:
            return url_for("learning.english_day", day_number=next_item), f"Перейти к дню {next_item}"
        return url_for("learning.english_final"), "Перейти к итоговому тесту"
    if course_key == "it":
        _progress, _passed, next_item = _it_course_state(user_id)
        if next_item:
            return url_for("learning.it_day", day_number=next_item), f"Перейти к дню {next_item}"
        return url_for("learning.it_final"), "Перейти к итоговому тесту"
    if course_key == "python":
        _progress, _passed, next_item = _python_course_state(user_id)
        if next_item:
            return url_for("learning.python_day", day_number=next_item), f"Перейти к дню {next_item}"
        return url_for("learning.python_final"), "Перейти к итоговому тесту"
    _progress, _passed, next_item = _get_course_state(user_id, "video", PYTHON_VIDEO_LESSONS)
    if next_item:
        return url_for("learning.it_video_lesson", lesson_number=next_item), f"Перейти к видео {next_item}"
    return url_for("learning.it_video_course"), "Вернуться к видеокурсам"


def _finalize_live_quiz_state(
    user_id: int, course_key: str, item_number: int, seed: int, state: dict, base_total: int
) -> dict:
    score = sum(bool(value.get("correct")) for value in state["base"].values()) + sum(
        bool(value.get("correct")) for value in state["extra"].values()
    )
    total = base_total + int(state["extra_count"])
    extra_score = sum(bool(value.get("correct")) for value in state["extra"].values())
    passed = _extra_stage_passed(extra_score, int(state["extra_count"]))
    pass_score = score if passed else score + 1
    _save_live_quiz_result(course_key, item_number, score, total, passed)
    continue_url, continue_label = _live_quiz_continue_action(course_key, item_number, passed)
    state.update({
        "complete": True,
        "passed": passed,
        "score": score,
        "total": total,
        "pass_score": pass_score,
    })
    _save_live_quiz_attempt(user_id, course_key, item_number, seed, state)
    return {
        "score": score,
        "total": total,
        "pass_score": pass_score,
        "passed": passed,
        "continue_url": continue_url,
        "continue_label": continue_label,
    }


def _ensure_live_quiz_access(course_key: str, item_number: int) -> None:
    user_id = int(current_user.id)
    if course_key == "english":
        _progress, passed_items, next_item = _course_state(user_id)
    elif course_key == "it":
        _progress, passed_items, next_item = _it_course_state(user_id)
    elif course_key == "python":
        _progress, passed_items, next_item = _python_course_state(user_id)
    else:
        _progress, passed_items, next_item = _get_course_state(user_id, "video", PYTHON_VIDEO_LESSONS)
    if item_number not in passed_items and item_number != next_item:
        abort(403)


def _live_answer_feedback(question: dict, answer) -> dict:
    submitted = {"question_0": answer if question.get("answer_type") == "multiple" else str(answer)}
    score, feedback = grade_quiz([question], submitted)
    item = feedback[0]
    return {
        "correct": bool(score),
        "selected_answer": item["selected_answer"],
        "correct_answer": item["correct_answer"],
        "explanation": item["explanation"],
        "answer": answer,
    }


@learning_bp.route("/study/quiz/state", methods=["GET"])
@login_required
def live_quiz_state():
    try:
        course_key = str(request.args["course"])
        item_number = int(request.args["item_number"])
        seed = int(request.args["seed"])
    except (KeyError, TypeError, ValueError):
        abort(400)
    if course_key not in {"english", "it", "python", "video"} or not 0 <= seed < 2**31:
        abort(400)
    _ensure_live_quiz_access(course_key, item_number)
    user_id = int(current_user.id)
    attempt = _load_live_quiz_attempt(user_id, course_key, item_number)
    state = attempt["state"] if attempt and int(attempt["seed"]) == seed else None
    if not isinstance(state, dict):
        state = session.get(_live_quiz_key(course_key, item_number, seed))
    if not isinstance(state, dict):
        return jsonify({"base_answers": {}, "extra_answers": {}, "extra_questions": []})

    base_questions = _base_quiz_for_attempt(course_key, item_number, seed)
    extra_count = int(state.get("extra_count", 0))
    extras = build_extra_quiz(course_key, item_number, 40, seed ^ 0x5F3759DF) if extra_count else []

    answers_complete = (
        len(state["base"]) == len(base_questions)
        and len(state["extra"]) == extra_count
    )
    recovered_completion = None
    if answers_complete and not state.get("complete"):
        recovered_completion = _finalize_live_quiz_state(
            user_id, course_key, item_number, seed, state, len(base_questions)
        )

    def restored_answers(stage_name: str, questions: list[dict]) -> dict:
        restored = {}
        for raw_index, saved in state.get(stage_name, {}).items():
            if not isinstance(saved, dict) or "answer" not in saved:
                continue
            index = int(raw_index)
            if 0 <= index < len(questions):
                restored[raw_index] = _live_answer_feedback(questions[index], saved["answer"])
        return restored

    response = {
        "base_answers": restored_answers("base", base_questions),
        "extra_answers": restored_answers("extra", extras[:extra_count]),
        "extra_questions": [_public_question(extras[index], index) for index in range(extra_count)],
        "complete": bool(state.get("complete")),
    }
    if response["complete"]:
        if recovered_completion:
            response.update(recovered_completion)
        else:
            passed = bool(state.get("passed"))
            continue_url, continue_label = _live_quiz_continue_action(course_key, item_number, passed)
            response.update({
                "passed": passed,
                "score": int(state.get("score", 0)),
                "total": int(state.get("total", len(base_questions) + extra_count)),
                "pass_score": int(state.get("pass_score", 0)),
                "continue_url": continue_url,
                "continue_label": continue_label,
            })
    return jsonify(response)


@learning_bp.route("/study/quiz/check", methods=["POST"])
@login_required
def check_live_quiz_answer():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400)
    try:
        course_key = str(payload["course"])
        item_number = int(payload["item_number"])
        seed = int(payload["seed"])
        question_index = int(payload["question_index"])
        stage = str(payload.get("stage", "base"))
    except (KeyError, TypeError, ValueError):
        abort(400)
    if course_key not in {"english", "it", "python", "video"} or stage not in {"base", "extra"} or not 0 <= seed < 2**31:
        abort(400)

    base_questions = _base_quiz_for_attempt(course_key, item_number, seed)
    _ensure_live_quiz_access(course_key, item_number)
    key = _live_quiz_key(course_key, item_number, seed)
    user_id = int(current_user.id)
    attempt = _load_live_quiz_attempt(user_id, course_key, item_number)
    state = attempt["state"] if attempt and int(attempt["seed"]) == seed else None
    if not isinstance(state, dict):
        state = session.get(key)
    if not isinstance(state, dict):
        state = {"base": {}, "extra": {}, "extra_count": 0}
    answered = state[stage]
    index_key = str(question_index)
    if index_key in answered:
        return jsonify({"error": "На этот вопрос уже дан ответ."}), 409

    if stage == "base":
        if not 0 <= question_index < len(base_questions):
            abort(400)
        question = base_questions[question_index]
    else:
        if not 0 <= question_index < int(state["extra_count"]):
            abort(400)
        extra_seed = seed ^ 0x5F3759DF
        question = build_extra_quiz(course_key, item_number, 40, extra_seed)[question_index]

    answer = payload.get("answer", "")
    if isinstance(answer, str):
        answer = answer[:300]
    elif isinstance(answer, list):
        answer = [str(value)[:8] for value in answer[:4]]
    else:
        answer = ""
    if question.get("answer_type") == "multiple":
        submitted_form = {"question_0": answer if isinstance(answer, list) else []}
    else:
        submitted_form = {"question_0": str(answer)}
    answer_score, feedback = grade_quiz([question], submitted_form)
    is_correct = bool(answer_score)
    answered[index_key] = {"correct": is_correct, "answer": answer}

    added_questions = []
    if stage == "base" and not is_correct:
        previous_count = int(state["extra_count"])
        state["extra_count"] = previous_count + 2
        extra_seed = seed ^ 0x5F3759DF
        extras = build_extra_quiz(course_key, item_number, 40, extra_seed)
        added_questions = [
            _public_question(extras[index], index)
            for index in range(previous_count, int(state["extra_count"]))
        ]

    base_complete = len(state["base"]) == len(base_questions)
    extra_complete = len(state["extra"]) == int(state["extra_count"])
    complete = base_complete and extra_complete
    response = {
        "correct": is_correct,
        "selected_answer": feedback[0]["selected_answer"],
        "correct_answer": feedback[0]["correct_answer"],
        "explanation": feedback[0]["explanation"],
        "added_questions": added_questions,
        "complete": complete,
    }
    if complete:
        session.pop(key, None)
        session.pop(_live_quiz_seed_key(course_key, item_number), None)
        response.update(
            _finalize_live_quiz_state(
                user_id, course_key, item_number, seed, state, len(base_questions)
            )
        )
    else:
        _save_live_quiz_attempt(user_id, course_key, item_number, seed, state)
    return jsonify(response)


@learning_bp.route("/study/quiz/sync", methods=["POST"])
@login_required
def sync_live_quiz_answers():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), list):
        abort(400)
    try:
        course_key = str(payload["course"])
        item_number = int(payload["item_number"])
        seed = int(payload["seed"])
    except (KeyError, TypeError, ValueError):
        abort(400)
    if course_key not in {"english", "it", "python", "video"} or not 0 <= seed < 2**31:
        abort(400)
    _ensure_live_quiz_access(course_key, item_number)
    base_questions = _base_quiz_for_attempt(course_key, item_number, seed)
    submitted = {"base": {}, "extra": {}}
    for item in payload["answers"][:60]:
        if not isinstance(item, dict) or item.get("stage") not in submitted:
            abort(400)
        try:
            index = int(item["index"])
        except (KeyError, TypeError, ValueError):
            abort(400)
        answer = item.get("answer", "")
        if isinstance(answer, str):
            answer = answer[:300]
        elif isinstance(answer, list):
            answer = [str(value)[:8] for value in answer[:4]]
        else:
            abort(400)
        submitted[item["stage"]][index] = answer
    if set(submitted["base"]) != set(range(len(base_questions))):
        return jsonify({"complete": False, "error": "Не все основные ответы получены."})

    state = {"base": {}, "extra": {}, "extra_count": 0}
    for index, question in enumerate(base_questions):
        result = _live_answer_feedback(question, submitted["base"][index])
        state["base"][str(index)] = {
            "correct": bool(result["correct"]), "answer": submitted["base"][index]
        }
    wrong_count = sum(not value["correct"] for value in state["base"].values())
    state["extra_count"] = wrong_count * 2
    if set(submitted["extra"]) != set(range(state["extra_count"])):
        return jsonify({"complete": False, "error": "Не все дополнительные ответы получены."})
    if state["extra_count"]:
        extras = build_extra_quiz(course_key, item_number, 40, seed ^ 0x5F3759DF)
        for index in range(state["extra_count"]):
            result = _live_answer_feedback(extras[index], submitted["extra"][index])
            state["extra"][str(index)] = {
                "correct": bool(result["correct"]), "answer": submitted["extra"][index]
            }

    user_id = int(current_user.id)
    completion = _finalize_live_quiz_state(
        user_id, course_key, item_number, seed, state, len(base_questions)
    )
    return jsonify({"complete": True, **completion})


@learning_bp.route("/study/quiz/reset", methods=["POST"])
@login_required
def reset_live_quiz_attempt():
    try:
        course_key = str(request.form["course"])
        item_number = int(request.form["item_number"])
    except (KeyError, TypeError, ValueError):
        abort(400)
    if course_key not in {"english", "it", "python", "video"}:
        abort(400)
    _ensure_live_quiz_access(course_key, item_number)
    user_id = int(current_user.id)
    _delete_live_quiz_attempt(user_id, course_key, item_number)
    session.pop(_live_quiz_seed_key(course_key, item_number), None)
    if course_key == "english":
        _reset_day_result(user_id, item_number)
        _reset_final_result(user_id)
        destination = url_for("learning.english_day_test", day_number=item_number, restart=1)
    elif course_key == "it":
        _reset_it_day_result(user_id, item_number)
        _reset_it_final_result(user_id)
        destination = url_for("learning.it_day_test", day_number=item_number, restart=1)
    elif course_key == "python":
        _reset_course_day_result(user_id, item_number, "python")
        _reset_course_final_result(user_id, "python")
        destination = url_for("learning.python_day_test", day_number=item_number, restart=1)
    else:
        _reset_course_day_result(user_id, item_number, "video")
        destination = url_for("learning.it_video_lesson", lesson_number=item_number, restart=1)
    return redirect(destination)


def _review_cards(passed_days: set[int]) -> list[dict]:
    return [
        {
            "end_day": end_day,
            "start_day": end_day - REVIEW_BLOCK_SIZE + 1,
            "unlocked": all(day in passed_days for day in range(1, end_day + 1)),
        }
        for end_day in REVIEW_MILESTONES
    ]


def _review_seed() -> int:
    if request.method == "GET":
        return secrets.randbelow(2**31)
    try:
        seed = int(request.form.get("quiz_seed", ""))
    except (TypeError, ValueError):
        abort(400)
    if not 0 <= seed < 2**31:
        abort(400)
    return seed


def grade_quiz(questions: list[dict], form) -> tuple[int, list[dict]]:
    score = 0
    feedback = []
    for index, question in enumerate(questions):
        field_name = f"question_{index}"
        answer_type = question.get("answer_type", "single")
        if answer_type == "text":
            selected_answer = str(form.get(field_name, "")).strip()
            accepted = question["accepted_answers"]
            is_correct = _normalize_text_answer(selected_answer) in {
                _normalize_text_answer(answer) for answer in accepted
            }
            correct_answer = accepted[0]
            selected_answer = selected_answer or "не выбран"
            selected_index = None
        elif answer_type == "multiple":
            raw_answers = form.getlist(field_name) if hasattr(form, "getlist") else form.get(field_name, [])
            if isinstance(raw_answers, str):
                raw_answers = [raw_answers]
            try:
                selected_indices = tuple(sorted({int(value) for value in raw_answers}))
            except (TypeError, ValueError):
                selected_indices = ()
            options = question["options"]
            valid_indices = tuple(index for index in selected_indices if 0 <= index < len(options))
            selected_answer = "; ".join(options[index] for index in valid_indices) or "не выбран"
            correct_indices = tuple(sorted(question["correct_indices"]))
            correct_answer = "; ".join(options[index] for index in correct_indices)
            is_correct = selected_indices == correct_indices
            selected_index = None
        else:
            raw_answer = form.get(field_name, "")
            try:
                selected_index = int(raw_answer)
            except (TypeError, ValueError):
                selected_index = -1
            options = question["options"]
            correct_index = question["correct_index"]
            selected_answer = options[selected_index] if 0 <= selected_index < len(options) else "не выбран"
            correct_answer = options[correct_index]
            is_correct = selected_index == correct_index
        score += int(is_correct)
        feedback.append(
            {
                **question,
                "selected_index": selected_index,
                "selected_answer": selected_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
            }
        )
    return score, feedback


def _normalize_text_answer(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).strip()


def _get_course_state(user_id: int, course_key: str, lessons):
    progress = _get_course_progress(user_id, course_key)
    passed_days = {
        day_number
        for day_number, item in progress.items()
        if bool(item["passed"])
    }
    next_day = next(
        (
            lesson["day"]
            for lesson in lessons
            if lesson["day"] not in passed_days
        ),
        None,
    )
    return progress, passed_days, next_day


def _course_state(user_id: int):
    return _get_course_state(user_id, "english", ENGLISH_LESSONS)


def _it_course_state(user_id: int):
    return _get_course_state(user_id, "it", IT_LESSONS)


def _python_course_state(user_id: int):
    return _get_course_state(user_id, "python", PYTHON_LESSONS)


def _locked_future_lessons(course_key: str) -> list[dict]:
    titles = {
        "english": "Продолжение English",
        "it": "Продолжение IT",
        "python": "Продолжение Python",
    }
    summaries = {
        "english": "Следующий уровень появится после запуска продолжения курса.",
        "it": "Следующий уровень фундамента IT пока готовится.",
        "python": "Следующий уровень Python пока готовится.",
    }
    return [
        {
            "day": day_number,
            "title": titles[course_key],
            "summary": summaries[course_key],
        }
        for day_number in LOCKED_FUTURE_DAYS
    ]


def _build_english_lecture_text(lesson: dict) -> str:
    return (
        f"Сначала знакомьтесь с темой по одному короткому правилу: {lesson['focus']} "
        "После чтения закройте карточку и попробуйте объяснить тему своими словами без подсказки. "
        "Затем возьмите одну фразу дня, поменяйте в ней имя, действие или время и соберите свой вариант предложения. "
        "Так короткая тема быстрее переходит из пассивного чтения в настоящую практику."
    )


def _build_english_lecture_details(lesson: dict) -> list[str]:
    first_word, first_translation = lesson["words"][0]
    first_phrase, first_phrase_translation = lesson["phrases"][0]
    second_phrase, second_phrase_translation = lesson["phrases"][1]
    return [
        (
            f"Что именно изучаем. Тема называется «{lesson['title']}». Её правило простыми словами: {lesson['focus']} "
            f"Не пытайтесь охватить всё сразу: сначала свяжите «{first_word}» только с одним значением — «{first_translation}»."
        ),
        (
            f"Примитивный пример №1. Вы видите или слышите: «{first_phrase}». Это означает: «{first_phrase_translation}». "
            f"Не переводите предложение наугад: сначала узнайте знакомое слово «{first_word}», затем восстановите общий смысл всей фразы."
        ),
        (
            f"Примитивный пример №2. Фраза «{second_phrase}» переводится как «{second_phrase_translation}». "
            "Прочитайте английский вариант один раз, закройте его и попробуйте восстановить по русскому смыслу. Затем сделайте наоборот."
        ),
        (
            f"Проверка понимания. Ответьте без подсказки на три вопроса: как по-английски будет «{first_translation}»; "
            f"что означает «{first_phrase}»; в какой обычной ситуации вам пригодится тема «{lesson['title']}». "
            "Если хотя бы один ответ не получается, откройте только нужную карточку и повторите её, а не весь урок с начала."
        ),
        (
            f"Разберите все слова урока по парам: "
            + "; ".join(f"{english} — {russian}" for english, russian in lesson["words"])
            + ". Сначала читайте слева направо, затем закройте английскую часть и восстановите каждое слово по переводу."
        ),
        (
            f"Практика на обычной ситуации. Представьте момент, связанный с темой «{lesson['title']}», и выберите из урока минимум три слова. "
            "Скажите их вслух, затем используйте одну готовую фразу дня. Не стремитесь говорить быстро: сначала важны правильный смысл и порядок слов."
        ),
    ]


def _english_audio_segments(lesson: dict) -> list[dict]:
    segments = [
        {"lang": "ru-RU", "text": f"День {lesson['day']}. {lesson['title']}."},
        {"lang": "ru-RU", "text": _build_english_lecture_text(lesson)},
        {"lang": "ru-RU", "text": "Словарь дня."},
    ]
    for english, russian in lesson["words"]:
        segments.extend(
            (
                {"lang": "en-US", "text": english},
                {"lang": "ru-RU", "text": russian},
            )
        )
    segments.append({"lang": "ru-RU", "text": "Предложения дня."})
    for english, russian in lesson["phrases"]:
        segments.extend(
            (
                {"lang": "en-US", "text": english},
                {"lang": "ru-RU", "text": russian},
            )
        )
    return segments


def _it_audio_segments(lesson: dict) -> list[dict]:
    segments = [
        {"lang": "ru-RU", "text": f"День {lesson['day']}. {lesson['title']}."},
        {"lang": "ru-RU", "text": lesson["summary"]},
    ]
    for point in _build_it_lecture_points(lesson):
        segments.append({"lang": "ru-RU", "text": point["text"]})
        segments.append({"lang": "ru-RU", "text": point["detail"]})
    segments.append({"lang": "ru-RU", "text": "Словарь вакансий."})
    for term_card in _build_it_term_cards(lesson):
        if term_card["is_english"]:
            segments.append({"lang": "en-US", "text": term_card["term"]})
        segments.append({"lang": "ru-RU", "text": f"{term_card['term']}. {term_card['definition']}"})
        segments.append({"lang": "ru-RU", "text": term_card["detail"]})
    if lesson.get("code"):
        segments.append(
            {
                "lang": "ru-RU",
                "text": f"Разбор кода. {lesson['code_title']}. Код можно прочитать на экране и разобрать построчно.",
            }
        )
    segments.append({"lang": "ru-RU", "text": f"Практика. {lesson['practice']}"})
    return segments


def _has_latin_letters(value: str) -> bool:
    return any(("a" <= char.lower() <= "z") for char in value)


def _build_it_term_cards(lesson: dict) -> list[dict]:
    cards = []
    for index, (term, definition) in enumerate(lesson["terms"]):
        related_term, related_definition = lesson["terms"][(index + 1) % len(lesson["terms"])]
        cards.append(
            {
                "term": term,
                "definition": definition,
                "detail": (
                    f"Совсем простыми словами: «{term}» — это {definition}. "
                    f"В уроке «{lesson['title']}» этим словом называют именно эту часть темы, а не всю тему целиком."
                ),
                "is_english": _has_latin_letters(term),
                "detail_paragraphs": [
                    (
                        f"Примитивный пример. Представьте учебное задание: «{lesson['practice']}» "
                        f"Когда вы выполняете его, ищите в происходящем конкретно «{term}»: то есть {definition}."
                    ),
                    (
                        f"Не путайте с «{related_term}». «{related_term}» означает: {related_definition}. "
                        f"Разница простая: «{term}» отвечает за смысл «{definition}», а «{related_term}» — за другой смысл из определения выше."
                    ),
                    (
                        f"Как сказать своими словами: «В теме “{lesson['title']}” термин {term} нужен, когда мы говорим про {definition}». "
                        "Это уже полноценное объяснение для новичка — без заучивания сложной формулировки."
                    ),
                    (
                        f"Самопроверка: закройте определение и закончите фразу «{term} — это…». Затем приведите один пример из задания этого дня. "
                        "Если пример не связан с определением, перечитайте только первый абзац этой расшифровки."
                    ),
                ],
            }
        )
    return cards


def _build_it_lecture_points(lesson: dict) -> list[dict]:
    points = []
    for index, paragraph in enumerate(lesson["lecture"], start=1):
        key_fragment = paragraph.split(".")[0].strip()
        first_term, first_definition = lesson["terms"][(index - 1) * 2]
        second_term, second_definition = lesson["terms"][(index - 1) * 2 + 1]
        points.append(
            {
                "number": index,
                "text": paragraph,
                "detail": (
                    f"Главная мысль этого пункта: «{key_fragment}». "
                    f"Он относится именно к теме «{lesson['title']}» и объясняет один её конкретный кусочек."
                ),
                "detail_paragraphs": [
                    (
                        f"Разберём слова из этого же урока. «{first_term}» — это {first_definition}. "
                        f"«{second_term}» — это {second_definition}. Эти два понятия помогают прочитать исходный абзац без ощущения, что он написан для специалиста."
                    ),
                    (
                        f"Примитивный пример из практики этого дня: «{lesson['practice']}» "
                        f"Сначала найдите в этом действии «{first_term}», затем отдельно «{second_term}». Так абстрактный пункт превращается в наблюдаемое действие."
                    ),
                    (
                        f"Что важно не перепутать: этот пункт не объясняет всю тему «{lesson['title']}». Он объясняет только мысль «{key_fragment.lower()}». "
                        "Остальные пункты урока дополняют её, поэтому их нужно рассматривать отдельно."
                    ),
                    (
                        f"Самопроверка: объясните вслух, что такое «{first_term}» и «{second_term}», не подсматривая определения. "
                        f"Потом одним предложением свяжите оба слова с мыслью «{key_fragment}»."
                    ),
                    (
                        f"Разложите мысль на простую цепочку: сначала происходит «{key_fragment.lower()}», затем в работе появляются понятия "
                        f"«{first_term}» и «{second_term}», после чего получается результат из темы «{lesson['title']}». "
                        "Если один шаг цепочки непонятен, вернитесь к его определению выше."
                    ),
                    (
                        f"Мини-задание без кода: запишите на бумаге два столбца. В первом — «{first_term}» и его роль, во втором — "
                        f"«{second_term}» и его роль. Под таблицей одним простым предложением перескажите исходный пункт: «{paragraph}»"
                    ),
                ],
            }
        )
    return points


def _explain_it_code_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return "Пустая строка отделяет смысловые части примера, чтобы код было легче читать."
    if stripped.startswith("import "):
        return f"Команда «{stripped}» подключает готовый модуль. После этого код ниже может использовать его возможности, не создавая их заново."
    if stripped.startswith("def "):
        return f"Строка «{stripped}» создаёт функцию. Имя стоит после def, а значения в скобках функция получит при вызове."
    if stripped.startswith("return "):
        return f"«{stripped}» отдаёт вычисленное значение из функции наружу. Без return результат остался бы внутри функции."
    if stripped.startswith("print("):
        return f"«{stripped}» печатает указанное значение в консоль. Так можно сразу увидеть и проверить результат предыдущих строк."
    if stripped.startswith("for "):
        return "Запускаем цикл: повторяем одно действие для нескольких элементов."
    if stripped.startswith("if "):
        return "Проверяем условие: если оно верное, выполняется вложенный блок кода."
    if stripped.startswith("else"):
        return "Описываем запасной вариант, если условие выше не сработало."
    if stripped.startswith("class "):
        return "Описываем класс: шаблон для объектов с данными и действиями."
    if stripped.startswith("with open("):
        return "Открываем файл безопасно: после блока Python сам закроет его."
    if stripped.upper().startswith(("SELECT", "FROM", "WHERE", "ORDER BY", "CREATE TABLE", "INSERT", "UPDATE", "DELETE")):
        return "Это строка SQL-запроса: она говорит базе данных, какие данные создать, найти или изменить."
    if stripped.startswith(("{", "}", "[", "]")) or ":" in stripped and stripped.endswith((",", "{", "}", "true", "false")):
        return "Это часть структурированных данных: ключи и значения описывают объект понятным для программы способом."
    if stripped.split(" ", 1)[0] in {"git", "pwd", "ls", "mkdir", "cd"}:
        return "Это команда терминала: её вводят в консоль, чтобы управлять файлами, папками или историей проекта."
    return f"Эта строка выполняется буквально как «{stripped}». Найдите имя слева: в него обычно записывается результат выражения справа; если знака = нет, строка вызывает указанное действие."


def _build_it_code_steps(lesson: dict) -> list[dict]:
    code = lesson.get("code") or ""
    return [
        {
            "line": line,
            "explanation": _explain_it_code_line(line),
        }
        for line in code.splitlines()
    ]


def _build_it_practice_steps(lesson: dict) -> list[str]:
    return [
        f"Цель именно этого упражнения по теме «{lesson['title']}»: {lesson['practice']}",
        f"Шаг 1. Подготовьте только то, что прямо названо в задании «{lesson['practice']}». Не добавляйте дополнительные функции и оформление.",
        f"Шаг 2. Выполните главное действие и вслух назовите, как оно связано с темой «{lesson['title']}». Если связь объяснить нельзя, вернитесь к лекции.",
        "Шаг 3. Проверьте видимый результат: команда должна показать ожидаемый вывод, файл — появиться, код — запуститься, а схема — содержать все элементы из задания.",
        f"Самопроверка. Закончите фразу: «Я выполнил задание “{lesson['practice']}”, получил конкретный результат и теперь могу объяснить, почему он относится к теме “{lesson['title']}”»."
    ]


def _build_english_word_cards(lesson: dict) -> list[dict]:
    cards = []
    for index, (english, russian) in enumerate(lesson["words"]):
        phrase_english, phrase_russian = lesson["phrases"][index % len(lesson["phrases"])]
        phrase_contains_word = english.lower() in phrase_english.lower()
        context_explanation = (
            f"В предложении «{phrase_english}» это слово уже стоит на своём месте."
            if phrase_contains_word
            else f"Фраза «{phrase_english}» показывает общую ситуацию этой темы; слово «{english}» можно использовать в похожей ситуации отдельно."
        )
        cards.append(
            {
                "english": english,
                "russian": russian,
                "detail": (
                    f"Точное значение: «{english}» означает «{russian}». {context_explanation} "
                    f"Тема урока — «{lesson['title']}», поэтому запоминайте слово именно в этом контексте."
                ),
                "detail_paragraphs": [
                    (
                        f"Примитивный пример. Вы видите карточку «{english}». Не нужно строить сложную фразу: сначала просто скажите «{english} — {russian}». "
                        f"Затем прочитайте «{phrase_english}» — «{phrase_russian}»."
                    ),
                    (
                        f"Частая ошибка — помнить тему «{lesson['title']}», но путать конкретные карточки. Здесь правильная пара только одна: "
                        f"«{english}» = «{russian}». Не подменяйте её переводом соседнего слова."
                    ),
                    (
                        f"Мини-проверка: закройте английскую часть и по слову «{russian}» восстановите «{english}». Потом закройте русский перевод и сделайте наоборот. "
                        "Повторите до тех пор, пока оба направления не получатся без паузы."
                    ),
                ],
            }
        )
    return cards


def _build_english_phrase_cards(lesson: dict) -> list[dict]:
    cards = []
    for english, russian in lesson["phrases"]:
        cards.append(
            {
                "english": english,
                "russian": russian,
                "detail": (
                    f"Полный смысл фразы «{english}» — «{russian}». Это готовое предложение из темы «{lesson['title']}»: "
                    "его можно произнести целиком, не собирая заново из отдельных слов."
                ),
                "detail_paragraphs": [
                    (
                        f"Примитивная ситуация: человек говорит «{english}». Вы должны понять не отдельные слова, а весь ответ целиком: «{russian}». "
                        "Сначала прочитайте английскую фразу медленно, затем сразу произнесите русский смысл."
                    ),
                    (
                        f"Порядок слов уже дан: «{' · '.join(english.rstrip('.!?').split())}». Не переставляйте слова по русскому порядку — "
                        "английская фраза должна остаться в том виде, в котором она показана на карточке."
                    ),
                    (
                        f"Мини-проверка: посмотрите только на перевод «{russian}» и восстановите «{english}». Затем сравните каждое слово и знак в конце. "
                        "Если ошиблись, повторите именно эту фразу три раза, а не весь список."
                    ),
                ],
            }
        )
    return cards


@learning_bp.route("/study")
@login_required
def study_hub():
    return render_template("study_hub.html")


@learning_bp.route("/study/english-it")
@login_required
def english_it_hub():
    user_id = int(current_user.id)
    _python_progress, python_passed, _python_next = _python_course_state(user_id)
    _it_progress, it_passed, _it_next = _it_course_state(user_id)
    _video_progress, video_passed, _video_next = _get_course_state(
        user_id, "video", PYTHON_VIDEO_LESSONS
    )
    _go_progress, go_passed, _go_next = _get_course_state(user_id, "go", GO_LESSONS)
    _html_progress, html_passed, _html_next = _get_course_state(user_id, "html", HTML_THEMES)
    _topic_progress, topic_passed, _topic_next = _get_course_state(user_id, "python_topics", PYTHON_V2_TOPICS)
    conn = get_connection()
    try:
        interview_passed = conn.execute(
            "SELECT COUNT(*) FROM python_interview_progress WHERE user_id = ? AND passed = 1",
            (user_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    blocks = (
        {"title": "Понятия (Для новичка)", "description": "30 дней фундаментальных IT-тем, практики и тестов.", "icon": "</>", "endpoint": "learning.it_course", "passed": len(it_passed), "total": len(IT_LESSONS)},
        {"title": "Python v1", "description": "30 дней от основ языка до Django и запуска проекта в production.", "icon": "Py", "endpoint": "learning.python_course", "passed": len(python_passed), "total": len(PYTHON_LESSONS)},
        {"title": "Разработчик Python v2", "description": "Последовательные видеоуроки Python с тестом после каждого.", "icon": "Py", "endpoint": "learning.it_video_course", "passed": len(video_passed), "total": len(PYTHON_VIDEO_LESSONS)},
        {"title": "Python v2", "description": "63 темы по 9–20 минут: видео, подробная лекция, практика и тест после каждой.", "icon": "Py2", "endpoint": "learning.python_v2_topics", "passed": len(topic_passed), "total": len(PYTHON_V2_TOPICS)},
        {"title": "Собеседования (Python)", "description": "Видеолекции, сильные ответы, практические задачи и тесты по блокам.", "icon": "QA", "endpoint": "learning.python_interview", "passed": int(interview_passed), "total": len(PYTHON_INTERVIEW_SECTIONS)},
        {"title": "HTML", "description": "13 тем: от устройства веба и тегов до адаптивного многостраничного проекта.", "icon": "HTML", "endpoint": "learning.html_course", "passed": len(html_passed), "total": len(HTML_THEMES)},
        {"title": "Язык Go", "description": "Синтаксис, конкурентность, HTTP backend и PostgreSQL.", "icon": "Go", "endpoint": "learning.go_course", "passed": len(go_passed), "total": len(GO_LESSONS)},
    )
    ordered_blocks = []
    access_open = True
    for order, block in enumerate(blocks):
        percent = round(block["passed"] / block["total"] * 100)
        ordered_blocks.append({**block, "percent": percent, "locked": not access_open, "order": order})
        access_open = access_open and percent >= 80
    ordered_blocks.sort(key=lambda block: (block["locked"], block["percent"] >= 80, block["order"]))
    return render_template("english_it_hub.html", blocks=ordered_blocks)


def _it_course_access(user_id: int) -> dict[str, bool]:
    """Последовательно открывает IT-направления после 80% предыдущего."""
    _it_progress, it_passed, _it_next = _it_course_state(user_id)
    _python_progress, python_passed, _python_next = _python_course_state(user_id)
    _video_progress, video_passed, _video_next = _get_course_state(
        user_id, "video", PYTHON_VIDEO_LESSONS
    )
    conn = get_connection()
    try:
        interview_passed = conn.execute(
            "SELECT COUNT(*) FROM python_interview_progress WHERE user_id = ? AND passed = 1",
            (user_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    python_ready = len(python_passed) / len(PYTHON_LESSONS) >= 0.8
    video_ready = len(video_passed) / len(PYTHON_VIDEO_LESSONS) >= 0.8
    _topic_progress, topic_passed, _topic_next = _get_course_state(user_id, "python_topics", PYTHON_V2_TOPICS)
    topics_ready = len(topic_passed) / len(PYTHON_V2_TOPICS) >= 0.8
    interview_ready = interview_passed / len(PYTHON_INTERVIEW_SECTIONS) >= 0.8
    _html_progress, html_passed, _html_next = _get_course_state(user_id, "html", HTML_THEMES)
    html_ready = len(html_passed) / len(HTML_THEMES) >= 0.8
    concepts_ready = len(it_passed) / len(IT_LESSONS) >= 0.8
    return {
        "it": True,
        "python": concepts_ready,
        "video": concepts_ready and python_ready,
        "python_topics": concepts_ready and python_ready and video_ready,
        "interview": concepts_ready and python_ready and video_ready and topics_ready,
        "html": concepts_ready and python_ready and video_ready and topics_ready and interview_ready,
        "go": concepts_ready and python_ready and video_ready and topics_ready and interview_ready and html_ready,
    }


@learning_bp.before_request
def enforce_it_course_sequence():
    if not current_user.is_authenticated or not request.endpoint:
        return None
    endpoint = request.endpoint.removeprefix("learning.")
    course = None
    if endpoint.startswith("python_interview"):
        course = "interview"
    elif endpoint.startswith("python_v2_topic"):
        course = "python_topics"
    elif endpoint.startswith("python_"):
        course = "python"
    elif endpoint.startswith("it_video"):
        course = "video"
    elif endpoint.startswith("go_"):
        course = "go"
    elif endpoint.startswith("html_"):
        course = "html"
    elif endpoint.startswith("it_"):
        course = "it"
    if course and not _it_course_access(int(current_user.id))[course]:
        flash("Этот курс откроется после прохождения предыдущего направления минимум на 80%.", "warning")
        return redirect(url_for("learning.english_it_hub"))
    return None


@learning_bp.route("/study/python-v2")
@login_required
def python_v2_topics():
    progress, passed_topics, next_topic = _get_course_state(
        int(current_user.id), "python_topics", PYTHON_V2_TOPICS
    )
    topics = []
    for topic in PYTHON_V2_TOPICS:
        item = progress.get(topic["number"])
        topics.append({
            **topic,
            "passed": topic["number"] in passed_topics,
            "unlocked": topic["number"] in passed_topics or topic["number"] == next_topic,
            "best_score": int(item["best_score"]) if item else 0,
        })
    return render_template(
        "python_v2_topics.html",
        topics=topics,
        passed_count=len(passed_topics),
        total_topics=len(PYTHON_V2_TOPICS),
        progress_percent=round(len(passed_topics) / len(PYTHON_V2_TOPICS) * 100),
        next_topic=next_topic,
    )


@learning_bp.route("/study/python-v2/topic/<int:topic_number>", methods=["GET", "POST"])
@login_required
def python_v2_topic(topic_number: int):
    if not 1 <= topic_number <= len(PYTHON_V2_TOPICS):
        abort(404)
    progress, passed_topics, next_topic = _get_course_state(
        int(current_user.id), "python_topics", PYTHON_V2_TOPICS
    )
    if topic_number not in passed_topics and topic_number != next_topic:
        flash("Сначала завершите предыдущую тему Python v2.", "warning")
        return redirect(url_for("learning.python_v2_topics"))
    topic = PYTHON_V2_TOPICS[topic_number - 1]
    seed = _review_seed()
    if request.method == "POST":
        try:
            seed = int(request.form.get("quiz_seed", seed))
        except (TypeError, ValueError):
            seed = _review_seed()
    questions = shuffle_quiz(build_python_v2_topic_quiz(topic_number), seed)
    score = feedback = None
    passed = False
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form)
        passed = score >= DAILY_PASS_SCORE
        _save_course_day_result(int(current_user.id), topic_number, score, passed, "python_topics")
        progress, passed_topics, next_topic = _get_course_state(
            int(current_user.id), "python_topics", PYTHON_V2_TOPICS
        )
    return render_template(
        "python_v2_topic.html",
        topic=topic,
        total_topics=len(PYTHON_V2_TOPICS),
        questions=questions,
        quiz_seed=seed,
        score=score,
        feedback=feedback,
        passed=passed,
        pass_score=DAILY_PASS_SCORE,
        next_topic=next_topic if passed else None,
        course_finished=len(passed_topics) == len(PYTHON_V2_TOPICS),
    )


@learning_bp.route("/study/html")
@login_required
def html_course():
    progress, passed_themes, next_theme = _get_course_state(int(current_user.id), "html", HTML_THEMES)
    themes = []
    for theme in HTML_THEMES:
        item = progress.get(theme["number"])
        themes.append({
            **theme,
            "passed": theme["number"] in passed_themes,
            "unlocked": theme["number"] in passed_themes or theme["number"] == next_theme,
            "best_score": int(item["best_score"]) if item else 0,
        })
    return render_template(
        "html_course.html",
        themes=themes,
        passed_count=len(passed_themes),
        total_themes=len(HTML_THEMES),
        progress_percent=round(len(passed_themes) / len(HTML_THEMES) * 100),
        next_theme=next_theme,
    )


@learning_bp.route("/study/html/theme/<int:theme_number>", methods=["GET", "POST"])
@login_required
def html_theme(theme_number: int):
    if not 1 <= theme_number <= len(HTML_THEMES):
        abort(404)
    progress, passed_themes, next_theme = _get_course_state(int(current_user.id), "html", HTML_THEMES)
    if theme_number not in passed_themes and theme_number != next_theme:
        flash("Сначала завершите предыдущую тему HTML.", "warning")
        return redirect(url_for("learning.html_course"))
    theme = HTML_THEMES[theme_number - 1]
    seed = _review_seed()
    if request.method == "POST":
        try:
            seed = int(request.form.get("quiz_seed", seed))
        except (TypeError, ValueError):
            seed = _review_seed()
    questions = shuffle_quiz(build_html_theme_quiz(theme_number), seed)
    score = feedback = None
    passed = False
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form)
        passed = score >= DAILY_PASS_SCORE
        _save_course_day_result(int(current_user.id), theme_number, score, passed, "html")
        progress, passed_themes, next_theme = _get_course_state(int(current_user.id), "html", HTML_THEMES)
    return render_template(
        "html_theme.html",
        theme=theme,
        total_themes=len(HTML_THEMES),
        questions=questions,
        quiz_seed=seed,
        score=score,
        feedback=feedback,
        passed=passed,
        pass_score=DAILY_PASS_SCORE,
        next_theme=next_theme if passed else None,
        course_finished=len(passed_themes) == len(HTML_THEMES),
    )


@learning_bp.route("/study/go")
@login_required
def go_course():
    progress, passed_days, next_day = _get_course_state(int(current_user.id), "go", GO_LESSONS)
    lessons = []
    for lesson in GO_LESSONS:
        item = progress.get(lesson["day"])
        lessons.append({
            **lesson,
            "passed": lesson["day"] in passed_days,
            "unlocked": lesson["day"] in passed_days or lesson["day"] == next_day,
            "best_score": int(item["best_score"]) if item else 0,
        })
    return render_template(
        "go_course.html",
        lessons=lessons,
        passed_count=len(passed_days),
        progress_percent=round(len(passed_days) / len(GO_LESSONS) * 100),
        next_day=next_day,
    )


@learning_bp.route("/study/go/day/<int:day_number>", methods=["GET", "POST"])
@login_required
def go_day(day_number: int):
    if not 1 <= day_number <= len(GO_LESSONS):
        abort(404)
    progress, passed_days, next_day = _get_course_state(int(current_user.id), "go", GO_LESSONS)
    if day_number not in passed_days and day_number != next_day:
        flash("Сначала завершите предыдущий урок Go.", "warning")
        return redirect(url_for("learning.go_course"))
    lesson = GO_LESSONS[day_number - 1]
    seed = _review_seed()
    if request.method == "POST":
        try:
            seed = int(request.form.get("quiz_seed", seed))
        except (TypeError, ValueError):
            seed = _review_seed()
    questions = shuffle_quiz(build_go_daily_quiz(day_number), seed)
    score = feedback = None
    passed = False
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form)
        passed = score >= DAILY_PASS_SCORE
        _save_course_day_result(int(current_user.id), day_number, score, passed, "go")
        progress, passed_days, next_day = _get_course_state(int(current_user.id), "go", GO_LESSONS)
    return render_template(
        "go_day.html",
        lesson=lesson,
        questions=questions,
        quiz_seed=seed,
        score=score,
        feedback=feedback,
        passed=passed,
        pass_score=DAILY_PASS_SCORE,
        next_day=next_day if passed else None,
        course_finished=len(passed_days) == len(GO_LESSONS),
    )
@learning_bp.route("/study/english")
@login_required
def english_course():
    progress, passed_days, next_day = _course_state(int(current_user.id))
    lesson_cards = []
    for lesson in ENGLISH_LESSONS:
        day_progress = progress.get(lesson["day"])
        lesson_cards.append(
            {
                **lesson,
                "passed": lesson["day"] in passed_days,
                "unlocked": lesson["day"] in passed_days or lesson["day"] == next_day,
                "best_score": int(day_progress["best_score"]) if day_progress else 0,
            }
        )
    return render_template(
        "english_course.html",
        lessons=lesson_cards,
        locked_future_lessons=_locked_future_lessons("english"),
        passed_count=len(passed_days),
        progress_percent=round(len(passed_days) / len(ENGLISH_LESSONS) * 100),
        next_day=next_day,
        final_unlocked=len(passed_days) == len(ENGLISH_LESSONS),
        final_result=_get_final_result(int(current_user.id)),
        review_tests=_review_cards(passed_days),
    )


@learning_bp.route("/study/english/day/<int:day_number>", methods=["GET", "POST"])
@login_required
def english_day(day_number: int):
    if day_number < 1 or day_number > len(ENGLISH_LESSONS):
        abort(404)

    progress, passed_days, next_day = _course_state(int(current_user.id))
    if day_number not in passed_days and day_number != next_day:
        flash("Сначала завершите предыдущий день курса.", "warning")
        return redirect(url_for("learning.english_course"))

    lesson = ENGLISH_LESSONS[day_number - 1]
    if request.method == "POST":
        return redirect(url_for("learning.english_day_test", day_number=day_number), code=307)

    return render_template(
        "english_day.html",
        lesson=lesson,
        lesson_video_file=f"videos/english-lectures/lesson-{day_number:02d}.mp4",
        lesson_lecture_text=_build_english_lecture_text(lesson),
        lesson_detail_steps=_build_english_lecture_details(lesson),
        pass_score=DAILY_PASS_SCORE,
        day_progress=progress.get(day_number),
        word_cards=_build_english_word_cards(lesson),
        phrase_cards=_build_english_phrase_cards(lesson),
        audio_segments=_english_audio_segments(lesson),
    )


@learning_bp.route("/study/english/videos")
@login_required
def english_video_lectures():
    progress, passed_days, next_day = _english_course_state(int(current_user.id))
    lessons = [{**lesson, "unlocked": lesson["day"] in passed_days or lesson["day"] == next_day,
                "passed": lesson["day"] in passed_days,
                "video_file": f"videos/english-lectures/lesson-{lesson['day']:02d}.mp4"}
               for lesson in ENGLISH_LESSONS]
    return render_template("course_video_catalog.html", course_key="english", course_title="English",
                           lessons=lessons, passed_count=len(passed_days), next_day=next_day)


@learning_bp.route("/study/english/videos/<int:day_number>")
@login_required
def english_video_lecture(day_number: int):
    if day_number < 1 or day_number > len(ENGLISH_LESSONS): abort(404)
    _progress, passed_days, next_day = _english_course_state(int(current_user.id))
    if day_number not in passed_days and day_number != next_day:
        flash("Сначала завершите предыдущий день курса.", "warning")
        return redirect(url_for("learning.english_video_lectures"))
    lesson = ENGLISH_LESSONS[day_number - 1]
    return render_template("course_video_lecture.html", course_key="english", course_title="English",
                           lesson=lesson, video_file=f"videos/english-lectures/lesson-{day_number:02d}.mp4",
                           total_lessons=len(ENGLISH_LESSONS), test_endpoint="learning.english_day_test")


@learning_bp.route("/study/english/day/<int:day_number>/test", methods=["GET", "POST"])
@login_required
def english_day_test(day_number: int):
    if day_number < 1 or day_number > len(ENGLISH_LESSONS):
        abort(404)

    progress, passed_days, next_day = _course_state(int(current_user.id))
    if day_number not in passed_days and day_number != next_day:
        flash("Сначала завершите предыдущий день курса.", "warning")
        return redirect(url_for("learning.english_course"))

    lesson = ENGLISH_LESSONS[day_number - 1]
    is_extra_post = request.method == "POST" and request.form.get("quiz_stage") == "extra"
    seed = (
        _live_quiz_seed("english", day_number)
        if request.method == "GET"
        else secrets.randbelow(2**31) if is_extra_post else _review_seed()
    )
    questions = shuffle_quiz(build_daily_quiz(day_number), seed)
    score = None
    passed = False
    feedback = None
    extra_questions = None
    wrong_count = 0
    result_total_questions = len(questions)
    pass_score = DAILY_PASS_SCORE
    if request.method == "POST":
        if request.form.get("quiz_stage") == "extra":
            score, result_total_questions, pass_score, feedback, passed = _finish_extra_quiz("english", day_number, request.form)
            _save_day_result(int(current_user.id), day_number, _stored_score(score, result_total_questions), passed)
            progress, passed_days, next_day = _course_state(int(current_user.id))
        else:
            base_score, _ = grade_quiz(questions, request.form)
            if base_score < len(questions):
                extra_questions, wrong_count = _start_extra_quiz("english", day_number, base_score, len(questions))
            else:
                score, passed = base_score, True
                _save_day_result(int(current_user.id), day_number, score, passed)
                progress, passed_days, next_day = _course_state(int(current_user.id))

    return render_template(
        "english_day_test.html",
        lesson=lesson,
        questions=questions,
        quiz_seed=seed,
        feedback=feedback,
        score=score,
        passed=passed,
        pass_score=pass_score,
        extra_questions=extra_questions,
        wrong_count=wrong_count,
        result_total_questions=result_total_questions,
        day_progress=progress.get(day_number),
        next_day=next_day,
        course_finished=len(passed_days) == len(ENGLISH_LESSONS),
    )


@learning_bp.route("/study/english/day/<int:day_number>/reset", methods=["POST"])
@login_required
def english_day_reset(day_number: int):
    if day_number < 1 or day_number > len(ENGLISH_LESSONS):
        abort(404)

    user_id = int(current_user.id)
    _reset_day_result(user_id, day_number)
    _reset_final_result(user_id)
    _delete_live_quiz_attempt(user_id, "english", day_number)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(
            {
                "ok": True,
                "test_url": url_for("learning.english_day_test", day_number=day_number),
            }
        )
    return redirect(url_for("learning.english_day", day_number=day_number))


@learning_bp.route("/study/english/final", methods=["GET", "POST"])
@login_required
def english_final():
    _progress, passed_days, _next_day = _course_state(int(current_user.id))
    if len(passed_days) != len(ENGLISH_LESSONS):
        flash("Итоговый тест откроется после завершения всех 30 дней.", "warning")
        return redirect(url_for("learning.english_course"))

    questions = build_final_quiz()
    score = None
    passed = False
    feedback = None
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form)
        passed = score >= FINAL_PASS_SCORE
        _save_final_result(int(current_user.id), score, passed)

    return render_template(
        "english_final.html",
        questions=questions,
        feedback=feedback,
        score=score,
        passed=passed,
        pass_score=FINAL_PASS_SCORE,
        total_questions=len(questions),
        final_result=_get_final_result(int(current_user.id)),
    )


@learning_bp.route("/study/<course_key>/review/<int:end_day>", methods=["GET", "POST"])
@login_required
def course_review(course_key: str, end_day: int):
    course_settings = {
        "english": {
            "title": "English",
            "course_endpoint": "learning.english_course",
            "state": _course_state,
        },
        "it": {
            "title": "IT",
            "course_endpoint": "learning.it_course",
            "state": _it_course_state,
        },
        "python": {
            "title": "Python",
            "course_endpoint": "learning.python_course",
            "state": _python_course_state,
        },
    }
    settings = course_settings.get(course_key)
    if settings is None or end_day not in REVIEW_MILESTONES:
        abort(404)

    _progress, passed_days, _next_day = settings["state"](int(current_user.id))
    if not all(day in passed_days for day in range(1, end_day + 1)):
        flash("Тест повторения откроется после прохождения этого блока дней.", "warning")
        return redirect(url_for(settings["course_endpoint"]))

    seed = _review_seed()
    questions = build_review_quiz(course_key, end_day, seed)
    score = None
    passed = False
    feedback = None
    pass_score = (len(questions) * REVIEW_PASS_PERCENT + 99) // 100
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form)
        passed = score >= pass_score

    return render_template(
        "course_review.html",
        course_key=course_key,
        course_title=settings["title"],
        course_endpoint=settings["course_endpoint"],
        start_day=end_day - REVIEW_BLOCK_SIZE + 1,
        end_day=end_day,
        questions=questions,
        quiz_seed=seed,
        score=score,
        passed=passed,
        feedback=feedback,
        pass_score=pass_score,
    )


@learning_bp.route("/study/it")
@login_required
def it_course():
    progress, passed_days, next_day = _it_course_state(int(current_user.id))
    lesson_cards = []
    for lesson in IT_LESSONS:
        day_progress = progress.get(lesson["day"])
        lesson_cards.append(
            {
                **lesson,
                "passed": lesson["day"] in passed_days,
                "unlocked": lesson["day"] in passed_days or lesson["day"] == next_day,
                "best_score": int(day_progress["best_score"]) if day_progress else 0,
            }
        )
    return render_template(
        "it_course.html",
        lessons=lesson_cards,
        locked_future_lessons=_locked_future_lessons("it"),
        passed_count=len(passed_days),
        progress_percent=round(len(passed_days) / len(IT_LESSONS) * 100),
        next_day=next_day,
        final_unlocked=len(passed_days) == len(IT_LESSONS),
        final_result=_get_it_final_result(int(current_user.id)),
        review_tests=_review_cards(passed_days),
    )


@learning_bp.route("/study/it/videos")
@login_required
def it_video_course():
    progress, passed_lessons, next_lesson = _get_course_state(
        int(current_user.id), "video", PYTHON_VIDEO_LESSONS
    )
    lessons = []
    for lesson in PYTHON_VIDEO_LESSONS:
        lesson_progress = progress.get(lesson["day"])
        lessons.append(
            {
                **lesson,
                "passed": lesson["day"] in passed_lessons,
                "unlocked": lesson["day"] in passed_lessons or lesson["day"] == next_lesson,
                "best_score": int(lesson_progress["best_score"]) if lesson_progress else 0,
            }
        )
    return render_template(
        "it_video_course.html",
        lessons=lessons,
        passed_count=len(passed_lessons),
        progress_percent=round(len(passed_lessons) / len(PYTHON_VIDEO_LESSONS) * 100),
        next_lesson=next_lesson,
    )


@learning_bp.route("/study/it/lectures")
@login_required
def it_video_lectures():
    progress, passed_days, next_day = _it_course_state(int(current_user.id))
    lessons = [{**lesson, "unlocked": lesson["day"] in passed_days or lesson["day"] == next_day,
                "passed": lesson["day"] in passed_days,
                "video_file": f"videos/it-lectures/lesson-{lesson['day']:02d}.mp4"}
               for lesson in IT_LESSONS]
    return render_template("course_video_catalog.html", course_key="it", course_title="IT",
                           lessons=lessons, passed_count=len(passed_days), next_day=next_day)


@learning_bp.route("/study/it/lectures/<int:day_number>")
@login_required
def it_video_lecture(day_number: int):
    if day_number < 1 or day_number > len(IT_LESSONS): abort(404)
    _progress, passed_days, next_day = _it_course_state(int(current_user.id))
    if day_number not in passed_days and day_number != next_day:
        flash("Сначала завершите предыдущий день курса.", "warning")
        return redirect(url_for("learning.it_video_lectures"))
    lesson = IT_LESSONS[day_number - 1]
    return render_template("course_video_lecture.html", course_key="it", course_title="IT",
                           lesson=lesson, video_file=f"videos/it-lectures/lesson-{day_number:02d}.mp4",
                           total_lessons=len(IT_LESSONS), test_endpoint="learning.it_day_test")


@learning_bp.route("/study/it/videos/<int:lesson_number>", methods=["GET", "POST"])
@login_required
def it_video_lesson(lesson_number: int):
    if lesson_number < 1 or lesson_number > len(PYTHON_VIDEO_LESSONS):
        abort(404)
    progress, passed_lessons, next_lesson = _get_course_state(
        int(current_user.id), "video", PYTHON_VIDEO_LESSONS
    )
    if lesson_number not in passed_lessons and lesson_number != next_lesson:
        flash("Сначала пройдите тест предыдущего видеоурока.", "warning")
        return redirect(url_for("learning.it_video_course"))

    lesson = PYTHON_VIDEO_LESSONS[lesson_number - 1]
    is_extra_post = request.method == "POST" and request.form.get("quiz_stage") == "extra"
    seed = (
        _live_quiz_seed("video", lesson_number)
        if request.method == "GET"
        else secrets.randbelow(2**31) if is_extra_post else _review_seed()
    )
    questions = build_video_lesson_quiz(lesson_number, seed)
    score = None
    passed = False
    feedback = None
    pass_score = VIDEO_PASS_SCORE
    extra_questions = None
    wrong_count = 0
    result_total_questions = len(questions)
    if request.method == "POST":
        if is_extra_post:
            score, result_total_questions, pass_score, feedback, passed = _finish_extra_quiz("video", lesson_number, request.form)
            _save_course_day_result(int(current_user.id), lesson_number, _stored_score(score, result_total_questions), passed, "video")
            progress, passed_lessons, next_lesson = _get_course_state(int(current_user.id), "video", PYTHON_VIDEO_LESSONS)
        else:
            base_score, _ = grade_quiz(questions, request.form)
            if base_score < len(questions):
                extra_questions, wrong_count = _start_extra_quiz("video", lesson_number, base_score, len(questions))
            else:
                score, passed = base_score, True
                _save_course_day_result(int(current_user.id), lesson_number, score, passed, "video")
                progress, passed_lessons, next_lesson = _get_course_state(int(current_user.id), "video", PYTHON_VIDEO_LESSONS)

    return render_template(
        "it_video_lesson.html",
        lesson=lesson,
        questions=questions,
        quiz_seed=seed,
        score=score,
        passed=passed,
        feedback=feedback,
        pass_score=pass_score,
        extra_questions=extra_questions,
        wrong_count=wrong_count,
        result_total_questions=result_total_questions,
        lesson_progress=progress.get(lesson_number),
        next_lesson=next_lesson,
        course_finished=len(passed_lessons) == len(PYTHON_VIDEO_LESSONS),
    )


@learning_bp.route("/study/it/day/<int:day_number>", methods=["GET", "POST"])
@login_required
def it_day(day_number: int):
    if day_number < 1 or day_number > len(IT_LESSONS):
        abort(404)

    progress, passed_days, next_day = _it_course_state(int(current_user.id))
    if day_number not in passed_days and day_number != next_day:
        flash("Сначала завершите предыдущий день курса.", "warning")
        return redirect(url_for("learning.it_course"))

    lesson = IT_LESSONS[day_number - 1]
    if request.method == "POST":
        return redirect(url_for("learning.it_day_test", day_number=day_number), code=307)

    return render_template(
        "it_day.html",
        lesson=lesson,
        lesson_video_file=f"videos/it-lectures/lesson-{day_number:02d}.mp4",
        pass_score=DAILY_PASS_SCORE,
        day_progress=progress.get(day_number),
        lecture_points=_build_it_lecture_points(lesson),
        term_cards=_build_it_term_cards(lesson),
        code_steps=_build_it_code_steps(lesson),
        practice_steps=_build_it_practice_steps(lesson),
        audio_segments=_it_audio_segments(lesson),
    )


@learning_bp.route("/study/it/day/<int:day_number>/test", methods=["GET", "POST"])
@login_required
def it_day_test(day_number: int):
    if day_number < 1 or day_number > len(IT_LESSONS):
        abort(404)

    progress, passed_days, next_day = _it_course_state(int(current_user.id))
    if day_number not in passed_days and day_number != next_day:
        flash("Сначала завершите предыдущий день курса.", "warning")
        return redirect(url_for("learning.it_course"))

    lesson = IT_LESSONS[day_number - 1]
    is_extra_post = request.method == "POST" and request.form.get("quiz_stage") == "extra"
    seed = (
        _live_quiz_seed("it", day_number)
        if request.method == "GET"
        else secrets.randbelow(2**31) if is_extra_post else _review_seed()
    )
    questions = shuffle_quiz(build_it_daily_quiz(day_number), seed)
    score = None
    passed = False
    feedback = None
    extra_questions = None
    wrong_count = 0
    result_total_questions = len(questions)
    pass_score = DAILY_PASS_SCORE
    if request.method == "POST":
        if request.form.get("quiz_stage") == "extra":
            score, result_total_questions, pass_score, feedback, passed = _finish_extra_quiz("it", day_number, request.form)
            _save_it_day_result(int(current_user.id), day_number, _stored_score(score, result_total_questions), passed)
            progress, passed_days, next_day = _it_course_state(int(current_user.id))
        else:
            base_score, _ = grade_quiz(questions, request.form)
            if base_score < len(questions):
                extra_questions, wrong_count = _start_extra_quiz("it", day_number, base_score, len(questions))
            else:
                score, passed = base_score, True
                _save_it_day_result(int(current_user.id), day_number, score, passed)
                progress, passed_days, next_day = _it_course_state(int(current_user.id))

    return render_template(
        "it_day_test.html",
        lesson=lesson,
        questions=questions,
        quiz_seed=seed,
        feedback=feedback,
        score=score,
        passed=passed,
        pass_score=pass_score,
        extra_questions=extra_questions,
        wrong_count=wrong_count,
        result_total_questions=result_total_questions,
        day_progress=progress.get(day_number),
        next_day=next_day,
        course_finished=len(passed_days) == len(IT_LESSONS),
    )


@learning_bp.route("/study/it/day/<int:day_number>/reset", methods=["POST"])
@login_required
def it_day_reset(day_number: int):
    if day_number < 1 or day_number > len(IT_LESSONS):
        abort(404)

    user_id = int(current_user.id)
    _reset_it_day_result(user_id, day_number)
    _reset_it_final_result(user_id)
    _delete_live_quiz_attempt(user_id, "it", day_number)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(
            {
                "ok": True,
                "test_url": url_for("learning.it_day_test", day_number=day_number),
            }
        )
    return redirect(url_for("learning.it_day", day_number=day_number))


@learning_bp.route("/study/it/final", methods=["GET", "POST"])
@login_required
def it_final():
    _progress, passed_days, _next_day = _it_course_state(int(current_user.id))
    if len(passed_days) != len(IT_LESSONS):
        flash("Итоговый тест откроется после завершения всех 30 дней.", "warning")
        return redirect(url_for("learning.it_course"))

    questions = build_it_final_quiz()
    score = None
    passed = False
    feedback = None
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form)
        passed = score >= FINAL_PASS_SCORE
        _save_it_final_result(int(current_user.id), score, passed)

    return render_template(
        "it_final.html",
        questions=questions,
        feedback=feedback,
        score=score,
        passed=passed,
        pass_score=FINAL_PASS_SCORE,
        total_questions=len(questions),
        final_result=_get_it_final_result(int(current_user.id)),
    )


@learning_bp.route("/study/python")
@login_required
def python_course():
    progress, passed_days, next_day = _python_course_state(int(current_user.id))
    lessons = []
    for lesson in PYTHON_LESSONS:
        item = progress.get(lesson["day"])
        lessons.append({**lesson, "passed": lesson["day"] in passed_days,
                        "unlocked": lesson["day"] in passed_days or lesson["day"] == next_day,
                        "best_score": int(item["best_score"]) if item else 0})
    return render_template("python_course.html", lessons=lessons,
                           passed_count=len(passed_days),
                           progress_percent=round(len(passed_days) / len(PYTHON_LESSONS) * 100),
                           next_day=next_day, final_unlocked=len(passed_days) == len(PYTHON_LESSONS),
                           final_result=_get_course_final_result(int(current_user.id), "python"),
                           review_tests=_review_cards(passed_days))


@learning_bp.route("/study/python/day/<int:day_number>")
@login_required
def python_day(day_number: int):
    if not 1 <= day_number <= len(PYTHON_LESSONS): abort(404)
    progress, passed_days, next_day = _python_course_state(int(current_user.id))
    if day_number not in passed_days and day_number != next_day:
        flash("Сначала завершите предыдущий день курса.", "warning")
        return redirect(url_for("learning.python_course"))
    lesson = PYTHON_LESSONS[day_number - 1]
    return render_template("python_day.html", lesson=lesson,
                           lesson_video_file=f"videos/python-lectures/lesson-{day_number:02d}.mp4",
                           day_progress=progress.get(day_number),
                           lecture_points=_build_it_lecture_points(lesson),
                           term_cards=_build_it_term_cards(lesson),
                           code_steps=_build_it_code_steps(lesson),
                           practice_steps=_build_it_practice_steps(lesson),
                           audio_segments=_it_audio_segments(lesson))


@learning_bp.route("/study/python/day/<int:day_number>/test", methods=["GET", "POST"])
@login_required
def python_day_test(day_number: int):
    if not 1 <= day_number <= len(PYTHON_LESSONS): abort(404)
    progress, passed_days, next_day = _python_course_state(int(current_user.id))
    if day_number not in passed_days and day_number != next_day:
        return redirect(url_for("learning.python_course"))
    lesson = PYTHON_LESSONS[day_number - 1]
    is_extra = request.method == "POST" and request.form.get("quiz_stage") == "extra"
    seed = _live_quiz_seed("python", day_number) if request.method == "GET" else (secrets.randbelow(2**31) if is_extra else _review_seed())
    questions = shuffle_quiz(build_python_daily_quiz(day_number), seed)
    score = feedback = extra_questions = None; passed = False; wrong_count = 0
    result_total_questions = len(questions); pass_score = DAILY_PASS_SCORE
    if request.method == "POST":
        if is_extra:
            score, result_total_questions, pass_score, feedback, passed = _finish_extra_quiz("python", day_number, request.form)
            _save_course_day_result(int(current_user.id), day_number, _stored_score(score, result_total_questions), passed, "python")
            progress, passed_days, next_day = _python_course_state(int(current_user.id))
        else:
            base_score, _ = grade_quiz(questions, request.form)
            if base_score < len(questions):
                extra_questions, wrong_count = _start_extra_quiz("python", day_number, base_score, len(questions))
            else:
                score = base_score; passed = True
                _save_course_day_result(int(current_user.id), day_number, score, True, "python")
                progress, passed_days, next_day = _python_course_state(int(current_user.id))
    return render_template("python_day_test.html", lesson=lesson, questions=questions, quiz_seed=seed,
                           feedback=feedback, score=score, passed=passed, pass_score=pass_score,
                           extra_questions=extra_questions, wrong_count=wrong_count,
                           result_total_questions=result_total_questions, next_day=next_day,
                           course_finished=len(passed_days) == len(PYTHON_LESSONS))


@learning_bp.route("/study/python/day/<int:day_number>/reset", methods=["POST"])
@login_required
def python_day_reset(day_number: int):
    if not 1 <= day_number <= len(PYTHON_LESSONS): abort(404)
    user_id = int(current_user.id)
    _reset_course_day_result(user_id, day_number, "python")
    _reset_course_final_result(user_id, "python")
    _delete_live_quiz_attempt(user_id, "python", day_number)
    return redirect(url_for("learning.python_day", day_number=day_number))


@learning_bp.route("/study/python/final", methods=["GET", "POST"])
@login_required
def python_final():
    _progress, passed_days, _next = _python_course_state(int(current_user.id))
    if len(passed_days) != len(PYTHON_LESSONS): return redirect(url_for("learning.python_course"))
    questions = build_python_final_quiz(); score = feedback = None; passed = False
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form); passed = score >= FINAL_PASS_SCORE
        _save_course_final_result(int(current_user.id), score, passed, "python")
    return render_template("python_final.html", questions=questions, score=score, feedback=feedback,
                           passed=passed, pass_score=FINAL_PASS_SCORE, total_questions=len(questions),
                           final_result=_get_course_final_result(int(current_user.id), "python"))


@learning_bp.route("/study/python/videos")
@login_required
def python_video_lectures():
    _progress, passed_days, next_day = _python_course_state(int(current_user.id))
    lessons = [{**lesson, "unlocked": lesson["day"] in passed_days or lesson["day"] == next_day,
                "passed": lesson["day"] in passed_days} for lesson in PYTHON_LESSONS]
    return render_template("python_video_catalog.html", lessons=lessons,
                           passed_count=len(passed_days), next_day=next_day)


@learning_bp.route("/study/python/videos/<int:day_number>")
@login_required
def python_video_lecture(day_number: int):
    if not 1 <= day_number <= len(PYTHON_LESSONS): abort(404)
    _progress, passed_days, next_day = _python_course_state(int(current_user.id))
    if day_number not in passed_days and day_number != next_day:
        return redirect(url_for("learning.python_video_lectures"))
    return render_template("python_video_lecture.html", lesson=PYTHON_LESSONS[day_number - 1],
                           video_file=f"videos/python-lectures/lesson-{day_number:02d}.mp4")


@learning_bp.route("/study/python/interview")
@login_required
def python_interview():
    user_id = int(current_user.id)
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT section_number, best_score, attempts, passed
            FROM python_interview_progress
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    progress = {int(row["section_number"]): dict(row) for row in rows}
    passed_sections = {number for number, row in progress.items() if row["passed"]}
    next_section = next(
        (number for number in range(1, len(PYTHON_INTERVIEW_SECTIONS) + 1) if number not in passed_sections),
        None,
    )
    sections = [
        {
            "number": number,
            "title": title,
            "question_count": len(questions),
            "passed": number in passed_sections,
            "unlocked": number in passed_sections or number == next_section,
            "best_score": int(progress.get(number, {}).get("best_score", 0)),
        }
        for number, (title, questions) in enumerate(PYTHON_INTERVIEW_SECTIONS, start=1)
    ]
    return render_template(
        "python_interview.html",
        sections=sections,
        passed_count=len(passed_sections),
        total_sections=len(PYTHON_INTERVIEW_SECTIONS),
    )


def build_python_interview_quiz(section_number: int, seed: int) -> list[dict]:
    if not 1 <= section_number <= len(PYTHON_INTERVIEW_SECTIONS):
        raise ValueError("Неизвестный блок собеседования.")
    _title, section_questions = PYTHON_INTERVIEW_SECTIONS[section_number - 1]
    all_answers = [
        answer
        for _section_title, questions in PYTHON_INTERVIEW_SECTIONS
        for _question, answer in questions
    ]
    rng = random.Random(seed)
    quiz = []
    for question_number, (prompt, answer) in enumerate(section_questions):
        distractors = [candidate for candidate in all_answers if candidate != answer]
        options = [answer, *rng.sample(distractors, 3)]
        rng.shuffle(options)
        quiz.append(
            {
                "prompt": prompt,
                "options": options,
                "correct_index": options.index(answer),
                "explanation": answer,
                "question_id": f"interview-{section_number}-{question_number}",
            }
        )
    rng.shuffle(quiz)
    return quiz


@learning_bp.route("/study/python/interview/<int:section_number>/test", methods=["GET", "POST"], endpoint="python_interview_test")
@learning_bp.route("/study/python/interview/<int:section_number>", methods=["GET", "POST"])
@login_required
def python_interview_section(section_number: int):
    if not 1 <= section_number <= len(PYTHON_INTERVIEW_SECTIONS):
        abort(404)
    user_id = int(current_user.id)
    conn = get_connection()
    try:
        passed_rows = conn.execute(
            """
            SELECT section_number FROM python_interview_progress
            WHERE user_id = ? AND passed = 1
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    passed_sections = {int(row["section_number"]) for row in passed_rows}
    if section_number > 1 and section_number - 1 not in passed_sections:
        flash("Сначала завершите предыдущий блок собеседования.", "warning")
        return redirect(url_for("learning.python_interview"))

    title, interview_questions = PYTHON_INTERVIEW_SECTIONS[section_number - 1]
    seed = int(request.form.get("quiz_seed", 0) or 0) if request.method == "POST" else secrets.randbelow(2**31)
    quiz = build_python_interview_quiz(section_number, seed)
    score = feedback = None
    passed = section_number in passed_sections
    pass_score = (len(quiz) * 80 + 99) // 100
    if request.method == "POST":
        score, feedback = grade_quiz(quiz, request.form)
        passed = score >= pass_score
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO python_interview_progress (
                    user_id, section_number, best_score, attempts, passed, completed_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, CASE WHEN ? THEN CURRENT_TIMESTAMP END, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, section_number) DO UPDATE SET
                    best_score = MAX(best_score, excluded.best_score),
                    attempts = attempts + 1,
                    passed = MAX(passed, excluded.passed),
                    completed_at = CASE
                        WHEN excluded.passed = 1 THEN COALESCE(completed_at, CURRENT_TIMESTAMP)
                        ELSE completed_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, section_number, score, int(passed), int(passed)),
            )
            conn.commit()
        finally:
            conn.close()
    return render_template(
        "python_interview_section.html",
        section_number=section_number,
        total_sections=len(PYTHON_INTERVIEW_SECTIONS),
        title=title,
        interview_questions=interview_questions,
        quiz=quiz,
        quiz_seed=seed,
        pass_score=pass_score,
        score=score,
        feedback=feedback,
        passed=passed,
        next_section=section_number + 1 if section_number < len(PYTHON_INTERVIEW_SECTIONS) else None,
        video_file=f"videos/python-interview/block-{section_number:02d}.mp4",
        test_page=request.endpoint == "learning.python_interview_test",
    )
