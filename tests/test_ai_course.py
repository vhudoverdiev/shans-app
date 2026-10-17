import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import create_app
from app.database import get_master_connection
from app.ai_course_content import AI_LESSONS, AI_SOURCE_DURATION, AI_PASS_SCORE
from app.learning import shuffle_quiz, _get_course_state
from app.access_control import ManagedUserForm, create_managed_user
from config import Config


class AiCourseTests(unittest.TestCase):
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
        self.app.config.update(TESTING=True, USER_DATABASE_DIR=str(Path(self.temp_directory.name) / "user_databases"))

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

    def _login_admin(self, client):
        conn = get_master_connection()
        try:
            user_id = int(conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()["id"])
        finally:
            conn.close()
        with client.session_transaction() as browser_session:
            browser_session["_user_id"] = str(user_id)
            browser_session["_fresh"] = True
            browser_session["_csrf_token"] = "test-token"

    def _answer(self, client, day, correct=True):
        client.get(f'/study/ai/lesson/{day}?retry=1')
        with client.session_transaction() as state:
            attempt = state['ai_quiz_attempts'][str(day)]
        questions = shuffle_quiz(list(AI_LESSONS[day - 1]['quiz']), attempt['seed'])
        form = {'_csrf_token': 'test-token', 'quiz_nonce': attempt['nonce']}
        form.update({f'question_{i}': str(q['correct_index'] if correct else (q['correct_index'] + 1) % 3)
                     for i, q in enumerate(questions)})
        return client.post(f'/study/ai/lesson/{day}', data=form), form

    def test_content_covers_source_contiguously_and_questions_are_valid(self):
        self.assertEqual(len(AI_LESSONS), 17)
        self.assertEqual(AI_LESSONS[0]['start'], 0)
        self.assertEqual(AI_LESSONS[-1]['end'], AI_SOURCE_DURATION)
        for index, lesson in enumerate(AI_LESSONS):
            self.assertEqual(lesson['day'], index + 1)
            self.assertGreater(lesson['end'], lesson['start'])
            self.assertTrue(lesson['practice'])
            self.assertEqual(len(lesson['quiz']), AI_PASS_SCORE)
            self.assertTrue(lesson['lecture'])
            if index:
                self.assertEqual(AI_LESSONS[index - 1]['end'], lesson['start'])
            for question in lesson['quiz']:
                self.assertEqual(len(set(question['options'])), 3)
                self.assertTrue(question['explanation'])
                self.assertTrue(0 <= question['correct_index'] < 3)

    def test_all_lessons_can_be_completed_and_refresh_does_not_resave(self):
        client = self.app.test_client()
        self._login_admin(client)
        for day in range(1, 18):
            with self.subTest(day=day):
                response, form = self._answer(client, day)
                self.assertEqual(response.status_code, 302)
                page = client.get(response.headers['Location'])
                self.assertEqual(page.status_code, 200)
                self.assertIn('Урок пройден', page.get_data(as_text=True))
                self.assertEqual(client.get(response.headers['Location']).status_code, 200)
                self.assertEqual(client.post(f'/study/ai/lesson/{day}', data=form).status_code, 400)
        html = client.get('/study/ai').get_data(as_text=True)
        self.assertIn('17 из 17', html)
        self.assertNotIn('Завершите предыдущий урок', html)

    def test_locked_failed_and_invalid_lessons(self):
        client = self.app.test_client()
        self._login_admin(client)
        self.assertEqual(client.get('/study/ai/lesson/2').status_code, 302)
        response, _form = self._answer(client, 1, correct=False)
        html = client.get(response.headers['Location']).get_data(as_text=True)
        self.assertIn('Повторите материал', html)
        self.assertEqual(client.get('/study/ai/lesson/2').status_code, 302)
        for day in (0, 18, 1000):
            self.assertEqual(client.get(f'/study/ai/lesson/{day}').status_code, 404)

    def test_csrf_nonce_validation_and_no_answer_leak(self):
        client = self.app.test_client()
        self._login_admin(client)
        html = client.get('/study/ai/lesson/1').get_data(as_text=True)
        self.assertNotIn('correct_index', html)
        self.assertNotIn('Правильный ответ:', html)
        self.assertEqual(client.post('/study/ai/lesson/1', data={}).status_code, 400)
        self.assertEqual(client.post('/study/ai/lesson/1', data={'_csrf_token': 'test-token', 'quiz_nonce': 'forged'}).status_code, 400)
        with client.session_transaction() as state:
            nonce = state['ai_quiz_attempts']['1']['nonce']
        response = client.post('/study/ai/lesson/1', data={'_csrf_token': 'test-token', 'quiz_nonce': nonce,
                                                        'question_0': '999', 'question_1': '0', 'question_2': '0'})
        self.assertEqual(response.status_code, 400)

    def test_login_and_section_permissions(self):
        client = self.app.test_client()
        self.assertIn('/login', client.get('/study/ai').headers['Location'])
        with self.app.app_context():
            conn = get_master_connection()
            admin = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']
            conn.close()
            user = create_managed_user(ManagedUserForm(username='ai_limited', password='TestPass-2026',
                                       display_name='Limited', permissions={'schedule'}), created_by_user_id=admin)
        with client.session_transaction() as state:
            state['_user_id'] = str(user)
            state['_fresh'] = True
        for path in ('/study/ai', '/study/ai/lesson/1'):
            response = client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers['Location'], '/')
