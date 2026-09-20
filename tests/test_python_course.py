import tempfile
import unittest
from pathlib import Path

from config import Config
from app.database import get_master_connection
from app.learning import (
    PYTHON_LESSONS,
    _base_quiz_for_attempt,
    build_python_interview_quiz,
    build_python_daily_quiz,
    build_python_final_quiz,
    init_learning_db,
)
from app.python_course_content import PYTHON_INTERVIEW_SECTIONS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIRECTORY = PROJECT_ROOT / "app" / "templates"
VIDEOS_DIRECTORY = PROJECT_ROOT / "app" / "static" / "videos"
PRESENTATIONS_DIRECTORY = PROJECT_ROOT / "app" / "static" / "presentations"


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
            self.assertEqual(
                lesson["presentation_file"],
                f"presentations/python-basics/python_day{lesson['day']:02d}_simple_readable.pdf",
            )
            self.assertEqual(lesson["cheatsheet_file"], "cheatsheets/python-basics/python_cheatsheet_days_01_30.pdf")
            self.assertEqual(lesson["cheatsheet_page"], lesson["day"])
            self.assertTrue(lesson["code"])
            self.assertTrue(lesson["project"]["title"])
            self.assertTrue(lesson["project"]["file_name"])
            self.assertGreaterEqual(len(lesson["project"]["steps"]), 5)
            self.assertTrue(lesson["project"]["result"])

    def test_practice_card_keeps_space_below_test_button(self):
        styles = (PROJECT_ROOT / "app" / "static" / "css" / "learning.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("padding: 24px 26px 38px 98px;", styles)
        self.assertIn("padding: 19px 19px 30px;", styles)

    def test_it_courses_are_sequential_and_interview_test_is_separate(self):
        learning = (PROJECT_ROOT / "app" / "learning.py").read_text(encoding="utf-8")
        hub = (TEMPLATES_DIRECTORY / "english_it_hub.html").read_text(encoding="utf-8")
        section = (TEMPLATES_DIRECTORY / "python_interview_section.html").read_text(encoding="utf-8")
        self.assertIn("def _it_course_access", learning)
        self.assertIn("percent >= 80", learning)
        self.assertIn('"it": True', learning)
        self.assertIn("block.locked", hub)
        self.assertIn("предыдущего курса минимум на 80%", hub)
        self.assertIn("learning.python_interview_test", section)
        self.assertNotIn("data-interview-test-toggle", section)

    def test_every_day_has_fifteen_valid_questions_with_code_practice(self):
        for day in range(1, 31):
            questions = build_python_daily_quiz(day)
            self.assertEqual(len(questions), 15)
            practical_questions = [
                question for question in questions
                if "код" in question["prompt"].lower() or "мини-проект" in question["prompt"].lower()
            ]
            self.assertGreaterEqual(len(practical_questions), 5)
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
        self.assertIn("python_interview_progress", names)

    def test_interview_section_covers_all_required_tracks(self):
        titles = " ".join(section[0] for section in PYTHON_INTERVIEW_SECTIONS).lower()
        for required in ("python", "django", "ооп", "алгоритм", "баз", "систем", "soft"):
            self.assertIn(required, titles)
        self.assertGreaterEqual(
            sum(len(section[1]) for section in PYTHON_INTERVIEW_SECTIONS),
            45,
        )

    def test_all_new_course_lecture_videos_are_present_and_valid_mp4_files(self):
        for directory_name in ("english-lectures", "it-lectures", "python-lectures"):
            directory = VIDEOS_DIRECTORY / directory_name
            files = sorted(directory.glob("lesson-*.mp4"))

            self.assertEqual(
                [path.name for path in files],
                [f"lesson-{day:02d}.mp4" for day in range(1, 31)],
            )
            for path in files:
                self.assertGreater(path.stat().st_size, 1024, path)
                with path.open("rb") as video:
                    self.assertEqual(video.read(8)[4:8], b"ftyp", path)

    def test_python_video_lecture_has_test_link_and_floating_player_controls(self):
        source = (TEMPLATES_DIRECTORY / "python_video_lecture.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("data-floating-video-player", source)
        self.assertIn("data-video-expand", source)
        self.assertIn("data-video-close", source)
        self.assertIn("js/floating-video-player.js", source)
        self.assertIn("learning.python_day_test", source)

    def test_python_daily_presentations_are_available_and_embedded(self):
        files = sorted((PRESENTATIONS_DIRECTORY / "python-basics").glob("python_day*_simple_readable.pdf"))
        self.assertEqual(
            [path.name for path in files],
            [f"python_day{day:02d}_simple_readable.pdf" for day in range(1, 31)],
        )
        for path in files:
            self.assertGreater(path.stat().st_size, 100 * 1024, path)
            with path.open("rb") as presentation:
                self.assertEqual(presentation.read(5), b"%PDF-", path)

        source = (TEMPLATES_DIRECTORY / "python_day.html").read_text(encoding="utf-8")
        self.assertIn("Смотреть презентацию", source)
        self.assertIn("data-presentation-viewer", source)
        self.assertIn("lesson.presentation_file", source)
        self.assertIn("js/presentation-viewer.js", source)

    def test_python_cheatsheet_is_available_per_day(self):
        path = PRESENTATIONS_DIRECTORY.parent / "cheatsheets" / "python-basics" / "python_cheatsheet_days_01_30.pdf"
        self.assertTrue(path.is_file(), path)
        self.assertGreater(path.stat().st_size, 100 * 1024, path)
        with path.open("rb") as cheatsheet:
            self.assertEqual(cheatsheet.read(5), b"%PDF-", path)

        source = (TEMPLATES_DIRECTORY / "python_day.html").read_text(encoding="utf-8")
        self.assertIn("Смотреть шпаргалку", source)
        self.assertIn("lesson.cheatsheet_file", source)
        self.assertIn("#page={{ lesson.cheatsheet_page }}", source)

    def test_separate_daily_lecture_tabs_are_removed_from_course_navigation(self):
        templates = {
            name: (TEMPLATES_DIRECTORY / name).read_text(encoding="utf-8")
            for name in ("english_course.html", "it_course.html", "python_course.html")
        }

        self.assertNotIn("learning.english_video_lectures", templates["english_course.html"])
        self.assertNotIn("learning.it_video_lectures", templates["it_course.html"])
        self.assertNotIn("learning.python_video_lectures", templates["python_course.html"])
        basics_hub = (TEMPLATES_DIRECTORY / "english_it_hub.html").read_text(encoding="utf-8")
        self.assertIn("url_for(block.endpoint)", basics_hub)
        self.assertIn("Python v3", (PROJECT_ROOT / "app" / "learning.py").read_text(encoding="utf-8"))
        self.assertIn("role=\"progressbar\"", basics_hub)
        self.assertIn("Python v1", templates["python_course.html"])
        self.assertNotIn("Курс по дням", templates["english_course.html"])
        self.assertNotIn("Курс по дням", templates["it_course.html"])
        self.assertNotIn("learning-course-tabs", templates["it_course.html"])

        video_hub = (TEMPLATES_DIRECTORY / "it_video_course.html").read_text(encoding="utf-8")
        self.assertNotIn("learning-course-tabs", video_hub)

        learning_source = (PROJECT_ROOT / "app" / "learning.py").read_text(encoding="utf-8")
        for title in ('"title": "Python v1"', '"title": "Понятия (Для новичка)"', '"title": "Python v3"', '"title": "Собеседования (Python)"'):
            self.assertIn(title, learning_source)

        self.assertNotIn("learning-course-tabs", templates["python_course.html"])
        self.assertNotIn("Курс по дням", templates["python_course.html"])
        interview_hub = (TEMPLATES_DIRECTORY / "python_interview.html").read_text(encoding="utf-8")
        self.assertNotIn("learning-course-tabs", interview_hub)
        self.assertNotIn("Курс по дням", interview_hub)
        self.assertIn("Семь направлений", basics_hub)

    def test_daily_lessons_have_topic_posters_and_video_controls(self):
        for template_name in ("english_day.html", "it_day.html", "python_day.html"):
            source = (TEMPLATES_DIRECTORY / template_name).read_text(encoding="utf-8")
            self.assertIn("data-video-anchor", source, template_name)
            self.assertIn("data-video-poster", source, template_name)
            self.assertIn("data-video-play", source, template_name)
            self.assertIn("{{ lesson.title }}", source, template_name)
            self.assertIn("data-video-expand", source, template_name)
            self.assertIn("data-video-close", source, template_name)
            self.assertIn("interview-video-section", source, template_name)
            self.assertNotIn("video-player-section", source, template_name)
            self.assertNotIn("Видеолекция дня", source, template_name)

    def test_interview_is_split_into_sequential_blocks_with_valid_quizzes_and_videos(self):
        for section_number in range(1, len(PYTHON_INTERVIEW_SECTIONS) + 1):
            quiz = build_python_interview_quiz(section_number, 20260830)
            self.assertEqual(len(quiz), len(PYTHON_INTERVIEW_SECTIONS[section_number - 1][1]))
            video_path = VIDEOS_DIRECTORY / "python-interview" / f"block-{section_number:02d}.mp4"
            self.assertTrue(video_path.is_file(), video_path)
            self.assertGreater(video_path.stat().st_size, 1024 * 1024, video_path)
            with video_path.open("rb") as video:
                self.assertEqual(video.read(8)[4:8], b"ftyp", video_path)
            for question in quiz:
                self.assertEqual(len(question["options"]), 4)
                self.assertGreaterEqual(question["correct_index"], 0)
                self.assertLess(question["correct_index"], 4)

        catalog = (TEMPLATES_DIRECTORY / "python_interview.html").read_text(encoding="utf-8")
        section = (TEMPLATES_DIRECTORY / "python_interview_section.html").read_text(encoding="utf-8")
        self.assertIn("learning.python_interview_section", catalog)
        self.assertIn("data-video-poster", section)
        self.assertIn("Ответы на все вопросы блока", section)
        self.assertIn("interview_questions|length }} ответов", section)
        self.assertIn("Проверка блока", section)
        self.assertIn("learning.python_interview_test", section)
        self.assertIn("{% if not test_page %}", section)
        self.assertNotIn("data-interview-test-toggle", section)
        styles = (PROJECT_ROOT / "app" / "static" / "css" / "learning.css").read_text(encoding="utf-8")
        self.assertNotIn("Видеолекция блока", section)
        self.assertNotIn("Посмотрите перед разбором", section)
        self.assertIn('class="interview-video-section"', section)
        self.assertIn(".study-progress-card .study-block-progress", styles)
        self.assertIn("margin-bottom: 24px", styles)
        self.assertIn("box-shadow: inset 0 0 0 2px #2563eb", styles)
        self.assertIn("box-shadow: inset 0 0 0 2px #7c3aed", styles)
        self.assertIn(
            'videos/python-interview/block-{section_number:02d}.mp4',
            (PROJECT_ROOT / "app" / "learning.py").read_text(encoding="utf-8"),
        )

    def test_it_hub_mobile_icons_and_lock_footer_do_not_overlap_progress(self):
        hub = (TEMPLATES_DIRECTORY / "english_it_hub.html").read_text(encoding="utf-8")
        styles = (PROJECT_ROOT / "app" / "static" / "css" / "learning.css").read_text(encoding="utf-8")

        self.assertIn('class="study-course-lock-footer"', hub)
        self.assertIn('class="study-course-lock-icon"', hub)
        self.assertNotIn('{% if block.locked %}🔒{% else %}→{% endif %}', hub)
        self.assertIn(".study-course-lock-footer {", styles)
        self.assertIn(".study-direction-grid .study-card-icon-it {\n        font-size: 14px;", styles)


if __name__ == "__main__":
    unittest.main()
