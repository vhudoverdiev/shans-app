"""Private DOCX generation from the supplied contract, without rewriting its layout."""
from copy import copy
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZipFile
from urllib.parse import urlsplit

from flask import Blueprint, abort, make_response, render_template, request, send_file
from flask_login import login_required

from app.database import get_connection
from app.models import get_shooting_by_id

contracts_bp = Blueprint('contracts', __name__)
TEMPLATE = Path(__file__).parent / 'document_templates' / 'shooting_contract.docx'
PRICE_SOURCE = 'https://ph.khudoverdiev.ru/'
PRICE_CHECKED = '19.11.2026'
# A snapshot of the public price list; changes to a booking remain editable.
PACKAGES = (
    dict(id='wedding-photo', title='Свадебная история', kind='photo', price=6000, hourly=5000, photos=60, retouch=5, hours=1),
    dict(id='studio', title='Студийная съёмка', kind='photo', price=6000, public_price=8500, photos=60, retouch=5, hours=1, studio=True),
    dict(id='walk', title='Прогулочная', kind='photo', price=6000, photos=60, retouch=3, hours=1),
    dict(id='full-look', title='Полный образ', kind='photo', price=12500, public_price=15000, photos=60, retouch=5, hours=1, studio=True, extras='Укладка, макияж и аренда платья.'),
    dict(id='photo-video', title='Два формата', kind='both', price=8000),
    dict(id='gift', title='Съёмка в подарок', kind='photo', price=5000, public_price=7500, photos=60, retouch=5, hours=1, studio=True, from_price=True, extras='Сертификат в подарочном конверте.'),
    dict(id='wedding-video', title='Свадебный фильм', kind='video', price=6000, hourly=5000),
    dict(id='episode', title='Главный эпизод', kind='video', price=6000, hourly=5000),
    dict(id='creative', title='Творческий ролик', kind='video', price=6000, hourly=5000),
    dict(id='brand', title='Контент для бренда', kind='video', hourly=6000, from_price=True),
    dict(id='custom', title='Индивидуальная съёмка', kind='both'),
)
KINDS = {'photo': 'фотосъёмка', 'video': 'видеосъёмка', 'both': 'фото и видео'}
FIELDS = {
    'city': ('Город заключения', 100), 'contract_date': ('Дата договора', 10),
    'client_name': ('ФИО или наименование заказчика', 240), 'representative': ('Представитель и основание полномочий', 300),
    'phone': ('Телефон клиента', 80), 'vk': ('Аккаунт ВКонтакте клиента', 200),
    'package': ('Пакет', 40), 'kind': ('Вид съёмки', 10), 'subject': ('Пакет или сюжет', 240),
    'shooting_date': ('Дата съёмки', 10), 'start_time': ('Начало съёмки', 5), 'end_time': ('Окончание съёмки', 5),
    'hours': ('Продолжительность', 12), 'location': ('Адрес или локация', 400), 'price': ('Цена услуг', 20),
    'delivery_days': ('Срок готовности, календарных дней', 3),
    'photo_count': ('Минимум фотографий за заказ', 6), 'retouch_count': ('Детальная ретушь', 6),
    'photo_format': ('Формат фото', 160), 'retouch_selector': ('Кто выбирает ретушь', 200),
    'video_count': ('Количество роликов', 6), 'video_duration': ('Длительность готового видео', 160), 'video_format': ('Параметры видео', 240),
    'video_extras': ('Дополнительные версии и запись речи', 300), 'photo_edits': ('Корректировки фото', 300), 'video_edits': ('Корректировки видео', 300),
    'studio': ('Аренда студии', 20), 'studio_details': ('Студия и время брони', 300),
    'license': ('Лицензия', 20), 'commercial_use': ('Коммерческое использование', 500),
    'wishes': ('Особые пожелания и услуги', 600), 'purpose': ('Цель заказа', 30), 'signature_name': ('ФИО подписанта', 180),
}


def default_values():
    values = {key: '' for key in FIELDS}
    values.update(contract_date=date.today().isoformat(), kind='photo', package='walk', subject='Прогулочная',
                  hours='1', price='6000', photo_count='60', retouch_count='3', photo_format='JPEG',
                  retouch_selector='Исполнитель', video_extras='не входят', studio='none',
                  video_format='MOV или MP4', delivery_days='30',
                  studio_details='не применимо', license='personal', commercial_use='не применимо',
                  wishes='нет', purpose='личная')
    return values


