from __future__ import annotations

import random
import secrets

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.database import get_connection
from app.it_course_content import IT_LESSONS
from app.python_video_course_content import PYTHON_VIDEO_LESSONS


learning_bp = Blueprint("learning", __name__)
DAILY_PASS_SCORE = 4
FINAL_PASS_SCORE = 24
REVIEW_BLOCK_SIZE = 5
REVIEW_QUESTIONS_PER_DAY = 2
REVIEW_PASS_PERCENT = 80
REVIEW_MILESTONES = tuple(range(REVIEW_BLOCK_SIZE, 31, REVIEW_BLOCK_SIZE))
LOCKED_FUTURE_DAYS = tuple(range(31, 61))
_PROGRESS_TABLES = {
    "english": "english_course_progress",
    "it": "it_course_progress",
    "video": "python_video_progress",
}
_FINAL_TABLES = {
    "english": "english_final_results",
    "it": "it_final_results",
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


def build_daily_quiz(day_number: int) -> list[dict]:
    lesson = ENGLISH_LESSONS[day_number - 1]
    words = lesson["words"]
    questions = []
    for question_index, word_index in enumerate((0, 2, 4)):
        english, russian = words[word_index]
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

    reverse_english, reverse_russian = words[1]
    reverse_options, reverse_correct_index = _rotated_options(
        reverse_english,
        (item[0] for item in words if item[0] != reverse_english),
        day_number + 3,
    )
    questions.append(
        {
            "prompt": f"Выберите английский перевод: «{reverse_russian}».",
            "options": reverse_options,
            "correct_index": reverse_correct_index,
            "explanation": f"{reverse_russian} — {reverse_english}.",
        }
    )

    phrase_english, phrase_russian = lesson["phrases"][day_number % 2]
    phrase_distractors = (
        other_lesson["phrases"][0][1]
        for other_lesson in ENGLISH_LESSONS
        if other_lesson["day"] != day_number
    )
    phrase_options, phrase_correct_index = _rotated_options(
        phrase_russian,
        phrase_distractors,
        day_number + 4,
    )
    questions.append(
        {
            "prompt": f"Как переводится предложение «{phrase_english}»?",
            "options": phrase_options,
            "correct_index": phrase_correct_index,
            "explanation": f"{phrase_english} — {phrase_russian}",
        }
    )
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
    for question_index, term_index in enumerate((0, 1, 2, 3)):
        term, definition = terms[term_index]
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

    questions.append(dict(lesson["checkpoint"]))
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


def build_review_quiz(course_key: str, end_day: int, seed: int) -> list[dict]:
    """Build a repeatable shuffled quiz for the five-day block ending at end_day."""
    if course_key not in {"english", "it"} or end_day not in REVIEW_MILESTONES:
        raise ValueError("Некорректный блок повторения.")

    quiz_builder = build_daily_quiz if course_key == "english" else build_it_daily_quiz
    rng = random.Random(seed)
    questions = []
    first_day = end_day - REVIEW_BLOCK_SIZE + 1
    for day_number in range(first_day, end_day + 1):
        daily_questions = quiz_builder(day_number)
        for question in rng.sample(daily_questions, REVIEW_QUESTIONS_PER_DAY):
            shuffled_question = dict(question)
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
    for index, (term, definition) in enumerate(lesson["facts"]):
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
    rng.shuffle(questions)
    return questions


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
        raw_answer = form.get(f"question_{index}", "")
        try:
            selected_index = int(raw_answer)
        except (TypeError, ValueError):
            selected_index = -1
        options = question["options"]
        correct_index = question["correct_index"]
        selected_answer = (
            options[selected_index]
            if 0 <= selected_index < len(options)
            else "не выбран"
        )
        correct_answer = options[correct_index]
        is_correct = selected_index == question["correct_index"]
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


def _locked_future_lessons(course_key: str) -> list[dict]:
    titles = {
        "english": "Продолжение English",
        "it": "Продолжение IT",
    }
    summaries = {
        "english": "Следующий уровень появится после запуска продолжения курса.",
        "it": "Следующий уровень фундамента IT пока готовится.",
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
        lesson_lecture_text=_build_english_lecture_text(lesson),
        lesson_detail_steps=_build_english_lecture_details(lesson),
        pass_score=DAILY_PASS_SCORE,
        day_progress=progress.get(day_number),
        word_cards=_build_english_word_cards(lesson),
        phrase_cards=_build_english_phrase_cards(lesson),
        audio_segments=_english_audio_segments(lesson),
    )


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
    questions = build_daily_quiz(day_number)
    score = None
    passed = False
    feedback = None
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form)
        passed = score >= DAILY_PASS_SCORE
        _save_day_result(int(current_user.id), day_number, score, passed)
        progress, passed_days, next_day = _course_state(int(current_user.id))

    return render_template(
        "english_day_test.html",
        lesson=lesson,
        questions=questions,
        feedback=feedback,
        score=score,
        passed=passed,
        pass_score=DAILY_PASS_SCORE,
        day_progress=progress.get(day_number),
        next_day=next_day,
        course_finished=len(passed_days) == len(ENGLISH_LESSONS),
    )


@learning_bp.route("/study/english/day/<int:day_number>/reset", methods=["POST"])
@login_required
def english_day_reset(day_number: int):
    if day_number < 1 or day_number > len(ENGLISH_LESSONS):
        abort(404)

    _reset_day_result(int(current_user.id), day_number)
    _reset_final_result(int(current_user.id))
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
    seed = _review_seed()
    questions = build_video_lesson_quiz(lesson_number, seed)
    score = None
    passed = False
    feedback = None
    pass_score = 3
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form)
        passed = score >= pass_score
        _save_course_day_result(
            int(current_user.id), lesson_number, score, passed, "video"
        )
        progress, passed_lessons, next_lesson = _get_course_state(
            int(current_user.id), "video", PYTHON_VIDEO_LESSONS
        )

    return render_template(
        "it_video_lesson.html",
        lesson=lesson,
        questions=questions,
        quiz_seed=seed,
        score=score,
        passed=passed,
        feedback=feedback,
        pass_score=pass_score,
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
    questions = build_it_daily_quiz(day_number)
    score = None
    passed = False
    feedback = None
    if request.method == "POST":
        score, feedback = grade_quiz(questions, request.form)
        passed = score >= DAILY_PASS_SCORE
        _save_it_day_result(int(current_user.id), day_number, score, passed)
        progress, passed_days, next_day = _it_course_state(int(current_user.id))

    return render_template(
        "it_day_test.html",
        lesson=lesson,
        questions=questions,
        feedback=feedback,
        score=score,
        passed=passed,
        pass_score=DAILY_PASS_SCORE,
        day_progress=progress.get(day_number),
        next_day=next_day,
        course_finished=len(passed_days) == len(IT_LESSONS),
    )


@learning_bp.route("/study/it/day/<int:day_number>/reset", methods=["POST"])
@login_required
def it_day_reset(day_number: int):
    if day_number < 1 or day_number > len(IT_LESSONS):
        abort(404)

    _reset_it_day_result(int(current_user.id), day_number)
    _reset_it_final_result(int(current_user.id))
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
