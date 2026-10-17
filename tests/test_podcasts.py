import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.database import get_master_connection
from app.access_control import ManagedUserForm, create_managed_user
from config import Config


class PodcastTests(unittest.TestCase):
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

    def _catalog(self):
        media_root = Path(self.temp_directory.name) / "podcasts"
        media_root.mkdir(exist_ok=True)
        with wave.open(str(media_root / "sample.wav"), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b"\0\0" * 8000)
        entries = ({"slug": "sample", "category": "it", "title": "Первый подкаст",
                    "description": "Кратко о технологиях.", "filename": "sample.wav"},)
        self.enterContext(patch("app.learning.PODCASTS", entries))
        self.enterContext(patch("app.learning._podcast_media_root", return_value=media_root))
        return media_root, entries[0]

    @patch("app.learning.PODCASTS", ())
    def test_hub_and_empty_categories(self):
        client = self.app.test_client()
        self._login_admin(client)
        self.assertIn('/study/podcasts', client.get('/study').get_data(as_text=True))
        response = client.get('/study/podcasts')
        self.assertEqual(response.status_code, 200)
        for category in ('it', 'self-development', 'english'):
            self.assertIn('/study/podcasts/' + category, response.get_data(as_text=True))
            page = client.get('/study/podcasts/' + category)
            self.assertEqual(page.status_code, 200)
            self.assertIn('Здесь скоро появятся подкасты', page.get_data(as_text=True))
        self.assertEqual(client.get('/study/podcasts/unknown').status_code, 404)

    def test_detail_player_download_and_range(self):
        self._catalog()
        client = self.app.test_client()
        self._login_admin(client)
        base = '/study/podcasts/it/sample'
        listing = client.get('/study/podcasts/it').get_data(as_text=True)
        self.assertIn(base, listing)
        self.assertIn('Первый подкаст', listing)
        detail = client.get(base).get_data(as_text=True)
        self.assertIn('Кратко о технологиях.', detail)
        self.assertIn('Прослушать', detail)
        self.assertIn('Скачать подкаст', detail)
        self.assertIn('controls preload="none"', detail)
        self.assertNotIn('autoplay', detail)
        for suffix, disposition in (('audio', 'inline'), ('download', 'attachment')):
            response = client.get(base + '/' + suffix)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data.startswith(b'RIFF'))
            self.assertIn(disposition, response.headers['Content-Disposition'])
            response.close()
        response = client.get(base + '/audio', headers={'Range': 'bytes=0-9'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(len(response.data), 10)
        self.assertIn('bytes 0-9/', response.headers['Content-Range'])
        response.close()
        self.assertEqual(client.get('/study/podcasts/self-development/sample').status_code, 404)
        self.assertEqual(client.get('/study/podcasts/it/missing').status_code, 404)

    def test_listened_mark_persists_and_can_be_removed(self):
        self._catalog()
        client = self.app.test_client()
        self._login_admin(client)
        base = '/study/podcasts/it/sample'
        self.assertNotIn('✓ Прослушал', client.get(base).get_data(as_text=True))
        self.assertEqual(client.post(base, data={'listened': '1'}).status_code, 400)
        for _ in range(2):
            response = client.post(base, data={'listened': '1', '_csrf_token': 'test-token'})
            self.assertEqual(response.status_code, 302)
        detail = client.get(base).get_data(as_text=True)
        self.assertIn('class="btn btn-danger"', detail)
        self.assertIn('>Снять отметку</button>', detail)
        self.assertNotIn('Отметить:', detail)
        self.assertIn('✓ Прослушал', client.get('/study/podcasts/it').get_data(as_text=True))
        fresh_client = self.app.test_client()
        self._login_admin(fresh_client)
        self.assertIn('>Снять отметку</button>', fresh_client.get(base).get_data(as_text=True))
        self.assertEqual(client.post(base, data={'listened': 'bad', '_csrf_token': 'test-token'}).status_code, 400)
        self.assertEqual(client.post('/study/podcasts/it/missing', data={'listened': '1', '_csrf_token': 'test-token'}).status_code, 404)
        client.post(base, data={'listened': '0', '_csrf_token': 'test-token'})
        for path in (base, '/study/podcasts/it'):
            self.assertNotIn('✓ Прослушал', client.get(path).get_data(as_text=True))
        self.assertIn('>Прослушал</button>', client.get(base).get_data(as_text=True))

    def test_series_navigation_stays_in_the_same_recording(self):
        _root, first = self._catalog()
        first.update(series='Серия', part=1, source_id='abcdefghijk')
        second = {**first, 'slug': 'part-two', 'part': 2}
        unrelated = {**first, 'slug': 'unrelated', 'part': 3, 'source_id': 'other-video'}
        client = self.app.test_client()
        self._login_admin(client)
        with patch('app.learning.PODCASTS', (first, second, unrelated)):
            html = client.get('/study/podcasts/it/sample').get_data(as_text=True)
            self.assertIn('/study/podcasts/it/part-two', html)
            self.assertNotIn('/study/podcasts/it/unrelated', html)
            self.assertNotIn('Исходный ролик', html)
            self.assertNotIn('youtube.com/watch', html)
            html = client.get('/study/podcasts/it/part-two').get_data(as_text=True)
            self.assertIn('/study/podcasts/it/sample', html)
            self.assertNotIn('Часть 3', html)

    def test_missing_unsafe_and_unsupported_files(self):
        root, entry = self._catalog()
        client = self.app.test_client()
        self._login_admin(client)
        for filename in ('missing.mp3', '../outside.wav', '/etc/passwd', 'note.txt'):
            with self.subTest(filename=filename):
                entry['filename'] = filename
                detail = client.get('/study/podcasts/it/sample').get_data(as_text=True)
                self.assertIn('Аудиозапись пока недоступна', detail)
                self.assertNotIn('<audio', detail)
                self.assertEqual(client.get('/study/podcasts/it/sample/audio').status_code, 404)
                self.assertEqual(client.get('/study/podcasts/it/sample/download').status_code, 404)

    def test_podcast_layout_uses_consistent_spacing_and_responsive_theme(self):
        styles = (Path(__file__).resolve().parents[1] / 'app/static/css/learning.css').read_text()
        podcast_styles = styles.split('/* Podcast pages use one spacing rhythm', 1)[1]
        desktop, mobile = podcast_styles.split('@media (max-width: 900px) and (pointer: coarse)', 1)
        self.assertIn('--podcast-accent: #2563eb;', desktop)
        self.assertIn('--podcast-accent: #6d28d9;', mobile)
        self.assertNotIn('#6d28d9', desktop)
        for selector in ('.podcast-page .lesson-section', '.podcast-heading', '.podcast-category-card,'):
            self.assertIn(selector, desktop)
        self.assertIn('gap: 18px;', desktop)
        self.assertIn('gap: 24px;', desktop)
        self.assertIn('padding: 24px;', mobile)
        self.assertIn('outline: 3px solid var(--podcast-accent);', desktop)
        self.assertIn('.podcast-status:empty', desktop)
        for template in ('podcasts.html', 'podcast_category.html'):
            source = (Path(__file__).resolve().parents[1] / 'app/templates' / template).read_text()
            self.assertLess(source.index('podcast-intro'), source.index('</div>'))

    def test_all_routes_require_login(self):
        self._catalog()
        client = self.app.test_client()
        for path in ('', '/it', '/it/sample', '/it/sample/audio', '/it/sample/download'):
            response = client.get('/study/podcasts' + path)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login', response.headers['Location'])

    def test_all_routes_require_study_permission(self):
        self._catalog()
        with self.app.app_context():
            conn = get_master_connection()
            admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()['id']
            conn.close()
            user_id = create_managed_user(ManagedUserForm(username='podcast_limited', password='TestPass-2026',
                                          display_name='Limited', permissions={'schedule'}),
                                          created_by_user_id=admin_id)
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        for path in ('', '/it', '/it/sample', '/it/sample/audio', '/it/sample/download'):
            response = client.get('/study/podcasts' + path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/")


if __name__ == '__main__':
    unittest.main()