def validate_values(form):
    values = {key: str(form.get(key, '')).strip() for key in FIELDS}
    errors = []
    if not re.fullmatch(r'[0-9]{1,3}', values['delivery_days']) or not 1 <= int(values['delivery_days']) <= 365:
        errors.append('Укажите срок готовности от 1 до 365 календарных дней.')
    for key, (label, limit) in FIELDS.items():
        if len(values[key]) > limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]', values[key]):
            errors.append(f'Поле «{label}»: максимум {limit} символов, без служебных знаков.')
    for key in ('city', 'contract_date', 'client_name', 'phone', 'vk', 'subject', 'shooting_date', 'start_time', 'end_time', 'hours', 'location', 'price'):
        if not values[key]: errors.append(f'Заполните поле «{FIELDS[key][0]}».')
    for key, allowed in [('package', {p['id'] for p in PACKAGES}), ('kind', set(KINDS)),
                         ('studio', {'none', 'separate'}), ('license', {'personal', 'commercial'}),
                         ('purpose', {'личная', 'семейная', 'бытовая', 'предпринимательская'})]:
        if values[key] not in allowed: errors.append(f'Выберите значение поля «{FIELDS[key][0]}».')
    parsed_dates = {}
    for key in ('contract_date', 'shooting_date'):
        try: parsed_dates[key] = date.fromisoformat(values[key])
        except ValueError: errors.append(f'Укажите корректную дату: {FIELDS[key][0]}.')
    if len(parsed_dates) == 2 and parsed_dates['shooting_date'] < parsed_dates['contract_date']:
        errors.append('Дата съёмки не может быть раньше даты договора.')
    for key, minimum, maximum in [('price', 1000, 10000000), ('hours', Decimal('0.25'), 24)]:
        try:
            number = Decimal(values[key].replace(',', '.'))
            if not number.is_finite() or not minimum <= number <= maximum or number.as_tuple().exponent < -2: raise ValueError
            values[key] = format(number, 'f')
        except (InvalidOperation, ValueError): errors.append(f'Поле «{FIELDS[key][0]}»: число от {minimum} до {maximum}, не более двух знаков после запятой.')
    try:
        start = datetime.strptime(values['start_time'], '%H:%M')
        end = datetime.strptime(values['end_time'], '%H:%M')
        minutes = int((end - start).total_seconds() / 60) % 1440
        if minutes == 0: minutes = 1440
        if abs(Decimal(minutes) - Decimal(values['hours']) * 60) > Decimal('0.6'):
            errors.append('Продолжительность не совпадает с началом и окончанием съёмки. Для ночной съёмки окончание считается следующим днём.')
    except (ValueError, InvalidOperation): errors.append('Укажите корректное время начала, окончания и продолжительность.')
    if values['kind'] in {'photo', 'both'}:
        for key in ('photo_count', 'retouch_count'):
            if not re.fullmatch(r'[0-9]{1,6}', values[key]) or not 0 <= int(values[key]) <= 100000 or (key == 'photo_count' and int(values[key]) == 0):
                errors.append(f'Укажите корректное количество: {FIELDS[key][0]}.')
        if re.fullmatch(r'[0-9]{1,6}', values['photo_count']) and re.fullmatch(r'[0-9]{1,6}', values['retouch_count']) and int(values['retouch_count']) > int(values['photo_count']):
            errors.append('Кадров в детальной ретуши не может быть больше общего количества фото.')
        for key in ('photo_format', 'retouch_selector', 'photo_edits'):
            if not values[key]: errors.append(f'Заполните поле «{FIELDS[key][0]}».')
    if values['kind'] in {'video', 'both'}:
        if not re.fullmatch(r'[0-9]{1,4}', values['video_count']) or not 1 <= int(values['video_count']) <= 1000: errors.append('Укажите количество готовых роликов от 1 до 1000.')
        for key in ('video_duration', 'video_format', 'video_edits'):
            if not values[key]: errors.append(f'Заполните поле «{FIELDS[key][0]}».')
    if values['studio'] == 'separate' and not values['studio_details']: errors.append('Укажите студию и время бронирования.')
    if values['license'] == 'commercial' and values['commercial_use'] in {'', 'не применимо'}: errors.append('Для коммерческой лицензии укажите цель, способы использования и рекламные каналы.')
    if not values['signature_name']:
        if values['representative']: errors.append('Укажите ФИО подписанта организации или ИП.')
        else: values['signature_name'] = values['client_name']
    return values, errors


