import tempfile
import unittest
from pathlib import Path

from config import Config
from app.database import get_master_connection
from app.learning import (
    PYTHON_LESSONS,
    _base_quiz_for_attempt,
    build_python_daily_quiz,
    build_python_final_quiz,
    init_learning_db,
)
from app.python_course_content import PYTHON_INTERVIEW_SECTIONS


class PythonCourseTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temp_directory = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_directory.name) / "learning.db")
        init_learning_db()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_directory.cleanup()

    def test_course_has_thirty_complete_lessons(self):
        self.assertEqual([lesson["day"] for lesson in PYTHON_LESSONS], list(range(1, 31)))
        for lesson in PYTHON_LESSONS:
            self.assertTrue(lesson["title"])
            self.assertTrue(lesson["summary"])
            self.assertGreaterEqual(len(lesson["terms"]), 8)
            self.assertGreaterEqual(len(lesson["lecture"]), 3)
            self.assertTrue(lesson["practice"])
            self.assertTrue(lesson["code"])
            self.assertTrue(lesson["project"]["title"])
            self.assertTrue(lesson["project"]["file_name"])
            self.assertGreaterEqual(len(lesson["project"]["steps"]), 5)
            self.assertTrue(lesson["project"]["result"])

    def test_every_day_has_twenty_valid_questions(self):
        for day in range(1, 31):
            questions = build_python_daily_quiz(day)
            self.assertEqual(len(questions), 20)
            for question in questions:
                self.assertTrue(question["prompt"])
                if question.get("answer_type") == "text":
                    self.assertTrue(question["accepted_answers"])
                elif question.get("answer_type") == "multiple":
                    self.assertTrue(question["correct_indices"])
                    self.assertTrue(all(index < len(question["options"]) for index in question["correct_indices"]))
                else:
                    self.assertGreaterEqual(question["correct_index"], 0)
                    self.assertLess(question["correct_index"], len(question["options"]))

    def test_live_and_final_quizzes_are_available(self):
        base = build_python_daily_quiz(7)
        live = _base_quiz_for_attempt("python", 7, 12345)
        self.assertEqual({question["prompt"] for question in base}, {question["prompt"] for question in live})
        self.assertGreaterEqual(len(build_python_final_quiz()), 30)

    def test_python_progress_tables_are_created(self):
        connection = get_master_connection()
        try:
            names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        finally:
            connection.close()
        self.assertIn("python_course_progress", names)
        self.assertIn("python_final_results", names)

    def test_interview_section_covers_all_required_tracks(self):
        titles = " ".join(section[0] for section in PYTHON_INTERVIEW_SECTIONS).lower()
        for required in ("python", "django", "ооп", "алгоритм", "баз", "систем", "soft"):
            self.assertIn(required, titles)
        self.assertGreaterEqual(
            sum(len(section[1]) for section in PYTHON_INTERVIEW_SECTIONS),
            45,
        )


if __name__ == "__main__":
    unittest.main()
