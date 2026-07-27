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
- Внешний скрипт, который уже отправляет сообщение в Telegram, может продублировать его в push на сайте через `POST https://shansplanner.ru/api/push/external/telegram`.
- На сервере нужно задать `TELEGRAM_PUSH_SECRET` в `.env`, а в запросе передавать тот же секрет в заголовке `X-Shans-Push-Secret`.

Пример запроса из скрипта:

```bash
curl -X POST "https://shansplanner.ru/api/push/external/telegram" \
  -H "Content-Type: application/json" \
  -H "X-Shans-Push-Secret: $TELEGRAM_PUSH_SECRET" \
  -d '{
    "title": "Шанс - скрипт",
    "body": "Скрипт завершился успешно.",
    "navigate_path": "/",
    "username": "vhudoverdiev"
  }'
```

`username` можно заменить на любой другой логин, если понадобится отправлять push конкретному пользователю.

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