W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
TEXT = re.compile(r'(<w:t\b[^>]*>)(.*?)(</w:t>)', re.S)
PARAGRAPH = re.compile(r'<w:p\b[^>]*?/>|<w:p\b[^>]*>.*?</w:p>', re.S)


def _paragraph_text(xml):
    return ''.join(ET.fromstring('<root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' + match[0] + '</root>')[0].text or '' for match in TEXT.finditer(xml))


def _replace_text(xml, old, new):
    """Replace across split Word runs while preserving every run's formatting."""
    text = _paragraph_text(xml)
    offset = text.find(old)
    if offset < 0: raise ValueError('В шаблоне отсутствует ожидаемое поле договора.')
    end = offset + len(old)
    cursor = 0
    def replace(match):
        nonlocal cursor
        raw = ET.fromstring('<root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' + match[0] + '</root>')[0].text or ''
        start, stop = cursor, cursor + len(raw)
        cursor = stop
        if start >= end or stop <= offset: return match[0]
        left = raw[:max(0, offset - start)]
        right = raw[max(0, end - start):] if stop > end else ''
        inserted = new if start <= offset < stop else ''
        return match[1] + escape(left + inserted + right) + match[3]
    return TEXT.sub(replace, xml)


def _fill_blank(xml, value):
    if xml.endswith('/>'):
        xml = xml[:-2] + '></w:p>'
    return xml.replace('</w:p>', '<w:r><w:t xml:space="preserve">' + escape(value) + '</w:t></w:r></w:p>')


def _signature_initials(name):
    parts = name.split()
    return ' '.join([parts[0], ' '.join(part[0].upper() + '.' for part in parts[1:])]) if len(parts) > 1 else name


def build_contract(values):
    """Return a DOCX in memory. No client data is written to disk or session."""
    v = values
    def ru_date(key): return date.fromisoformat(v[key]).strftime('%d.%m.%Y')
    kind = v['kind']
    photo = kind in {'photo', 'both'}
    video = kind in {'video', 'both'}
    days = int(v['delivery_days'])
    deadline = f'{days} календарного дня' if days % 10 == 1 and days % 100 != 11 else f'{days} календарных дней'
    money = format(Decimal(v['price']), ',.2f').replace(',', ' ').replace('.', ',').removesuffix(',00')
    replacements = {
        1: [('[город]', v['city']), ('[дата заключения]', ru_date('contract_date'))],
        2: [('[ФИО гражданина либо наименование организации / ИП]', v['client_name'])],
        96: [('[личная / семейная / бытовая либо предпринимательская]', v['purpose'])],
        39: [('30 календарных дней', deadline)],
        113: [('[ФИО]', _signature_initials(v['signature_name']))],
    }
    representative = 'в лице [для организации: ФИО, должность и основание полномочий], '
    replacements[2].append((representative, f'в лице {v["representative"]}, ' if v['representative'] else ''))
    # Each line in 1.2 is a distinct formatted Word run in the retained source.
    lines = [
        (1, f'Вид: {KINDS[kind]}. Пакет или сюжет: {v["subject"]}.'),
        (2, f'Дата съёмки: {ru_date("shooting_date")}. Время: с {v["start_time"]} до {v["end_time"]}, московское. Продолжительность: {v["hours"].replace(".", ",")} часов. Съёмочное время учитывается непрерывно по пункту 4.8.'),
        (3, f'Место: {v["location"]}. Общая цена услуг Исполнителя: {money} рублей.'),
        (4, f'Результат фото за весь заказ: не менее {v["photo_count"]} готовых фотографий; из них детальная ретушь {v["retouch_count"]} кадров. Формат файлов: {v["photo_format"]}. Кадры для детальной ретуши выбирает {v["retouch_selector"]}.' if photo else 'Результат фото за весь заказ: не входит.'),
        (5, f'Результат видео: {v["video_count"]} смонтированных роликов продолжительностью {v["video_duration"]} каждый. Формат файлов, разрешение и ориентация: {v["video_format"]}. Дополнительные версии и отдельная запись речи: {v["video_extras"] or "не входят"}. Один час съёмки означает время работы, а не длительность готового видео.' if video else 'Результат видео: не входит. Один час съёмки означает время работы, а не длительность готового видео.'),
        (6, f'Объём одного раунда творческих корректировок: фото — {v["photo_edits"] if photo else "не входит"}; видео — {v["video_edits"] if video else "не входит"}.'),
        (7, f'Аренда студии: {"Заказчик самостоятельно бронирует и оплачивает студию" if v["studio"] == "separate" else "не предусмотрена"}. Студия и время бронирования: {v["studio_details"] if v["studio"] == "separate" else "не применимо"}. Аренда не входит в общую цену услуг Исполнителя и не оплачивается ему.'),
        (9, f'Лицензия: {"коммерческое использование" if v["license"] == "commercial" else "личное использование"}. Для коммерческого использования указать цель, разрешённые способы, ресурсы и рекламные каналы: {v["commercial_use"] if v["license"] == "commercial" else "не применимо"}.'),
        (10, f'Особые существенные пожелания и включённые услуги: {v["wishes"] or "нет"}.'),
    ]
    with ZipFile(TEMPLATE) as source:
        xml = source.read('word/document.xml').decode('utf-8')
        paragraphs = list(PARAGRAPH.finditer(xml))
        root = ET.fromstring(source.read('word/document.xml'))
        condition_texts = [t.text or '' for t in root.findall('.//' + W + 'p')[5].findall('.//' + W + 't')]
        replacements[5] = [(condition_texts[index], value) for index, value in lines]
        replacements[5].append(('Окончательный результат — не позднее 30 календарных дней после съёмки.',
                                f'Окончательный результат — не позднее {deadline} после съёмки.'))
        blanks = {101: v['client_name'], 103: v['phone'], 105: v['vk']}
        for index in reversed(range(len(paragraphs))):
            match = paragraphs[index]
            block = match[0]
            for old, new in replacements.get(index, []): block = _replace_text(block, old, new)
            if index in blanks: block = _fill_blank(block, blanks[index])
            xml = xml[:match.start()] + block + xml[match.end():]
        ET.fromstring(xml)  # Verify XML after escaped field replacement.
        output = BytesIO()
        with ZipFile(output, 'w') as target:
            for info in source.infolist(): target.writestr(copy(info), xml.encode('utf-8') if info.filename == 'word/document.xml' else source.read(info.filename))
    output.seek(0)
    return output


