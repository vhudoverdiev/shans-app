import unittest
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from unittest.mock import patch

from tests import test_learning_course as fixtures
from app.shooting_contracts import PACKAGES, TEMPLATE, build_contract, default_values, validate_values
from app.database import get_master_connection
from app.access_control import ManagedUserForm, create_managed_user
from app.models import create_shooting


def valid_form(kind='photo'):
    values = default_values()
    values.update(city='Северодвинск', contract_date='2026-11-20', client_name='Иванова Анна Сергеевна',
                  phone='+7 900 123-45-67', vk='https://vk.com/example', shooting_date='2026-12-01',
                  start_time='12:00', end_time='13:00', location='Северодвинск, парк',
                  photo_size='от 3000 px по длинной стороне', photo_edits='3 кадра: цвет и кадрирование',
                  kind=kind, video_count='1', video_duration='3–5 минут',
                  video_format='MP4, 1920×1080, горизонтальная', video_edits='3 локальных изменения монтажа')
    return values


class ContractGeneratorTests(unittest.TestCase):
    setUp = fixtures.EnglishLiveQuizRouteTests.setUp
    tearDown = fixtures.EnglishLiveQuizRouteTests.tearDown
    _login_admin = fixtures.EnglishLiveQuizRouteTests._login_admin

    def test_docx_preserves_package_and_removes_stamp(self):
        for kind in ('photo', 'video', 'both'):
            with self.subTest(kind=kind):
                values, errors = validate_values(valid_form(kind))
                self.assertEqual(errors, [])
                with ZipFile(build_contract(values)) as output, ZipFile(TEMPLATE) as template:
                    self.assertEqual(output.testzip(), None)
                    self.assertEqual(output.namelist(), template.namelist())
                    for name in template.namelist():
                        if name != 'word/document.xml': self.assertEqual(output.read(name), template.read(name), name)
                    self.assertNotIn('word/media/image1.png', output.namelist())
                    self.assertNotIn('word/media/hdphoto1.wdp', output.namelist())
                    self.assertIn('word/media/image2.png', output.namelist())
                    xml = output.read('word/document.xml')
                    text = ''.join(ET.fromstring(xml).itertext())
                    for value in ('Иванова Анна Сергеевна', '20.11.2026', '01.12.2026', '6 000', 'Худовердиев Владимир Сергеевич', '12.5.'):
                        self.assertIn(value, text)
                    self.assertNotIn('[', text)
                    self.assertNotIn('rId11', xml.decode())
                    self.assertIn('Результат фото за весь заказ: не входит.', text) if kind == 'video' else None
                    self.assertIn('Результат видео: не входит.', text) if kind == 'photo' else None
                    source = ET.fromstring(template.read('word/document.xml'))
                    final = ET.fromstring(xml)
                    drawing_ns = {'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
                    signature = final.find('.//wp:anchor', drawing_ns)
                    self.assertEqual(signature.find('wp:positionH/wp:posOffset', drawing_ns).text, '379258')
                    self.assertEqual(signature.find('wp:positionV/wp:posOffset', drawing_ns).text, '228600')
                    ns = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    self.assertEqual(ET.tostring(source.find('.//w:sectPr', ns)), ET.tostring(final.find('.//w:sectPr', ns)))
                    for index in (4, 6, 8, 15, 16, 30, 50, 68, 90, 98):
                        self.assertEqual(ET.tostring(source.findall('.//w:p', ns)[index]), ET.tostring(final.findall('.//w:p', ns)[index]))

    def test_studio_prices_exclude_2500_and_validation_rejects_invalid_orders(self):
        studio = {p['id']:p for p in PACKAGES if p.get('studio')}
        self.assertEqual({k:v['price'] for k,v in studio.items()}, {'studio':6000,'full-look':12500,'gift':5000})
        for package in studio.values(): self.assertEqual(package['public_price'] - package['price'], 2500)
        for changes in ({'price':'NaN'}, {'price':'999'}, {'hours':'Infinity'}, {'end_time':'15:00'},
                        {'photo_size':''}, {'kind':'video','video_duration':''}, {'retouch_count':'100'},
                        {'license':'commercial','commercial_use':'не применимо'}, {'client_name':'a'*241},
                        {'studio':'included'}, {'shooting_date':'2026-01-01'}, {'phone':'\x01'}):
            with self.subTest(changes=changes):
                self.assertTrue(validate_values({**valid_form(), **changes})[1])
        night = {**valid_form(), 'start_time':'23:00','end_time':'01:00','hours':'2'}
        self.assertFalse(validate_values(night)[1])

    def test_route_requires_login_csrf_and_returns_private_docx(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/shootings/contracts').status_code, 302)
        self._login_admin(client)
        self.assertIn('Генерация договора на съёмку', client.get('/shootings-hub').get_data(as_text=True))
        self.assertEqual(client.post('/shootings/contracts', data=valid_form()).status_code, 400)
        response = client.post('/shootings/contracts', data={**valid_form(), '_csrf_token':'test-token'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertTrue(response.data.startswith(b'PK'))
        response.close()
        bad = client.post('/shootings/contracts', data={**valid_form(), 'video_count':'', 'kind':'video', '_csrf_token':'test-token'})
        self.assertIn('Укажите количество', bad.get_data(as_text=True))
        self.assertIn('Иванова Анна', bad.get_data(as_text=True))
        with client.session_transaction() as session:
            self.assertNotIn('client_name', session)

    def test_booking_prefill_and_user_isolation(self):
        client = self.app.test_client()
        self._login_admin(client)
        with self.app.app_context():
            shooting_id = create_shooting('Прогулочная', 'Секретный клиент', '2026-12-01', '12:00', 1, '+79001234567', 6000, 1000, '')
            conn = get_master_connection()
            admin_id = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']
            conn.close()
            other_id = create_managed_user(ManagedUserForm(username='contract_other', display_name='Other', password='TestPass-2026', permissions={'shootings'}), created_by_user_id=admin_id)
            limited_id = create_managed_user(ManagedUserForm(username='contract_limited', display_name='Limited', password='TestPass-2026', permissions={'study'}), created_by_user_id=admin_id)
        html = client.get(f'/shootings/contracts?shooting_id={shooting_id}').get_data(as_text=True)
        self.assertIn('Секретный клиент', html)
        self.assertIn('value="13:00"', html)
        self.assertEqual(client.get('/shootings/contracts?shooting_id=oops').status_code, 400)
        for user_id in (other_id, limited_id):
            other = self.app.test_client()
            with other.session_transaction() as session:
                session['_user_id'] = str(user_id); session['_fresh'] = True; session['_csrf_token'] = 'test-token'
            response = other.get(f'/shootings/contracts?shooting_id={shooting_id}')
            self.assertEqual(response.status_code, 404 if user_id == other_id else 302)
            if user_id == limited_id:
                self.assertEqual(other.post('/shootings/contracts', data={**valid_form(),'_csrf_token':'test-token'}).status_code, 403)
            else:
                self.assertNotIn('Секретный клиент', other.get('/shootings/contracts').get_data(as_text=True))

    def test_template_escapes_client_xml(self):
        values, errors = validate_values({**valid_form(), 'client_name':'Анна & <Клиент>'})
        self.assertFalse(errors)
        with ZipFile(build_contract(values)) as output:
            self.assertIn('Анна & <Клиент>', ''.join(ET.fromstring(output.read('word/document.xml')).itertext()))

    def test_return_navigation_and_clean_form_labels(self):
        client = self.app.test_client()
        self._login_admin(client)
        for path in ('/shootings/upcoming', '/shootings/archive', '/shootings/add', '/shootings/12'):
            html = client.get('/shootings/contracts', query_string={'return_to':path}).get_data(as_text=True)
            self.assertIn(f'class="contract-back" href="{path}"', html)
            self.assertIn(f'name="return_to" value="{path}"', html)
        for path in ('https://example.com', '//example.com', '/account/settings', '/\\example.com', 'http://[bad'):
            html = client.get('/shootings/contracts', query_string={'return_to':path}).get_data(as_text=True)
            self.assertIn('class="contract-back" href="/shootings"', html)
        response = client.post('/shootings/contracts', data={'_csrf_token':'test-token', 'return_to':'/shootings/archive'})
        self.assertIn('class="contract-back" href="/shootings/archive"', response.get_data(as_text=True))
        html = client.get('/shootings/contracts').get_data(as_text=True)
        for text in ('Заполните заказ — скачайте', 'Подпись исполнителя и остальные условия', 'Введите данные клиента.', 'Перед подписанием проверьте', 'DOCX', '<span>Печать</span>'):
            self.assertNotIn(text, html)
        for text in ('Фотосъёмка', 'Видеосъёмка', 'Фото и видео', 'Личная', 'Предпринимательская'):
            self.assertIn(text, html)


if __name__ == '__main__': unittest.main()
