import tempfile
import unittest
from pathlib import Path

from config import Config
from app.learning import (
    DAILY_PASS_SCORE,
    ENGLISH_LESSONS,
    FINAL_PASS_SCORE,
    _build_english_lecture_details,
    _build_english_lecture_text,
    _build_english_phrase_cards,
    _build_english_word_cards,
    _build_it_code_steps,
    _build_it_lecture_points,
    _build_it_practice_steps,
    _build_it_term_cards,
    _course_state,
    _english_audio_segments,
    _get_final_result,
    _get_it_final_result,
    _it_course_state,
    _it_audio_segments,
    _save_day_result,
    _save_final_result,
    _reset_day_result,
    _reset_final_result,
    _reset_it_day_result,
    _reset_it_final_result,
    _save_it_day_result,
    _save_it_final_result,
    build_daily_quiz,
    build_final_quiz,
    build_it_daily_quiz,
    build_it_final_quiz,
    grade_quiz,
    init_learning_db,
)
from app.it_course_content import IT_LESSONS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = PROJECT_ROOT / "app" / "templates"
LEARNING_STYLES = PROJECT_ROOT / "app" / "static" / "css" / "learning.css"
MOBILE_STYLES = PROJECT_ROOT / "app" / "static" / "css" / "mobile.css"
COURSE_AUDIO_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "course-audio.js"
COURSE_DAY_ACTIONS_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "course-day-actions.js"


class EnglishCourseTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temp_directory = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_directory.name) / "learning.db")
        init_learning_db()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_directory.cleanup()

    def test_course_has_thirty_complete_daily_lessons(self):
        self.assertEqual(len(ENGLISH_LESSONS), 30)
        self.assertEqual(
            [lesson["day"] for lesson in ENGLISH_LESSONS],
            list(range(1, 31)),
        )
        for lesson in ENGLISH_LESSONS:
            self.assertTrue(lesson["title"])
            self.assertTrue(lesson["focus"])
            self.assertEqual(len(lesson["words"]), 6)
            self.assertEqual(len(lesson["phrases"]), 2)

    def test_every_daily_quiz_has_five_valid_questions(self):
        for day_number in range(1, 31):
            questions = build_daily_quiz(day_number)
            self.assertEqual(len(questions), 5)
            for question in questions:
                self.assertEqual(len(question["options"]), 4)
                self.assertEqual(len(set(question["options"])), 4)
                self.assertIn(
                    question["correct_index"],
                    range(len(question["options"])),
                )

    def test_quiz_grading_accepts_correct_answers_and_handles_missing_answers(self):
        questions = build_daily_quiz(1)
        correct_form = {
            f"question_{index}": str(question["correct_index"])
            for index, question in enumerate(questions)
        }

        score, feedback = grade_quiz(questions, correct_form)
        missing_score, missing_feedback = grade_quiz(questions, {})

        self.assertEqual(score, len(questions))
        self.assertTrue(all(item["is_correct"] for item in feedback))
        self.assertEqual(missing_score, 0)
        self.assertFalse(any(item["is_correct"] for item in missing_feedback))
        self.assertEqual(DAILY_PASS_SCORE, 4)

    def test_progress_unlocks_only_the_next_day_and_preserves_best_score(self):
        progress, passed_days, next_day = _course_state(7)
        self.assertEqual(progress, {})
        self.assertEqual(passed_days, set())
        self.assertEqual(next_day, 1)

        _save_day_result(7, 1, 2, False)
        progress, passed_days, next_day = _course_state(7)
        self.assertEqual(progress[1]["attempts"], 1)
        self.assertEqual(next_day, 1)

        _save_day_result(7, 1, 5, True)
        _save_day_result(7, 1, 3, False)
        progress, passed_days, next_day = _course_state(7)

        self.assertEqual(passed_days, {1})
        self.assertEqual(next_day, 2)
        self.assertEqual(progress[1]["best_score"], 5)
        self.assertEqual(progress[1]["attempts"], 3)

    def test_day_reset_clears_progress_and_final_result_for_english(self):
        _save_day_result(11, 1, 5, True)
        _save_day_result(11, 2, 4, True)
        _save_final_result(11, 27, True)

        _reset_day_result(11, 2)
        _reset_final_result(11)

        progress, passed_days, next_day = _course_state(11)
        self.assertEqual(set(progress), {1})
        self.assertEqual(passed_days, {1})
        self.assertEqual(next_day, 2)
        self.assertIsNone(_get_final_result(11))

    def test_final_quiz_covers_all_days_and_saves_best_result(self):
        questions = build_final_quiz()
        self.assertEqual(len(questions), 30)
        self.assertEqual(FINAL_PASS_SCORE, 24)

        _save_final_result(9, 20, False)
        _save_final_result(9, 27, True)
        _save_final_result(9, 22, False)
        result = _get_final_result(9)

        self.assertEqual(result["best_score"], 27)
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["passed"], 1)

    def test_development_hub_exposes_only_courses_and_sport_is_separate(self):
        study_source = (TEMPLATES / "study_hub.html").read_text(encoding="utf-8")
        sport_source = (TEMPLATES / "sport_hub.html").read_text(encoding="utf-8")
        base_source = (TEMPLATES / "base.html").read_text(encoding="utf-8")

        self.assertIn("<h1>Развитие</h1>", study_source)
        self.assertIn(">IT<", study_source)
        self.assertIn("Фундамент IT на Python", study_source)
        self.assertIn("url_for('learning.english_course')", study_source)
        self.assertIn("url_for('learning.it_course')", study_source)
        self.assertNotIn("url_for('workouts.index')", study_source)
        self.assertNotIn("url_for('nutrition.index')", study_source)
        self.assertNotIn("section-hero", sport_source)
        self.assertIn("url_for('workouts.index')", sport_source)
        self.assertIn("url_for('nutrition.index')", sport_source)
        self.assertIn('<div class="dashboard-card-title">Тренировки</div>', sport_source)
        self.assertIn('<div class="dashboard-card-title">Питание</div>', sport_source)
        self.assertIn("url_for('shootings_hub')", base_source)
        self.assertIn(">Съёмки</a>", base_source)
        self.assertNotIn("url_for('budget')", base_source)
        self.assertNotIn(">Бюджет</a>", base_source)
        self.assertIn(">Развитие</a>", base_source)
        self.assertIn(">Спорт</a>", base_source)

    def test_learning_hub_is_neutral_on_desktop_and_keeps_purple_touch_palette(self):
        styles = LEARNING_STYLES.read_text(encoding="utf-8")
        desktop_hub_theme = styles.split(
            "/* Desktop development hub stays neutral;",
            1,
        )[1]

        self.assertIn(
            "@media (hover: hover) and (pointer: fine)",
            desktop_hub_theme,
        )
        self.assertIn(".learning-page .learning-hero-compact", desktop_hub_theme)
        self.assertIn("background: #ffffff;", desktop_hub_theme)
        self.assertIn("border-color: #e5eaf2;", desktop_hub_theme)
        self.assertIn(
            ".learning-page .study-direction-grid .dashboard-card",
            desktop_hub_theme,
        )
        self.assertNotIn("#9333ea", desktop_hub_theme)
        self.assertIn(
            "linear-gradient(135deg, #4338ca 0%, #6d28d9 52%, #9333ea 100%)",
            styles,
        )

    def test_it_and_english_desktop_theme_replaces_purple_accents_with_blue(self):
        styles = LEARNING_STYLES.read_text(encoding="utf-8")
        desktop_course_theme = styles.split(
            "/* Desktop follows the shared blue site theme;",
            1,
        )[1].split(
            "/* Desktop development hub stays neutral;",
            1,
        )[0]

        self.assertIn(
            "@media (hover: hover) and (pointer: fine)",
            desktop_course_theme,
        )
        for selector in (
            ".learning-page .lesson-more-details summary",
            ".learning-page .lesson-more-details summary::after",
            ".learning-page .course-pronounce-button",
            ".learning-page .course-audio-button",
            ".learning-page .phrase-card",
        ):
            self.assertIn(selector, desktop_course_theme)
        self.assertIn("#2563eb", desktop_course_theme)
        self.assertIn("#3b82f6", desktop_course_theme)
        self.assertIn("#bfdbfe", desktop_course_theme)
        self.assertNotIn("#6d28d9", desktop_course_theme)
        self.assertNotIn("#7c3aed", desktop_course_theme)
        self.assertNotIn("#9333ea", desktop_course_theme)
        self.assertNotIn("#5b21b6", desktop_course_theme)

    def test_it_course_has_thirty_complete_daily_lessons(self):
        self.assertEqual(len(IT_LESSONS), 30)
        self.assertEqual(
            [lesson["day"] for lesson in IT_LESSONS],
            list(range(1, 31)),
        )
        for lesson in IT_LESSONS:
            self.assertTrue(lesson["title"])
            self.assertTrue(lesson["summary"])
            self.assertEqual(len(lesson["lecture"]), 3)
            self.assertEqual(len(lesson["terms"]), 6)
            self.assertTrue(lesson["practice"])
            self.assertEqual(len(lesson["checkpoint"]["options"]), 4)

    def test_every_it_daily_quiz_and_final_quiz_are_valid(self):
        for day_number in range(1, 31):
            questions = build_it_daily_quiz(day_number)
            self.assertEqual(len(questions), 5)
            for question in questions:
                self.assertEqual(len(question["options"]), 4)
                self.assertEqual(len(set(question["options"])), 4)
                self.assertIn(
                    question["correct_index"],
                    range(len(question["options"])),
                )

        final_questions = build_it_final_quiz()
        self.assertEqual(len(final_questions), 30)
        self.assertEqual(
            {question["day"] for question in final_questions},
            set(range(1, 31)),
        )

    def test_it_progress_is_sequential_and_independent_from_english(self):
        progress, passed_days, next_day = _it_course_state(17)
        self.assertEqual(progress, {})
        self.assertEqual(passed_days, set())
        self.assertEqual(next_day, 1)

        _save_it_day_result(17, 1, 2, False)
        _save_it_day_result(17, 1, 5, True)
        _save_it_day_result(17, 1, 3, False)
        progress, passed_days, next_day = _it_course_state(17)

        self.assertEqual(progress[1]["best_score"], 5)
        self.assertEqual(progress[1]["attempts"], 3)
        self.assertEqual(passed_days, {1})
        self.assertEqual(next_day, 2)
        self.assertEqual(_course_state(17), ({}, set(), 1))

    def test_day_reset_clears_progress_and_final_result_for_it(self):
        _save_it_day_result(23, 1, 5, True)
        _save_it_day_result(23, 2, 4, True)
        _save_it_final_result(23, 28, True)

        _reset_it_day_result(23, 2)
        _reset_it_final_result(23)

        progress, passed_days, next_day = _it_course_state(23)
        self.assertEqual(set(progress), {1})
        self.assertEqual(passed_days, {1})
        self.assertEqual(next_day, 2)
        self.assertIsNone(_get_it_final_result(23))

    def test_it_final_result_preserves_best_score_and_passed_state(self):
        _save_it_final_result(19, 20, False)
        _save_it_final_result(19, 28, True)
        _save_it_final_result(19, 21, False)
        result = _get_it_final_result(19)

        self.assertEqual(result["best_score"], 28)
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["passed"], 1)

    def test_it_templates_explain_direction_and_daily_timing(self):
        course_source = (TEMPLATES / "it_course.html").read_text(encoding="utf-8")
        day_source = (TEMPLATES / "it_day.html").read_text(encoding="utf-8")
        final_source = (TEMPLATES / "it_final.html").read_text(encoding="utf-8")

        self.assertIn("Фундамент IT на Python", course_source)
        self.assertIn("30 дней", course_source)
        self.assertIn("15 минут", day_source)
        self.assertIn("Словарь вакансий", day_source)
        self.assertIn("Практика на 5 минут", day_source)
        self.assertIn("30 вопросов", final_source)

    def test_courses_show_locked_future_days_after_day_thirty(self):
        english_source = (TEMPLATES / "english_course.html").read_text(encoding="utf-8")
        it_source = (TEMPLATES / "it_course.html").read_text(encoding="utf-8")

        for source in (english_source, it_source):
            self.assertIn("locked_future_lessons", source)
            self.assertIn("Продолжение после 30-го дня", source)
            self.assertIn("Пока не открыто", source)
            self.assertNotIn("url_for('learning.english_day', day_number=lesson.day)", source.split("learning-future-grid", 1)[1])

    def test_daily_lessons_expose_speech_synthesis_controls(self):
        english_source = (TEMPLATES / "english_day.html").read_text(encoding="utf-8")
        it_source = (TEMPLATES / "it_day.html").read_text(encoding="utf-8")
        english_test_source = (TEMPLATES / "english_day_test.html").read_text(encoding="utf-8")
        it_test_source = (TEMPLATES / "it_day_test.html").read_text(encoding="utf-8")
        script_source = COURSE_AUDIO_SCRIPT.read_text(encoding="utf-8")
        day_actions_source = COURSE_DAY_ACTIONS_SCRIPT.read_text(encoding="utf-8")
        learning_styles = LEARNING_STYLES.read_text(encoding="utf-8")

        for source in (english_source, it_source):
            self.assertIn("data-course-audio", source)
            self.assertIn("course-audio-segments", source)
            self.assertIn("course-audio.js", source)
            self.assertIn("Озвучить урок", source)
            self.assertEqual(source.count("data-course-audio-play"), 1)
            self.assertIn("course-audio-inline", source)
            self.assertIn("course-audio-button", source)
            self.assertIn("course-audio-label", source)
            self.assertIn("course-audio-icon", source)
            self.assertIn("lesson-next-button", source)
            self.assertIn("course-day-actions.js", source)
            self.assertIn("data-course-day-reset-form", source)
            self.assertIn("data-test-url", source)
            self.assertIn("Отменить результат", source)
            self.assertNotIn("data-course-audio-toggle", source)
            self.assertNotIn("data-course-audio-stop", source)
            self.assertNotIn("Включить озвучку", source)
            self.assertNotIn("Стоп", source)
            self.assertIn("Пройти тест", source)
            self.assertIn('target="_blank"', source)
            self.assertIn('rel="noopener"', source)
            self.assertNotIn("data-quiz-reveal-button", source)
            self.assertNotIn("data-quiz-form-shell", source)
            self.assertNotIn("lesson-quiz.js", source)
            self.assertNotIn("Проверка знаний", source)
            self.assertNotIn("course-audio-controller", source)
            self.assertIn("data-course-pronounce", source)
            self.assertIn("data-pronounce-text", source)
            self.assertIn("data-pronounce-lang=\"en-US\"", source)
            self.assertIn("course-pronounce-button", source)
            self.assertIn("Прослушать произношение", source)
        self.assertIn("english_day_reset", english_source)
        self.assertIn("it_day_reset", it_source)
        self.assertIn("day_progress and day_progress.passed", english_source)
        self.assertIn("lesson-reset-form", english_source)
        self.assertIn("day_progress and day_progress.passed", it_source)
        self.assertIn("lesson-reset-form", it_source)
        self.assertGreater(english_source.index("lesson-reset-form"), english_source.index("phrase-list"))
        self.assertGreater(it_source.index("lesson-reset-form"), it_source.index("it-practice-card"))
        self.assertIn("window.fetch(form.action", day_actions_source)
        self.assertIn('"X-Requested-With": "XMLHttpRequest"', day_actions_source)
        self.assertIn("form.replaceWith(createTestLink", day_actions_source)
        self.assertIn('window.open("", "_blank")', day_actions_source)
        self.assertIn("openTestWithoutDarkFlash", day_actions_source)
        self.assertIn('<meta name=\\"color-scheme\\" content=\\"light\\">', day_actions_source)
        self.assertIn("background:#f5f7fb", day_actions_source)
        self.assertIn("testWindow.location.replace(url)", day_actions_source)
        self.assertIn("testWindow.requestAnimationFrame(navigateToTest)", day_actions_source)
        self.assertIn("testWindow.setTimeout(navigateToTest, 0)", day_actions_source)
        self.assertIn("event.preventDefault();", day_actions_source)
        self.assertIn('link.target = "_blank"', day_actions_source)
        self.assertIn('link.textContent = "Пройти тест"', day_actions_source)
        self.assertIn("<summary>Подробнее</summary>", english_source)
        self.assertIn("lesson_detail_steps", english_source)
        self.assertIn("card.detail_paragraphs", english_source)
        self.assertIn("card.detail_steps", english_source)
        self.assertIn("lesson_lecture_text", english_source)
        self.assertIn("<summary>Подробнее</summary>", it_source)
        self.assertIn("lecture_points", it_source)
        self.assertIn("term_cards", it_source)
        self.assertIn("point.detail_paragraphs", it_source)
        self.assertIn("point.detail_steps", it_source)
        self.assertIn("term.detail_paragraphs", it_source)
        self.assertIn("term.detail_steps", it_source)
        self.assertIn("code_steps", it_source)
        self.assertIn("practice_steps", it_source)
        self.assertNotIn("quiz_revealed", english_source)
        self.assertNotIn("quiz_revealed", it_source)
        self.assertNotIn('id="daily-test-result"', english_source)
        self.assertNotIn('id="daily-test-result"', it_source)
        self.assertIn("url_for('learning.english_day_test'", english_source)
        self.assertIn("url_for('learning.it_day_test'", it_source)
        for source in (english_test_source, it_test_source):
            self.assertIn("Тест дня", source)
            self.assertIn("quiz-form", source)
            self.assertIn('id="daily-test-result"', source)
            self.assertIn("_anchor='daily-test-result'", source)
            self.assertIn("Проверить ответы", source)
            self.assertIn("Вернуться к уроку", source)
        self.assertIn("url_for('learning.english_day_test'", english_test_source)
        self.assertIn("url_for('learning.it_day_test'", it_test_source)
        self.assertIn("SpeechSynthesisUtterance", script_source)
        self.assertIn("data-course-pronounce", script_source)
        self.assertIn("playPronunciation", script_source)
        self.assertIn("data-pronounce-text", english_source)
        self.assertIn("term.is_english", it_source)
        self.assertIn("phrase-title-row", english_source)
        self.assertIn("phrase-title-row", learning_styles)
        self.assertEqual(english_source.count("data-course-pronounce"), 2)
        self.assertEqual(english_source.count("data-pronounce-lang=\"en-US\""), 2)
        self.assertIn('data-pronounce-text="{{ card.english }}"', english_source)
        self.assertNotIn("speakSingle", script_source)
        self.assertIn("ru-RU", script_source)
        self.assertIn('startsWith("en")', script_source)
        self.assertIn("course-audio-playing", script_source)
        self.assertNotIn("course-audio-toggle", script_source)
        self.assertNotIn("course-audio-stop", script_source)
        self.assertNotIn("STORAGE_KEY", script_source)
        self.assertIn("VOICE_PREFERENCES", script_source)
        self.assertIn("voiceScore", script_source)
        self.assertIn("getProsody", script_source)
        self.assertIn("getSegmentPause", script_source)
        self.assertIn("window.setTimeout(function ()", script_source)
        self.assertIn("microsoft aria online", script_source)
        self.assertIn("microsoft svetlana online", script_source)
        self.assertIn("course-audio-button", learning_styles)
        self.assertIn("course-pronounce-button", learning_styles)
        self.assertIn("learning-card-title-row", learning_styles)
        self.assertIn(".learning-section-heading h1", learning_styles)
        self.assertIn("course-audio-label", learning_styles)
        self.assertIn("course-audio-inline", learning_styles)
        self.assertIn("lesson-more-details", learning_styles)
        self.assertNotIn("max-width: 850px", learning_styles)
        self.assertNotIn("max-width: 930px", learning_styles)
        self.assertNotIn("max-width: 960px", learning_styles)
        self.assertNotIn("course-audio-copy", learning_styles)
        self.assertNotIn("course-audio-actions", learning_styles)

    def test_lesson_cards_render_beginner_friendly_more_details_controls(self):
        english_source = (TEMPLATES / "english_day.html").read_text(encoding="utf-8")
        it_source = (TEMPLATES / "it_day.html").read_text(encoding="utf-8")
        learning_styles = LEARNING_STYLES.read_text(encoding="utf-8")
        mobile_styles = MOBILE_STYLES.read_text(encoding="utf-8")

        for source in (english_source, it_source):
            self.assertIn("<details", source)
            self.assertIn("<summary>Подробнее</summary>", source)
            self.assertIn("lesson-more-body", source)
            self.assertIn("lesson-next-button", source)

        self.assertIn("english-card-detail", english_source)
        self.assertIn("it-point-detail", it_source)
        self.assertIn("it-term-detail", it_source)
        self.assertIn("english-more-details", english_source)
        self.assertIn("it-more-details", it_source)
        self.assertIn("lesson-more-details summary::after", learning_styles)
        self.assertIn("lesson-more-body ol", learning_styles)
        self.assertIn("course-pronounce-button", mobile_styles)
        self.assertNotIn("it-more-details", mobile_styles)

    def test_lecture_texts_are_expanded_for_english_and_it(self):
        english_lesson = ENGLISH_LESSONS[0]
        expanded_english = _build_english_lecture_text(english_lesson)
        self.assertGreater(len(expanded_english), len(english_lesson["focus"]))
        self.assertIn("Сначала знакомьтесь", expanded_english)
        self.assertIn("практику", expanded_english)

        it_points = _build_it_lecture_points(IT_LESSONS[0])
        self.assertEqual(len(it_points), 3)
        self.assertGreater(len(it_points[0]["text"]), len(IT_LESSONS[0]["lecture"][0]))
        self.assertIn("реальный сайт", it_points[0]["text"])
        self.assertIn("рабочую ситуацию", it_points[0]["text"])

    def test_more_details_content_is_expanded_for_beginners(self):
        english_lesson = ENGLISH_LESSONS[0]
        english_details = _build_english_lecture_details(english_lesson)
        word_cards = _build_english_word_cards(english_lesson)
        phrase_cards = _build_english_phrase_cards(english_lesson)

        self.assertGreaterEqual(len(english_details), 3)
        self.assertTrue(any("Например" in step for step in english_details))
        self.assertNotIn("Что изучаем:", english_details[0])
        self.assertEqual(len(word_cards[0]["detail_paragraphs"]), 2)
        self.assertEqual(len(phrase_cards[0]["detail_paragraphs"]), 2)
        self.assertNotIn("Значение:", word_cards[0]["detail"])
        self.assertTrue(any("Например" in step for step in word_cards[0]["detail_paragraphs"]))

        it_lesson = IT_LESSONS[0]
        it_points = _build_it_lecture_points(it_lesson)
        term_cards = _build_it_term_cards(it_lesson)
        code_steps = _build_it_code_steps(IT_LESSONS[6])
        practice_steps = _build_it_practice_steps(it_lesson)

        self.assertEqual(len(it_points[0]["detail_paragraphs"]), 2)
        self.assertEqual(len(term_cards[0]["detail_paragraphs"]), 2)
        self.assertNotIn(term_cards[0]["definition"], term_cards[0]["detail"])
        self.assertTrue(any("Например" in step for step in term_cards[0]["detail_paragraphs"]))
        self.assertTrue(any(step["explanation"] for step in code_steps))
        self.assertGreaterEqual(len(practice_steps), 4)

    def test_every_daily_lesson_has_audio_segments(self):
        for lesson in ENGLISH_LESSONS:
            segments = _english_audio_segments(lesson)
            self.assertGreaterEqual(len(segments), 1 + 1 + len(lesson["words"]) * 2 + len(lesson["phrases"]) * 2)
            self.assertTrue(any(segment["lang"] == "ru-RU" for segment in segments))
            self.assertTrue(any(segment["lang"] == "en-US" for segment in segments))
            for english, _russian in lesson["words"]:
                self.assertTrue(
                    any(segment["lang"] == "en-US" and segment["text"] == english for segment in segments),
                    english,
                )

        for lesson in IT_LESSONS:
            segments = _it_audio_segments(lesson)
            lecture_points = _build_it_lecture_points(lesson)
            term_cards = _build_it_term_cards(lesson)
            self.assertGreaterEqual(
                len(segments),
                3 + len(lecture_points) * 2 + len(term_cards) * 2 + 1,
            )
            self.assertTrue(any(segment["lang"] == "en-US" for segment in segments))
            for point in lecture_points:
                self.assertTrue(any(segment["text"] == point["text"] for segment in segments))
                self.assertTrue(any(segment["text"] == point["detail"] for segment in segments))
            for term in term_cards:
                self.assertTrue(term["detail"])
                if term["is_english"]:
                    self.assertTrue(
                        any(segment["lang"] == "en-US" and segment["text"] == term["term"] for segment in segments),
                        term["term"],
                    )


if __name__ == "__main__":
    unittest.main()
