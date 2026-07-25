import tempfile
import unittest
from pathlib import Path

from config import Config
from app.learning import (
    DAILY_PASS_SCORE,
    ENGLISH_LESSONS,
    FINAL_PASS_SCORE,
    _course_state,
    _get_final_result,
    _get_it_final_result,
    _it_course_state,
    _save_day_result,
    _save_final_result,
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

    def test_study_hub_exposes_both_active_courses(self):
        study_source = (TEMPLATES / "study_hub.html").read_text(encoding="utf-8")
        base_source = (TEMPLATES / "base.html").read_text(encoding="utf-8")

        self.assertIn(">IT<", study_source)
        self.assertIn("Фундамент IT на Python", study_source)
        self.assertIn("url_for('learning.english_course')", study_source)
        self.assertIn("url_for('learning.it_course')", study_source)
        self.assertNotIn("Скоро", study_source)
        self.assertIn(
            ">Учёба</a>",
            base_source,
        )

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


if __name__ == "__main__":
    unittest.main()
