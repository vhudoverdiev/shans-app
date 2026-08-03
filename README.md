# Shans

Flask веб-приложение для личного управления данными.

## Возможности

- Авторизация пользователей
- Учёт бюджета
- История баланса
- Экспорт бюджета в Excel
- Учёт выполненных работ по автомобилю
- Учёт планируемых работ по автомобилю
- Уведомления по обслуживанию автомобиля
- Раздел фотопроектов: город/адрес, временные окна и записи с оплатой

## Технологии

- Python
- Flask
- Flask-Login
- SQLite
- openpyxl
- Gunicorn
- Nginx
- systemd

## Запуск локально

### 1. Клонировать репозиторий

```bash
git clone https://github.com/vhudoverdiev/shans-app.git
cd shans-app
```

## Уведомления

- Уведомления личного графика доставляются через Web Push в установленное на экран «Домой» веб-приложение.
- Сводка приходит в 10:00 за текущий день и в 20:00 за следующий день по московскому времени.
- Для задач с указанным временем отдельное напоминание приходит за 2 часа.
- Внешний скрипт или Telegram-бот, который уже отправляет сообщение в Telegram, может продублировать его в push на сайте через `POST https://shansplanner.ru/api/push/external/telegram`.
- На сервере нужно задать `TELEGRAM_PUSH_SECRET` в `.env`, а в запросе передавать тот же секрет в заголовке `X-Shans-Push-Secret`.
- Внешний Telegram-push всегда доставляется только основному системному администратору, созданному через `create_admin.py`; `username` и `user_id` в запросе не нужны.

Куда внести данные:

- `.env` на сервере с CRM: `TELEGRAM_PUSH_SECRET=длинный_случайный_секрет`.
- Окружение сервера, где работает Telegram-бот: тот же `TELEGRAM_PUSH_SECRET`.
- Если CRM доступна не по `https://shansplanner.ru`, добавьте рядом с ботом `CRM_TELEGRAM_PUSH_URL=https://ваш-домен/api/push/external/telegram`.

Пример запроса из скрипта:

```bash
curl -X POST "https://shansplanner.ru/api/push/external/telegram" \
  -H "Content-Type: application/json" \
  -H "X-Shans-Push-Secret: $TELEGRAM_PUSH_SECRET" \
  -d '{
    "title": "Шанс - Telegram",
    "body": "Бот прислал новое уведомление.",
    "navigate_path": "/"
  }'
```

Готовый Python-клиент можно импортировать прямо в код бота:

```python
from telegram_crm_push import send_crm_push


def notify_admin(text):
    # здесь остаётся ваша текущая отправка сообщения в Telegram
    # bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
    send_crm_push(text, title="Шанс - Telegram", navigate_path="/")
```

Или проверить вручную с сервера:

```bash
python telegram_crm_push.py "Проверка push из Telegram-бота"
```

## Деплой на сервер (main)

Если на сервере нет `deploy.sh`, значит локальный серверный репозиторий ещё не подтянут до коммита, где он добавлен.

```bash
cd /var/www/shans-app
git fetch origin
git checkout main
git reset --hard origin/main
```

Проверка, что скрипт появился:

```bash
ls -l /var/www/shans-app/deploy.sh
```

Запуск деплоя:

```bash
cd /var/www/shans-app
chmod +x deploy.sh
./deploy.sh
```

По умолчанию скрипт не удаляет `.env` (режим `CLEAN_MODE=safe`).
Также по умолчанию включена проверка чистоты tracked-файлов после деплоя (`VERIFY_CLEAN=true`).

Если после рестарта сервиса снова появляются изменения в `git status`, это признак того, что в репозитории по ошибке отслеживаются runtime-файлы (например, `__pycache__`, `*.pyc`, `logs/*`).
