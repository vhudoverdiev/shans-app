from pathlib import Path
import tempfile
import unittest

from config import Config
from app.database import get_master_connection
from app.html_course_content import HTML_THEMES
from app.learning import build_html_theme_quiz, init_learning_db


ROOT = Path(__file__).resolve().parents[1]


class HtmlCourseTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temp_directory = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_directory.name) / "html-course.db")
        init_learning_db()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_directory.cleanup()

    def test_course_is_split_into_named_themes_not_days(self):
        self.assertEqual([theme["number"] for theme in HTML_THEMES], list(range(1, 14)))
        self.assertTrue(all(theme["day"] == theme["number"] for theme in HTML_THEMES))
        self.assertTrue(all(len(theme["lecture"]) >= 5 for theme in HTML_THEMES))
        self.assertTrue(all(len(theme["terms"]) >= 8 for theme in HTML_THEMES))
        self.assertTrue(all(theme["video_file"].endswith(f"theme-{theme['number']:02d}.mp4") for theme in HTML_THEMES))

    def test_every_theme_has_twenty_questions(self):
        for theme in HTML_THEMES:
            questions = build_html_theme_quiz(theme["number"])
            self.assertEqual(len(questions), 20)
            self.assertTrue(all(len(question["options"]) == 4 for question in questions))

    def test_all_cut_video_files_are_present(self):
        for theme in HTML_THEMES:
            video = ROOT / "app" / "static" / theme["video_file"]
            self.assertTrue(video.is_file(), video)
            self.assertGreater(video.stat().st_size, 500_000, video)
            with video.open("rb") as stream:
                self.assertEqual(stream.read(8)[4:8], b"ftyp", video)

    def test_progress_tables_exist(self):
        connection = get_master_connection()
        try:
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()
        self.assertIn("html_course_progress", names)
        self.assertIn("html_final_results", names)

    def test_routes_templates_and_access_chain_include_html(self):
        learning = (ROOT / "app" / "learning.py").read_text(encoding="utf-8")
        hub = (ROOT / "app" / "templates" / "english_it_hub.html").read_text(encoding="utf-8")
        course = (ROOT / "app" / "templates" / "html_course.html").read_text(encoding="utf-8")
        theme = (ROOT / "app" / "templates" / "html_theme.html").read_text(encoding="utf-8")
        self.assertIn('@learning_bp.route("/study/html")', learning)
        self.assertIn('@learning_bp.route("/study/html/theme/<int:theme_number>"', learning)
        self.assertIn('"html": concepts_ready and python_ready and video_ready and topics_ready and interview_ready', learning)
        self.assertIn('"go": concepts_ready and python_ready and video_ready and topics_ready and interview_ready and html_ready', learning)
        self.assertIn("Семь направлений", hub)
        self.assertIn("последовательных тем", course)
        self.assertIn("Текстовая лекция", theme)
        self.assertIn("data-floating-video-player", theme)
        self.assertIn("20 вопросов", course)


if __name__ == "__main__":
    unittest.main()
