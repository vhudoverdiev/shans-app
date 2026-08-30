from pathlib import Path
import tempfile
import unittest

from config import Config
from app.database import get_master_connection
from app.learning import build_python_v2_topic_quiz, init_learning_db
from app.python_v2_topics_content import PYTHON_V2_TOPICS


ROOT = Path(__file__).resolve().parents[1]


class PythonV2TopicCourseTests(unittest.TestCase):
    def setUp(self):
        self.original_database_name = Config.DATABASE_NAME
        self.temp_directory = tempfile.TemporaryDirectory()
        Config.DATABASE_NAME = str(Path(self.temp_directory.name) / "python-v2-topics.db")
        init_learning_db()

    def tearDown(self):
        Config.DATABASE_NAME = self.original_database_name
        self.temp_directory.cleanup()

    def test_course_has_sixty_three_topics_and_no_video_exceeds_twenty_minutes(self):
        self.assertEqual(len(PYTHON_V2_TOPICS), 63)
        self.assertEqual([topic["number"] for topic in PYTHON_V2_TOPICS], list(range(1, 64)))
        self.assertTrue(all(0 < topic["duration_minutes"] <= 20 for topic in PYTHON_V2_TOPICS))
        self.assertTrue(all(len(topic["lecture"]) >= 5 for topic in PYTHON_V2_TOPICS))
        self.assertTrue(all(len(topic["terms"]) == 8 for topic in PYTHON_V2_TOPICS))

    def test_each_topic_has_twenty_valid_questions(self):
        for topic in PYTHON_V2_TOPICS:
            questions = build_python_v2_topic_quiz(topic["number"])
            self.assertEqual(len(questions), 20)
            self.assertTrue(all(len(question["options"]) == 4 for question in questions))
            self.assertTrue(all(question["correct_index"] in range(4) for question in questions))

    def test_every_cut_video_is_present_and_is_mp4(self):
        for topic in PYTHON_V2_TOPICS:
            path = ROOT / "app" / "static" / topic["video_file"]
            self.assertTrue(path.is_file(), path)
            self.assertGreater(path.stat().st_size, 500_000, path)
            with path.open("rb") as stream:
                self.assertEqual(stream.read(8)[4:8], b"ftyp", path)

    def test_progress_tables_exist(self):
        connection = get_master_connection()
        try:
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()
        self.assertIn("python_v2_topic_progress", names)
        self.assertIn("python_v2_topic_final_results", names)

    def test_routes_templates_and_access_sequence(self):
        learning = (ROOT / "app" / "learning.py").read_text(encoding="utf-8")
        catalog = (ROOT / "app/templates/python_v2_topics.html").read_text(encoding="utf-8")
        topic = (ROOT / "app/templates/python_v2_topic.html").read_text(encoding="utf-8")
        hub = (ROOT / "app/templates/english_it_hub.html").read_text(encoding="utf-8")
        self.assertIn('@learning_bp.route("/study/python-v2")', learning)
        self.assertIn('"python_topics": concepts_ready and python_ready and video_ready', learning)
        self.assertIn('"interview": concepts_ready and python_ready and video_ready and topics_ready', learning)
        self.assertIn("Семь направлений", hub)
        self.assertIn("Видео до 20 минут", catalog)
        for marker in ("data-floating-video-player", "Текстовая лекция", "Рабочий пример", "Перейти к тесту"):
            self.assertIn(marker, topic)


if __name__ == "__main__":
    unittest.main()