@contracts_bp.route('/shootings/contracts', methods=['GET', 'POST'])
@login_required
def generate():
    from app.routes import _is_mobile_request
    if _is_mobile_request():
        abort(403, description="Генерация договора доступна только на ПК.")
    candidate = request.form.get('return_to') if request.method == 'POST' else request.args.get('return_to')
    allowed_paths = {'/shootings', '/shootings/upcoming', '/shootings/archive', '/shootings/add', '/shootings-hub'}
    back_url = '/shootings'
    if candidate:
        try:
            parsed = urlsplit(candidate)
        except ValueError:
            parsed = urlsplit('/shootings')
        if not parsed.scheme and not parsed.netloc and not parsed.query and not parsed.fragment and '\\' not in candidate:
            if parsed.path in allowed_paths or re.fullmatch(r'/shootings/\d+', parsed.path):
                back_url = parsed.path
    values = default_values()
    errors = []
    if request.method == 'POST':
        values, errors = validate_values(request.form)
        if not errors:
            document = build_contract(values)
            response = send_file(document, as_attachment=True,
                                 download_name=f'Договор на съёмку {values["shooting_date"]}.docx',
                                 mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response.headers['Cache-Control'] = 'no-store, private'
            return response
    elif request.args.get('shooting_id'):
        try: shooting_id = int(request.args['shooting_id'])
        except ValueError: abort(400)
        shooting = get_shooting_by_id(shooting_id)
        if not shooting: abort(404)
        values.update(client_name=shooting['client_name'], phone=shooting['phone'] or '',
                      subject=shooting['project_name'], shooting_date=shooting['shooting_date'],
                      start_time=shooting['shooting_time'] or '', hours=str(shooting['duration_hours'] or ''),
                      price=str(shooting['price'] or ''), wishes=shooting['notes'] or 'нет')
        if values['start_time'] and values['hours']:
            try: values['end_time'] = (datetime.strptime(values['start_time'], '%H:%M') + timedelta(hours=float(values['hours']))).strftime('%H:%M')
            except ValueError: pass
    conn = get_connection()
    try:
        bookings = conn.execute('SELECT id, project_name, client_name, shooting_date FROM shootings ORDER BY shooting_date DESC LIMIT 100').fetchall()
    finally: conn.close()
    response = make_response(render_template('shooting_contract.html', values=values, errors=errors,
                                             packages=PACKAGES, kinds=KINDS, bookings=bookings,
                                             fields=FIELDS,
                                             back_url=back_url,
                                             price_source=PRICE_SOURCE, price_checked=PRICE_CHECKED))
    response.headers['Cache-Control'] = 'no-store, private'
    return response
