import unittest
from app.database import get_master_connection
from app.access_control import ManagedUserForm, create_managed_user
from tests import test_learning_course as learning_fixtures


class LearningAccessTests(unittest.TestCase):
    setUp = learning_fixtures.EnglishLiveQuizRouteTests.setUp
    tearDown = learning_fixtures.EnglishLiveQuizRouteTests.tearDown
    _login_admin = learning_fixtures.EnglishLiveQuizRouteTests._login_admin

    def change(self, client, course, item, mode):
        return client.post('/study/access', data={
            'course': course, 'item': str(item), 'mode': mode, '_csrf_token': 'test-token'})

    def test_only_whole_courses_are_configurable_and_legacy_lesson_settings_are_ignored(self):
        client = self.app.test_client()
        self._login_admin(client)
        html = client.get('/study/access').get_data(as_text=True)
        self.assertEqual(html.count('class="lesson-section learning-access-row"'), 9)
        self.assertNotIn('name="item"', html)
        self.assertNotIn('Карта мира IT и язык вакансий', html)
        self.assertEqual(self.change(client, 'it', 10, 'open').status_code, 400)
        with client.session_transaction() as session:
            user_id = int(session['_user_id'])
        conn = get_master_connection()
        conn.executemany('INSERT INTO learning_access_overrides (user_id, course_key, item_number, is_open) VALUES (?, ?, ?, ?)',
                         [(user_id, 'it', 10, 1), (user_id, 'it', 1, 0)])
        conn.commit()
        conn.close()
        self.assertEqual(client.get('/study/it/day/10').status_code, 302)
        self.assertEqual(client.get('/study/it/day/1').status_code, 200)

    def test_all_directions_can_be_opened_without_unlocking_later_lessons(self):
        client = self.app.test_client()
        self._login_admin(client)
        routes = {
            'english': '/study/english', 'it': '/study/it', 'python': '/study/python',
            'video': '/study/it/videos', 'python_topics': '/study/python-v2',
            'interview': '/study/python/interview', 'html': '/study/html',
            'go': '/study/go', 'ai': '/study/ai',
        }
        for course, route in routes.items():
            with self.subTest(course=course):
                self.assertEqual(self.change(client, course, 0, 'open').status_code, 302)
                self.assertEqual(client.get(route).status_code, 200, route)
                self.change(client, course, 0, 'closed')
                self.assertEqual(client.get(route).status_code, 302)
                self.change(client, course, 0, 'open')
                self.assertEqual(client.get(route).status_code, 200)
        self.assertEqual(client.get('/study/python/day/3').status_code, 302)
        self.change(client, 'python', 0, 'auto')
        self.assertEqual(client.get('/study/python').status_code, 302)

    def test_users_control_only_their_own_access_and_csrf_is_required(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/study/access').status_code, 302)
        self._login_admin(client)
        self.assertEqual(client.post('/study/access', data={'course': 'it', 'item': '1', 'mode': 'open'}).status_code, 400)
        for course, item, mode in [('bad', 1, 'open'), ('it', -1, 'open'), ('it', 1000, 'open'), ('it', 'x', 'open'), ('it', 1, 'bad')]:
            self.assertIn(self.change(client, course, item, mode).status_code, (400, 404))
        self.change(client, 'it', 0, 'closed')
        with self.app.app_context():
            conn = get_master_connection()
            admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()['id']
            conn.close()
            user_id = create_managed_user(ManagedUserForm(username='access_other', password='TestPass-2026',
                                          display_name='Other', permissions={'study'}), created_by_user_id=admin_id)
        other = self.app.test_client()
        with other.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
            session['_csrf_token'] = 'test-token'
        self.assertEqual(other.get('/study/access').status_code, 200)
        self.assertEqual(self.change(other, 'it', 0, 'open').status_code, 302)
        self.assertEqual(other.get('/study/it/day/1').status_code, 200)
        self.assertIn('Доступ к обучению', other.get('/study').get_data(as_text=True))
        self.change(other, 'python', 0, 'open')
        self.assertEqual(other.get('/study/python').status_code, 200)
        self.assertEqual(client.get('/study/python').status_code, 302)
        self.assertEqual(other.post('/study/access', data={'course': 'it', 'item': '0', 'mode': 'open',
                              'user_id': str(admin_id), '_csrf_token': 'test-token'}).status_code, 302)
        self.assertEqual(client.get('/study/it/day/1').status_code, 302)

    def test_personal_access_does_not_grant_the_study_section_permission(self):
        with self.app.app_context():
            conn = get_master_connection()
            admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()['id']
            conn.close()
            user_id = create_managed_user(ManagedUserForm(username='access_limited', password='TestPass-2026',
                                          display_name='Limited', permissions={'schedule'}), created_by_user_id=admin_id)
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
            session['_csrf_token'] = 'test-token'
        response = client.get('/study/access')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/')
        self.assertEqual(self.change(client, 'it', 1, 'open').status_code, 403)

    def test_closing_completed_lesson_keeps_result_and_settings_survive_login(self):
        client = self.app.test_client()
        self._login_admin(client)
        with client.session_transaction() as session:
            user_id = int(session['_user_id'])
        conn = get_master_connection()
        conn.execute('INSERT INTO it_course_progress (user_id, day_number, best_score, attempts, passed) VALUES (?, 1, 20, 1, 1)', (user_id,))
        conn.commit()
        conn.close()
        self.change(client, 'it', 0, 'closed')
        another_session = self.app.test_client()
        self._login_admin(another_session)
        self.assertEqual(another_session.get('/study/it/day/1').status_code, 302)
        self.change(another_session, 'it', 0, 'auto')
        self.assertEqual(client.get('/study/it/day/1').status_code, 200)
        conn = get_master_connection()
        try:
            row = conn.execute('SELECT best_score, attempts, passed FROM it_course_progress WHERE user_id = ? AND day_number = 1', (user_id,)).fetchone()
            self.assertEqual((row['best_score'], row['attempts'], row['passed']), (20, 1, 1))
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
