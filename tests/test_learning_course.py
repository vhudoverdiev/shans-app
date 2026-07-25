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
    _save_day_result,
    _save_final_result,
    build_daily_quiz,
    build_final_quiz,
    grade_quiz,
    init_learning_db,
)


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

    def test_study_hub_exposes_english_and_keeps_it_as_placeholder(self):
        study_source = (TEMPLATES / "study_hub.html").read_text(encoding="utf-8")
        base_source = (TEMPLATES / "base.html").read_text(encoding="utf-8")

        self.assertIn(">IT<", study_source)
        self.assertIn("Скоро", study_source)
        self.assertIn("url_for('learning.english_course')", study_source)
        self.assertNotIn("learning.it", study_source)
        self.assertIn(
            ">Учёба</a>",
            base_source,
        )


if __name__ == "__main__":
    unittest.main()
