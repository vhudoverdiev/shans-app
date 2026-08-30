import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask, session
from werkzeug.datastructures import MultiDict

from config import Config
from app import create_app
from app.database import get_master_connection
from app.learning import (
    DAILY_PASS_SCORE,
    ENGLISH_LESSONS,
    FINAL_PASS_SCORE,
    REVIEW_MILESTONES,
    VIDEO_PASS_SCORE,
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
    _english_speech,
    _get_final_result,
    _get_it_final_result,
    _it_course_state,
    _it_audio_segments,
    _review_cards,
    _save_day_result,
    _save_final_result,
    _reset_day_result,
    _reset_final_result,
    _reset_it_day_result,
    _reset_it_final_result,
    _save_it_day_result,
    _save_it_final_result,
    _get_course_state,
    _base_quiz_for_attempt,
    _delete_live_quiz_attempt,
    _load_live_quiz_attempt,
    _live_quiz_seed,
    _public_question,
    _extra_question_count,
    _extra_stage_passed,
    _save_course_day_result,
    _save_live_quiz_attempt,
    _stored_score,
    build_daily_quiz,
    build_extra_quiz,
    build_final_quiz,
    build_it_daily_quiz,
    build_it_final_quiz,
    build_review_quiz,
    build_video_lesson_quiz,
    grade_quiz,
    init_learning_db,
    shuffle_quiz,
)
from app.it_course_content import IT_LESSONS
from app.python_video_course_content import PYTHON_VIDEO_LESSONS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = PROJECT_ROOT / "app" / "templates"
LEARNING_STYLES = PROJECT_ROOT / "app" / "static" / "css" / "learning.css"
MOBILE_STYLES = PROJECT_ROOT / "app" / "static" / "css" / "mobile.css"
COURSE_AUDIO_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "course-audio.js"
COURSE_DAY_ACTIONS_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "course-day-actions.js"
PYTHON_VIDEO_DIRECTORY = PROJECT_ROOT / "app" / "static" / "videos" / "python-basics"
LIVE_QUIZ_SCRIPT = PROJECT_ROOT / "app" / "static" / "js" / "live-quiz.js"


def correct_quiz_form(questions):
    values = []
    for index, question in enumerate(questions):
        name = f"question_{index}"
        answer_type = question.get("answer_type", "single")
        if answer_type == "text":
            values.append((name, question["accepted_answers"][0]))
        elif answer_type == "multiple":
            values.extend((name, str(answer_index)) for answer_index in question["correct_indices"])
        else:
            values.append((name, str(question["correct_index"])))
    return MultiDict(values)


