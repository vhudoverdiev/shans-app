import tempfile
import unittest
from pathlib import Path

from config import Config
from app.database import get_master_connection
from app.go_course_content import GO_LESSONS
from app.learning import build_go_daily_quiz, init_learning_db


ROOT = Path(__file__).resolve().parents[1]


class GoCourseTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temp_directory = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_directory.name) / "go-course.db")
        init_learning_db()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_directory.cleanup()

    def test_go_course_has_twenty_complete_sequential_lessons(self):
        self.assertEqual([lesson["day"] for lesson in GO_LESSONS], list(range(1, 31)))
        for lesson in GO_LESSONS:
            self.assertGreaterEqual(len(lesson["terms"]), 8)
            self.assertGreaterEqual(len(lesson["lecture"]), 4)
            self.assertTrue(lesson["code"])
            self.assertTrue(lesson["practice"])

    def test_every_go_lesson_has_twenty_valid_questions(self):
        for day in range(1, 31):
            questions = build_go_daily_quiz(day)
            self.assertEqual(len(questions), 20)
            for question in questions:
                self.assertEqual(len(question["options"]), 4)
                self.assertIn(question["correct_index"], range(4))

    def test_go_progress_tables_exist(self):
        connection = get_master_connection()
        try:
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()
        self.assertIn("go_course_progress", names)
        self.assertIn("go_final_results", names)

    def test_go_templates_include_video_text_practice_and_test(self):
        catalog = (ROOT / "app/templates/go_course.html").read_text(encoding="utf-8")
        lesson = (ROOT / "app/templates/go_day.html").read_text(encoding="utf-8")
        hub = (ROOT / "app/templates/english_it_hub.html").read_text(encoding="utf-8")
        learning = (ROOT / "app/learning.py").read_text(encoding="utf-8")
        self.assertIn("30 последовательных дней", catalog)
        for marker in ("data-floating-video-player", "Текстовая лекция", "Рабочий пример", "Задание урока", "Перейти к тесту"):
            self.assertIn(marker, lesson)
        self.assertIn("Семь направлений", hub)
        self.assertIn('"title": "Язык Go"', learning)

    def test_all_go_video_segments_are_valid_mp4(self):
        directory = ROOT / "app/static/videos/go-course"
        files = sorted(directory.glob("lesson-*.mp4"))
        self.assertEqual([path.name for path in files], [f"lesson-{day:02d}.mp4" for day in range(1, 31)])
        for path in files:
            self.assertGreater(path.stat().st_size, 1024 * 1024, path)
            with path.open("rb") as video:
                self.assertEqual(video.read(8)[4:8], b"ftyp", path)


if __name__ == "__main__":
    unittest.main()