def live_correct_answer(question):
    if question.get("answer_type") == "text":
        return question["accepted_answers"][0]
    if question.get("answer_type") == "multiple":
        return [str(index) for index in question["correct_indices"]]
    return str(question["correct_index"])


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

    def test_each_wrong_answer_adds_two_questions_from_the_same_lesson(self):
        for course_key, current_number in (("english", 1), ("it", 2), ("video", 3)):
            for wrong_count in (1, 3, 20):
                extra_count = _extra_question_count(wrong_count)
                self.assertEqual(extra_count, wrong_count * 2)
                questions = build_extra_quiz(
                    course_key, current_number, extra_count, seed=12345
                )
                self.assertEqual(len(questions), extra_count)
                self.assertTrue(
                    all(question["source_number"] == current_number for question in questions)
                )

    def test_extra_questions_are_repeatable_and_stay_in_current_section(self):
        first = build_extra_quiz("english", 7, 6, seed=9876)
        second = build_extra_quiz("english", 7, 6, seed=9876)
        self.assertEqual(first, second)
        self.assertEqual({question["source_number"] for question in first}, {7})

    def test_one_extra_mistake_passes_but_two_require_full_retry(self):
        self.assertTrue(_extra_stage_passed(2, 2))
        self.assertTrue(_extra_stage_passed(3, 4))
        self.assertFalse(_extra_stage_passed(2, 4))
        self.assertFalse(_extra_stage_passed(0, 2))

    def test_combined_score_is_saved_on_existing_twenty_point_scale(self):
        self.assertEqual(_stored_score(21, 22), 19)
        self.assertEqual(_stored_score(16, 20), 16)

    def test_daily_and_video_templates_render_mandatory_extra_stage(self):
        for template_name in ("english_day_test.html", "it_day_test.html", "it_video_lesson.html"):
            source = (TEMPLATES / template_name).read_text(encoding="utf-8")
            self.assertIn('name="quiz_stage" value="extra"', source)
            self.assertIn("extra_questions", source)
            self.assertIn("по 2 новых вопроса", source)
            self.assertIn("из этого же", source)
            self.assertNotIn('name="base_score"', source)

    def test_every_daily_quiz_has_twenty_valid_questions(self):
        for day_number in range(1, 31):
            questions = build_daily_quiz(day_number)
            self.assertEqual(len(questions), 20)
            for question in questions:
                if question.get("answer_type") == "text":
                    self.assertTrue(question["accepted_answers"])
                elif question.get("answer_type") == "multiple":
                    self.assertEqual(len(question["correct_indices"]), 2)
                else:
                    self.assertIn(question["correct_index"], range(len(question["options"])))

    def test_quiz_grading_accepts_correct_answers_and_handles_missing_answers(self):
        questions = build_daily_quiz(1)
        correct_form = correct_quiz_form(questions)

        score, feedback = grade_quiz(questions, correct_form)
        missing_score, missing_feedback = grade_quiz(questions, {})

        self.assertEqual(score, len(questions))
        self.assertTrue(all(item["is_correct"] for item in feedback))
        self.assertEqual(feedback[0]["selected_answer"], questions[0]["accepted_answers"][0])
        self.assertEqual(feedback[0]["correct_answer"], questions[0]["accepted_answers"][0])
        self.assertEqual(missing_score, 0)
        self.assertFalse(any(item["is_correct"] for item in missing_feedback))
        self.assertEqual(missing_feedback[0]["selected_answer"], "не выбран")
        self.assertEqual(missing_feedback[0]["correct_answer"], questions[0]["accepted_answers"][0])
        self.assertEqual(DAILY_PASS_SCORE, 16)

    def test_main_courses_use_recall_multiple_selection_and_single_choice_tasks(self):
        quiz_sets = (
            build_daily_quiz(1),
            build_it_daily_quiz(1),
            build_video_lesson_quiz(1, seed=17),
        )
        for questions in quiz_sets:
            answer_types = [question.get("answer_type", "single") for question in questions]
            self.assertGreaterEqual(answer_types.count("text"), 3)
            self.assertGreaterEqual(answer_types.count("multiple"), 2)
            self.assertIn("single", answer_types)

    def test_text_answers_are_tolerant_but_multiple_selection_requires_exact_set(self):
        questions = [
            {
                "answer_type": "text",
                "prompt": "Введите ответ",
                "accepted_answers": ("Ёлка, тест!",),
                "explanation": "Проверка текста.",
            },
            {
                "answer_type": "multiple",
                "prompt": "Выберите два",
                "options": ("A", "B", "C", "D"),
                "correct_indices": (0, 2),
                "explanation": "A и C.",
            },
        ]
        correct_score, _ = grade_quiz(
            questions,
            MultiDict((("question_0", "  елка ТЕСТ  "), ("question_1", "2"), ("question_1", "0"))),
        )
        incomplete_score, feedback = grade_quiz(
            questions,
            MultiDict((("question_0", "другой ответ"), ("question_1", "0"), ("question_1", "99"))),
        )
        self.assertEqual(correct_score, 2)
        self.assertEqual(incomplete_score, 0)
        self.assertFalse(any(item["is_correct"] for item in feedback))

    def test_every_attempt_shuffles_questions_and_all_choice_types_safely(self):
        original = build_daily_quiz(1)
        first = shuffle_quiz(original, seed=111)
        repeated = shuffle_quiz(original, seed=111)
        second = shuffle_quiz(original, seed=222)

        self.assertEqual(first, repeated)
        self.assertNotEqual(
            [question["prompt"] for question in first],
            [question["prompt"] for question in second],
        )
        for questions in (first, second):
            score, feedback = grade_quiz(questions, correct_quiz_form(questions))
            self.assertEqual(score, 20)
            self.assertTrue(all(item["is_correct"] for item in feedback))

    def test_daily_templates_keep_attempt_seed_for_server_grading(self):
        for template_name in ("english_day_test.html", "it_day_test.html", "it_video_lesson.html"):
            source = (TEMPLATES / template_name).read_text(encoding="utf-8")
            self.assertIn('name="quiz_seed" value="{{ quiz_seed }}"', source)

    def test_live_quiz_checks_each_answer_and_adds_questions_immediately(self):
        script = LIVE_QUIZ_SCRIPT.read_text(encoding="utf-8")
        template = (TEMPLATES / "_quiz_question_fields.html").read_text(encoding="utf-8")
        for marker in (
            "data-live-quiz",
            "checkQuestion(fieldset)",
            "added_questions",
            "showFeedback(fieldset, result)",
            "recoverCompletedAttempt()",
            "answers: answeredSnapshot()",
            '"Осталось ответить: " + remaining',
            'submitButton.textContent = "Повторить завершение"',
            'checked.length !== 2',
            'event.target.closest("[data-answer-question]")',
        ):
            self.assertIn(marker, script if marker != "data-live-quiz" else " ".join(
                (TEMPLATES / name).read_text(encoding="utf-8")
                for name in ("english_day_test.html", "it_day_test.html", "it_video_lesson.html")
            ))
        self.assertIn("data-live-feedback", template)
        self.assertIn("data-answer-question", template)
        self.assertNotIn('form.addEventListener("change"', script)
        self.assertNotIn('form.addEventListener("focusout"', script)
        self.assertNotIn("Дополнительное закрепление", script)
        self.assertNotIn("Новые вопросы появляются здесь", script)
        self.assertNotIn("quiz-live-extra-heading", script)
        self.assertNotIn("showCompletion", script)
        self.assertIn('submitButton.disabled = true', script)
        self.assertIn('submitButton.textContent = "Ответьте на все вопросы"', script)
        self.assertIn("result.continue_label", script)
        self.assertIn("window.location.assign(submitButton.dataset.continueUrl)", script)
        for template_name in ("english_day_test.html", "it_day_test.html", "it_video_lesson.html"):
            source = (TEMPLATES / template_name).read_text(encoding="utf-8")
            live_form = source.split("data-live-quiz", 1)[1].split("</form>", 1)[0]
            self.assertIn("data-sync-url=", live_form)
            self.assertIn('_quiz_attempt_reset.html', source)
            self.assertIn("disabled>Ответьте на все вопросы</button>", live_form)
            self.assertNotIn(">Проверить ответы</button>", live_form)

    def test_each_question_requires_an_explicit_adaptive_answer_button(self):
        template = (TEMPLATES / "_quiz_question_fields.html").read_text(encoding="utf-8")
        script = LIVE_QUIZ_SCRIPT.read_text(encoding="utf-8")
        styles = LEARNING_STYLES.read_text(encoding="utf-8")

        self.assertIn('data-answer-question>Ответить</button>', template)
        self.assertIn(".quiz-answer-button", styles)
        self.assertIn("width: 100%", styles.split(".quiz-answer-button", 2)[-1])
        self.assertIn("showInputPrompt", script)

    def test_live_quiz_serializes_answer_requests_without_losing_session_progress(self):
        script = LIVE_QUIZ_SCRIPT.read_text(encoding="utf-8")

        # Flask's cookie session is replaced by every response. Two parallel
        # checks could both look successful in the UI while the later cookie
        # discarded the other answer and left continuation disabled.
        self.assertIn("let answerQueue = Promise.resolve()", script)
        self.assertIn("fieldset.dataset.queued", script)
        self.assertIn("answerQueue = answerQueue", script)
        self.assertIn('.then(function () { return checkQuestion(fieldset); })', script)
        self.assertIn('enqueueQuestion(button.closest("[data-live-question]"))', script)
        self.assertNotIn('checkQuestion(button.closest("[data-live-question]"))', script)

    def test_live_quiz_never_sends_correct_answers_to_browser(self):
        questions = _base_quiz_for_attempt("it", 1, seed=1357)
        for index, question in enumerate(questions):
            public = _public_question(question, index)
            self.assertNotIn("correct_index", public)
            self.assertNotIn("correct_indices", public)
            self.assertNotIn("accepted_answers", public)
            self.assertEqual(public["live_index"], index)

    def test_quiz_english_fragments_have_pronunciation_controls_in_all_courses(self):
        self.assertEqual(
            _english_speech("Что означают Python, REST API и backend developer?"),
            "Python; REST API; backend developer",
        )
        self.assertEqual(_english_speech("слово в IT-вакансии"), "IT")
        public = _public_question(
            {
                "prompt": "Что означает Python?",
                "options": ("язык программирования", "Python language"),
                "correct_index": 0,
            },
            0,
        )
        self.assertEqual(public["prompt_speech"], "Python")
        self.assertEqual(public["option_speech"], ["", "Python language"])

        question_template = (TEMPLATES / "_quiz_question_fields.html").read_text(encoding="utf-8")
        audio_script = COURSE_AUDIO_SCRIPT.read_text(encoding="utf-8")
        live_script = LIVE_QUIZ_SCRIPT.read_text(encoding="utf-8")
        for marker in ("english_speech", "data-course-pronounce", "quiz-pronounce-button"):
            self.assertIn(marker, question_template)
        self.assertIn('document.addEventListener("click"', audio_script)
        self.assertIn('event.target.closest("[data-course-pronounce]")', audio_script)
        self.assertIn("buildPronounceButton", live_script)
        self.assertIn("question.prompt_speech", live_script)
        self.assertIn("question.option_speech", live_script)
        for template_name in ("english_day_test.html", "it_day_test.html", "it_video_lesson.html"):
            source = (TEMPLATES / template_name).read_text(encoding="utf-8")
            self.assertIn("course-audio.js", source)
            self.assertIn("data-quiz-pronounce-status", source)

    def test_partial_live_attempt_reuses_its_seed_after_returning_to_lesson(self):
        app = Flask(__name__)
        app.secret_key = "test-secret"
        with app.test_request_context("/"):
            first_seed = _live_quiz_seed("english", 4)
            repeated_seed = _live_quiz_seed("english", 4)
            another_course_seed = _live_quiz_seed("it", 4)
            self.assertEqual(first_seed, repeated_seed)
            self.assertIsInstance(another_course_seed, int)
            self.assertIn("live_quiz_seed:english:4", session)

    def test_partial_live_attempt_survives_server_restart_in_database(self):
        state = {
            "base": {"0": {"correct": True, "answer": "Привет, меня зовут Алекс"}},
            "extra": {"0": {"correct": True, "answer": "пожалуйста"}},
            "extra_count": 2,
        }
        _save_live_quiz_attempt(17, "english", 1, 123456, state)

        # Re-running startup migrations represents a new server process. The
        # unfinished attempt must remain independent of its old cookie session.
        init_learning_db()
        self.assertEqual(
            _load_live_quiz_attempt(17, "english", 1),
            {"seed": 123456, "state": state},
        )

        _delete_live_quiz_attempt(17, "english", 1)
        self.assertIsNone(_load_live_quiz_attempt(17, "english", 1))

    def test_live_quiz_restores_partial_answers_and_added_questions(self):
        script = LIVE_QUIZ_SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "restoreAttempt()",
            "restoreAnswerGroup",
            "state.extra_questions",
            "state.base_answers",
            "state.extra_answers",
            "if (state.complete) enableContinuation(state)",
            'cache: "no-store"',
        ):
            self.assertIn(marker, script)
        for template_name in ("english_day_test.html", "it_day_test.html", "it_video_lesson.html"):
            source = (TEMPLATES / template_name).read_text(encoding="utf-8")
            self.assertIn("data-state-url=", source)


    def test_review_quizzes_cover_each_five_day_block_for_both_courses(self):
        self.assertEqual(REVIEW_MILESTONES, (5, 10, 15, 20, 25, 30))
        for course_key in ("english", "it"):
            for end_day in REVIEW_MILESTONES:
                questions = build_review_quiz(course_key, end_day, seed=12345)
                self.assertEqual(len(questions), 10)
                self.assertEqual(
                    {question["day"] for question in questions},
                    set(range(end_day - 4, end_day + 1)),
                )
                for day_number in range(end_day - 4, end_day + 1):
                    self.assertEqual(
                        sum(question["day"] == day_number for question in questions),
                        2,
                    )

    def test_review_question_and_answer_order_is_shuffled_but_grading_stays_valid(self):
        first_attempt = build_review_quiz("english", 5, seed=11)
        repeated_seed = build_review_quiz("english", 5, seed=11)
        next_attempt = build_review_quiz("english", 5, seed=987654)

        self.assertEqual(first_attempt, repeated_seed)
        self.assertNotEqual(first_attempt, next_attempt)
        for questions in (first_attempt, next_attempt):
            correct_form = correct_quiz_form(questions)
            score, feedback = grade_quiz(questions, correct_form)
            self.assertEqual(score, 10)
            self.assertTrue(all(item["is_correct"] for item in feedback))

    def test_review_cards_unlock_only_after_each_complete_five_day_milestone(self):
        cards = _review_cards(set(range(1, 8)))

        self.assertEqual(len(cards), 6)
        self.assertTrue(cards[0]["unlocked"])
        self.assertEqual((cards[0]["start_day"], cards[0]["end_day"]), (1, 5))
        self.assertFalse(cards[1]["unlocked"])

    def test_review_templates_are_available_in_both_courses(self):
        english_source = (TEMPLATES / "english_course.html").read_text(encoding="utf-8")
        it_source = (TEMPLATES / "it_course.html").read_text(encoding="utf-8")
        review_source = (TEMPLATES / "course_review.html").read_text(encoding="utf-8")

        for source, course_key in ((english_source, "english"), (it_source, "it")):
            self.assertIn("Дополнительные тесты каждые 5 дней", source)
            self.assertIn("review_tests", source)
            self.assertIn(f"course_key='{course_key}'", source)
        self.assertIn('name="quiz_seed"', review_source)
        self.assertIn("Новая попытка", review_source)
        self.assertIn("Вопросы и варианты ответов перемешиваются", review_source)

    def test_python_video_course_contains_all_22_local_videos(self):
        self.assertEqual(len(PYTHON_VIDEO_LESSONS), 22)
        self.assertEqual(PYTHON_VIDEO_LESSONS[0]["title"], "Что такое программирование и Python")
        self.assertEqual(
            [lesson["day"] for lesson in PYTHON_VIDEO_LESSONS],
            list(range(1, 23)),
        )
        for lesson in PYTHON_VIDEO_LESSONS:
            video_path = PROJECT_ROOT / "app" / "static" / lesson["video_file"]
            self.assertTrue(video_path.is_file(), video_path)
            self.assertGreater(video_path.stat().st_size, 100_000)
            self.assertLess(video_path.stat().st_size, 100 * 1024 * 1024)
            with video_path.open("rb") as video_file:
                self.assertIn(b"ftyp", video_file.read(12))

    def test_every_python_video_has_a_specific_valid_quiz(self):
        for lesson in PYTHON_VIDEO_LESSONS:
            questions = build_video_lesson_quiz(lesson["day"], seed=lesson["day"])
            self.assertEqual(len(questions), 20)
            quiz_copy = " ".join(
                question["prompt"] + " " + question["explanation"]
                for question in questions
            )
            for term, definition in lesson["facts"]:
                self.assertIn(term, quiz_copy)
                self.assertIn(definition, quiz_copy)
            for question in questions:
                if question.get("answer_type") == "text":
                    self.assertTrue(question["accepted_answers"])
                elif question.get("answer_type") == "multiple":
                    self.assertEqual(len(question["correct_indices"]), 2)
                else:
                    self.assertIn(question["correct_index"], range(4))
        self.assertEqual(VIDEO_PASS_SCORE, 16)

    def test_python_video_progress_requires_each_previous_test(self):
        progress, passed_lessons, next_lesson = _get_course_state(
            41, "video", PYTHON_VIDEO_LESSONS
        )
        self.assertEqual((progress, passed_lessons, next_lesson), ({}, set(), 1))

        _save_course_day_result(41, 1, 2, False, "video")
        self.assertEqual(
            _get_course_state(41, "video", PYTHON_VIDEO_LESSONS)[2], 1
        )
        _save_course_day_result(41, 1, 4, True, "video")
        progress, passed_lessons, next_lesson = _get_course_state(
            41, "video", PYTHON_VIDEO_LESSONS
        )
        self.assertEqual(passed_lessons, {1})
        self.assertEqual(next_lesson, 2)
        self.assertEqual(progress[1]["best_score"], 4)

    def test_it_templates_expose_responsive_video_course_and_required_tests(self):
        it_course_source = (TEMPLATES / "it_course.html").read_text(encoding="utf-8")
        video_course_source = (TEMPLATES / "it_video_course.html").read_text(encoding="utf-8")
        video_lesson_source = (TEMPLATES / "it_video_lesson.html").read_text(encoding="utf-8")
        styles = LEARNING_STYLES.read_text(encoding="utf-8")

        self.assertIn("Фундамент IT", it_course_source)
        self.assertIn("22 видеоурока", video_course_source)
        self.assertIn("обязательный тест", video_course_source)
        self.assertIn('<video class="python-course-video" controls playsinline preload="metadata">', video_lesson_source)
        self.assertIn("lesson.video_file", video_lesson_source)
        self.assertIn('name="quiz_seed"', video_lesson_source)
        self.assertIn("Проверка после видео", video_lesson_source)
        self.assertIn(".python-course-video", styles)
        self.assertIn("@media (max-width: 760px) and (pointer: coarse)", styles)

    def test_video_lesson_has_topic_poster_and_accessible_floating_player(self):
        video_lesson_source = (TEMPLATES / "it_video_lesson.html").read_text(encoding="utf-8")
        player_script = (PROJECT_ROOT / "app" / "static" / "js" / "floating-video-player.js").read_text(encoding="utf-8")
        styles = LEARNING_STYLES.read_text(encoding="utf-8")

        self.assertIn("data-video-poster", video_lesson_source)
        self.assertIn("{% block title %}{{ lesson.title }} | Шанс{% endblock %}", video_lesson_source)
        self.assertNotIn("Видео {{ lesson.day }} — {{ lesson.title }}", video_lesson_source)
        self.assertIn("Видеоурок {{ lesson.day }} из 22", video_lesson_source)
        self.assertIn("{{ lesson.title }}", video_lesson_source)
        self.assertIn('class="python-video-play-icon"', video_lesson_source)
        self.assertNotIn(">▶</span>", video_lesson_source)
        self.assertIn("data-video-expand", video_lesson_source)
        self.assertIn("data-video-close", video_lesson_source)
        self.assertIn("floating-video-player.js", video_lesson_source)
        self.assertIn("new IntersectionObserver", player_script)
        self.assertIn('video.addEventListener("play"', player_script)
        self.assertIn("video.pause()", player_script)
        self.assertIn("scrollIntoView", player_script)
        self.assertIn(".python-video-shell-floating", styles)
        self.assertIn("prefers-reduced-motion: reduce", styles)

    def test_video_quiz_is_revealed_by_an_adaptive_button(self):
        template = (TEMPLATES / "it_video_lesson.html").read_text(encoding="utf-8")
        reveal_script = (PROJECT_ROOT / "app" / "static" / "js" / "lesson-quiz.js").read_text(encoding="utf-8")
        live_quiz_script = LIVE_QUIZ_SCRIPT.read_text(encoding="utf-8")
        styles = LEARNING_STYLES.read_text(encoding="utf-8")

        self.assertIn('data-quiz-reveal-button data-quiz-target="video-test"', template)
        self.assertIn('aria-controls="video-test"', template)
        self.assertIn('data-quiz-form-shell{% if score is none %} hidden{% endif %}', template)
        self.assertIn("lesson-quiz.js", template)
        self.assertIn('shell.addEventListener("livequiz:restored"', reveal_script)
        self.assertIn('form.dispatchEvent(new CustomEvent("livequiz:restored"', live_quiz_script)
        self.assertIn(".video-quiz-launch .quiz-reveal-button", styles)

    def test_it_course_tabs_are_blue_on_desktop_and_purple_on_mobile(self):
        styles = LEARNING_STYLES.read_text(encoding="utf-8")
        active_tab_rule = styles.split(".learning-course-tab-active", 1)[1].split("}", 1)[0]
        mobile_rules = styles.split("@media (max-width: 760px) and (pointer: coarse)", 1)[1]

        self.assertIn("background: #2563eb", active_tab_rule)
        self.assertIn("background: #7c3aed", mobile_rules)
        self.assertIn(".learning-course-nav", styles)

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
        self.assertIn(">Разработчик Python<", study_source)
        self.assertIn(">English и IT<", study_source)
        self.assertIn("url_for('learning.english_it_hub')", study_source)
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

    def test_learning_hub_uses_neutral_header_without_hero_block(self):
        study_source = (TEMPLATES / "study_hub.html").read_text(encoding="utf-8")
        styles = LEARNING_STYLES.read_text(encoding="utf-8")

        self.assertIn("section-styled-page", study_source)
        self.assertIn("<h1>Развитие</h1>", study_source)
        self.assertNotIn("learning-hero-compact", study_source)
        self.assertNotIn("learning-hero", study_source)
        self.assertNotIn("learning-kicker", study_source)
        self.assertIn(".learning-page .study-direction-grid .dashboard-card", styles)

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
            self.assertEqual(len(lesson["lecture"]), 5)
            self.assertEqual(len(lesson["terms"]), 10)
            self.assertEqual(len({term for term, _definition in lesson["terms"]}), 10)
            self.assertTrue(lesson["practice"])
            self.assertEqual(len(lesson["checkpoint"]["options"]), 4)

    def test_lesson_templates_show_expanded_material_and_real_term_count(self):
        it_source = (TEMPLATES / "it_day.html").read_text(encoding="utf-8")
        english_source = (TEMPLATES / "english_day.html").read_text(encoding="utf-8")
        video_source = (TEMPLATES / "it_video_lesson.html").read_text(encoding="utf-8")

        self.assertIn("{{ term_cards|length }} терминов дня", it_source)
        self.assertNotIn("6 терминов дня", it_source)
        self.assertIn("{{ lecture_points|length }} смысловым частям", it_source)
        self.assertIn("<strong>Цель дня:</strong>", english_source)
        self.assertIn("Конспект видео", video_source)
        self.assertIn("{% for term, definition in lesson.facts %}", video_source)

    def test_every_it_daily_quiz_and_final_quiz_are_valid(self):
        for day_number in range(1, 31):
            questions = build_it_daily_quiz(day_number)
            self.assertEqual(len(questions), 20)
            quiz_copy = " ".join(
                question["prompt"] + " " + question["explanation"]
                for question in questions
            )
            for term, _definition in IT_LESSONS[day_number - 1]["terms"]:
                self.assertIn(term, quiz_copy)
            for question in questions:
                if question.get("answer_type") == "text":
                    self.assertTrue(question["accepted_answers"])
                elif question.get("answer_type") == "multiple":
                    self.assertEqual(len(question["correct_indices"]), 2)
                else:
                    self.assertIn(question["correct_index"], range(len(question["options"])))

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

        self.assertIn("Фундамент IT", course_source)
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
            self.assertNotIn('target="_blank"', source)
            self.assertNotIn('rel="noopener"', source)
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
        self.assertNotIn("window.open", day_actions_source)
        self.assertNotIn("openTestWithoutDarkFlash", day_actions_source)
        self.assertNotIn('link.target = "_blank"', day_actions_source)
        self.assertNotIn('link.rel = "noopener"', day_actions_source)
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
            self.assertIn("item.selected_answer", source)
            self.assertIn("item.correct_answer", source)
            self.assertIn('id="daily-test-result"', source)
            self.assertIn("_anchor='daily-test-result'", source)
            self.assertIn("Ответьте на все вопросы", source)
            self.assertNotIn(">Проверить ответы</button>", source)
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
        self.assertIn(".quiz-feedback-item span b", learning_styles)
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
        self.assertEqual(len(it_points), 5)
        self.assertEqual(it_points[0]["text"], IT_LESSONS[0]["lecture"][0])
        self.assertGreater(len(it_points[0]["detail"]), 50)
        self.assertIn(IT_LESSONS[0]["title"], it_points[0]["detail"])

    def test_more_details_content_is_expanded_for_beginners(self):
        english_lesson = ENGLISH_LESSONS[0]
        english_details = _build_english_lecture_details(english_lesson)
        word_cards = _build_english_word_cards(english_lesson)
        phrase_cards = _build_english_phrase_cards(english_lesson)

        self.assertGreaterEqual(len(english_details), 3)
        self.assertTrue(any("Примитивный пример" in step for step in english_details))
        self.assertNotIn("Что изучаем:", english_details[0])
        self.assertGreaterEqual(len(word_cards[0]["detail_paragraphs"]), 3)
        self.assertGreaterEqual(len(phrase_cards[0]["detail_paragraphs"]), 3)
        self.assertNotIn("Значение:", word_cards[0]["detail"])
        self.assertTrue(any("Примитивный пример" in step for step in word_cards[0]["detail_paragraphs"]))

        it_lesson = IT_LESSONS[0]
        it_points = _build_it_lecture_points(it_lesson)
        term_cards = _build_it_term_cards(it_lesson)
        code_steps = _build_it_code_steps(IT_LESSONS[6])
        practice_steps = _build_it_practice_steps(it_lesson)

        self.assertGreaterEqual(len(it_points[0]["detail_paragraphs"]), 4)
        self.assertGreaterEqual(len(term_cards[0]["detail_paragraphs"]), 4)
        self.assertIn(term_cards[0]["definition"], term_cards[0]["detail"])
        self.assertTrue(any("Примитивный пример" in step for step in term_cards[0]["detail_paragraphs"]))
        self.assertTrue(any(step["explanation"] for step in code_steps))
        self.assertGreaterEqual(len(practice_steps), 4)

    def test_every_more_details_block_is_specific_to_its_own_learning_item(self):
        generic_phrases = (
            "пользователь нажал кнопку",
            "возьмите привычный процесс",
            "кандидат рассказывает о небольшом сервисе",
        )
        for lesson in ENGLISH_LESSONS:
            lecture_details = " ".join(_build_english_lecture_details(lesson))
            self.assertIn(lesson["title"], lecture_details)
            self.assertIn(lesson["focus"], lecture_details)
            for card in _build_english_word_cards(lesson):
                details = " ".join([card["detail"], *card["detail_paragraphs"]])
                self.assertIn(card["english"], details)
                self.assertIn(card["russian"], details)
                self.assertIn("Примитивный пример", details)
                self.assertIn("Мини-проверка", details)
            for card in _build_english_phrase_cards(lesson):
                details = " ".join([card["detail"], *card["detail_paragraphs"]])
                self.assertIn(card["english"], details)
                self.assertIn(card["russian"], details)
                self.assertIn("Порядок слов", details)

        for lesson in IT_LESSONS:
            lecture_points = _build_it_lecture_points(lesson)
            term_cards = _build_it_term_cards(lesson)
            practice_details = " ".join(_build_it_practice_steps(lesson))
            self.assertIn(lesson["practice"], practice_details)
            self.assertIn(lesson["title"], practice_details)
            for point, paragraph in zip(lecture_points, lesson["lecture"]):
                details = " ".join([point["detail"], *point["detail_paragraphs"]])
                self.assertIn(paragraph.split(".")[0].strip(), details)
                self.assertIn(lesson["practice"], details)
            for card in term_cards:
                details = " ".join([card["detail"], *card["detail_paragraphs"]])
                self.assertIn(card["term"], details)
                self.assertIn(card["definition"], details)
                self.assertIn(lesson["practice"], details)
                self.assertIn("Самопроверка", details)
            combined = " ".join(
                point["detail"] for point in lecture_points
            ) + " " + " ".join(card["detail"] for card in term_cards)
            for phrase in generic_phrases:
                self.assertNotIn(phrase, combined.lower())

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


class EnglishLiveQuizRouteTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.original_environment = Config.ENV
        self.original_secret_key = Config.SECRET_KEY
        self.original_admin_username = os.environ.get("ADMIN_USERNAME")
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        self.temp_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        Config.DATABASE_NAME = str(Path(self.temp_directory.name) / "learning-route.db")
        Config.ENV = "testing"
        Config.SECRET_KEY = "learning-route-secret"
        os.environ["ADMIN_USERNAME"] = "admin"
        os.environ["ADMIN_PASSWORD"] = "AdminPass-2026"
        with patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": "false"}):
            self.app = create_app()
        self.app.config.update(TESTING=True)

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        Config.ENV = self.original_environment
        Config.SECRET_KEY = self.original_secret_key
        if self.original_admin_username is None:
            os.environ.pop("ADMIN_USERNAME", None)
        else:
            os.environ["ADMIN_USERNAME"] = self.original_admin_username
        if self.original_admin_password is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self.original_admin_password
        self.temp_directory.cleanup()

    def test_one_base_mistake_and_correct_extra_answers_unlock_next_english_day(self):
        conn = get_master_connection()
        try:
            user_id = int(conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()["id"])
        finally:
            conn.close()
        client = self.app.test_client()
        with client.session_transaction() as browser_session:
            browser_session["_user_id"] = str(user_id)
            browser_session["_fresh"] = True
            browser_session["_csrf_token"] = "test-token"

        page = client.get("/study/english/day/1/test")
        self.assertEqual(page.status_code, 200)
        seed_match = re.search(rb'data-quiz-seed="(\d+)"', page.data)
        self.assertIsNotNone(seed_match)
        seed = int(seed_match.group(1))
        base_questions = _base_quiz_for_attempt("english", 1, seed)
        headers = {"X-CSRFToken": "test-token"}

        for index, question in enumerate(base_questions):
            answer = "__deliberately_wrong__" if index == 0 else live_correct_answer(question)
            response = client.post(
                "/study/quiz/check",
                json={
                    "course": "english", "item_number": 1, "seed": seed,
                    "stage": "base", "question_index": index, "answer": answer,
                },
                headers=headers,
            )
            self.assertEqual(response.status_code, 200)

        extras = build_extra_quiz("english", 1, 40, seed ^ 0x5F3759DF)
        for index in range(2):
            response = client.post(
                "/study/quiz/check",
                json={
                    "course": "english", "item_number": 1, "seed": seed,
                    "stage": "extra", "question_index": index,
                    "answer": live_correct_answer(extras[index]),
                },
                headers=headers,
            )
            self.assertEqual(response.status_code, 200)

        result = response.get_json()
        self.assertTrue(result["complete"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["continue_label"], "Перейти к дню 2")
        self.assertEqual(result["continue_url"], "/study/english/day/2")

        restored = client.get(
            f"/study/quiz/state?course=english&item_number=1&seed={seed}"
        )
        self.assertEqual(restored.status_code, 200)
        restored_result = restored.get_json()
        self.assertTrue(restored_result["complete"])
        self.assertTrue(restored_result["passed"])
        self.assertEqual(restored_result["continue_label"], "Перейти к дню 2")
        self.assertEqual(restored_result["continue_url"], "/study/english/day/2")

        day_two_page = client.get("/study/english/day/2/test")
        self.assertEqual(day_two_page.status_code, 200)
        day_two_seed = int(re.search(rb'data-quiz-seed="(\d+)"', day_two_page.data).group(1))
        day_two_questions = _base_quiz_for_attempt("english", 2, day_two_seed)
        day_two_snapshot = []
        for index, question in enumerate(day_two_questions):
            answer = "__deliberately_wrong__" if index == 5 else live_correct_answer(question)
            day_two_snapshot.append({"stage": "base", "index": index, "answer": answer})
            response = client.post(
                "/study/quiz/check",
                json={
                    "course": "english", "item_number": 2, "seed": day_two_seed,
                    "stage": "base", "question_index": index, "answer": answer,
                },
                headers=headers,
            )
            self.assertEqual(response.status_code, 200)

        day_two_extras = build_extra_quiz("english", 2, 40, day_two_seed ^ 0x5F3759DF)
        for index in range(2):
            extra_answer = live_correct_answer(day_two_extras[index])
            day_two_snapshot.append({"stage": "extra", "index": index, "answer": extra_answer})
            response = client.post(
                "/study/quiz/check",
                json={
                    "course": "english", "item_number": 2, "seed": day_two_seed,
                    "stage": "extra", "question_index": index,
                    "answer": extra_answer,
                },
                headers=headers,
            )
            self.assertEqual(response.status_code, 200)

        day_two_result = response.get_json()
        self.assertTrue(day_two_result["complete"])
        self.assertTrue(day_two_result["passed"])
        self.assertEqual(day_two_result["continue_label"], "Перейти к дню 3")

        stranded_attempt = _load_live_quiz_attempt(user_id, "english", 2)
        for key in ("complete", "passed", "score", "total", "pass_score"):
            stranded_attempt["state"].pop(key, None)
        _save_live_quiz_attempt(
            user_id, "english", 2, day_two_seed, stranded_attempt["state"]
        )
        recovered = client.get(
            f"/study/quiz/state?course=english&item_number=2&seed={day_two_seed}"
        )
        self.assertEqual(recovered.status_code, 200)
        recovered_result = recovered.get_json()
        self.assertTrue(recovered_result["complete"])
        self.assertTrue(recovered_result["passed"])
        self.assertEqual(recovered_result["continue_label"], "Перейти к дню 3")

        synchronized = client.post(
            "/study/quiz/sync",
            json={
                "course": "english", "item_number": 2, "seed": day_two_seed,
                "answers": day_two_snapshot,
            },
            headers=headers,
        )
        self.assertEqual(synchronized.status_code, 200)
        synchronized_result = synchronized.get_json()
        self.assertTrue(synchronized_result["complete"])
        self.assertTrue(synchronized_result["passed"])
        self.assertEqual(synchronized_result["continue_label"], "Перейти к дню 3")

        reset = client.post(
            "/study/quiz/reset",
            data={"_csrf_token": "test-token", "course": "english", "item_number": "2"},
        )
        self.assertEqual(reset.status_code, 302)
        self.assertIn("/study/english/day/2/test?restart=1", reset.headers["Location"])
        self.assertIsNone(_load_live_quiz_attempt(user_id, "english", 2))
        _progress, passed_days, next_day = _course_state(user_id)
        self.assertNotIn(2, passed_days)
        self.assertEqual(next_day, 2)


if __name__ == "__main__":
    unittest.main()
