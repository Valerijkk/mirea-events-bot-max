# 7. Развёртывание

## Учётка для проверки (этот стенд)

Для жюри и быстрой проверки уже создан:

* Бот в МАКС — **@spring_cat44_bot** (Весенний_код_44).
* Админка (SPA): `http://localhost/` — `admin@mirea.ru` / `admin12345`.

## Самый быстрый путь: Docker

```bash
cp .env.example .env
# Заполните BOT_TOKEN, BOT_USERNAME, JWT_SECRET

docker compose up -d --build
docker compose exec backend python -m app.cli.init_project
```

Готово — SPA на `http://localhost/` (nginx, порт 80), API на `http://localhost:8000/api/v1/`.

Стек compose: **db** (PostgreSQL 17) + **backend** (uvicorn) + **frontend** (nginx + React static).
Образ backend — multi-stage, запускается под непривилегированным юзером `mirea`, HTTP-healthcheck.

Перед сборкой frontend локально (опционально, если не через compose):

```bash
cd frontend && npm install && npm run build
```

## Локальный запуск (для разработки)

Требования: Python 3.11+, Node.js 20+, виртуальное окружение.

```bash
# 1. Backend-зависимости
python -m venv .venv
source .venv/bin/activate           # Linux/macOS
# .venv\Scripts\activate            # Windows
pip install -r backend/requirements.txt

# 2. Frontend-зависимости и билд (для prod-like проверки)
cd frontend && npm install && npm run build && cd ..

# 3. Конфигурация
cp .env.example .env
# Открой .env и заполни как минимум:
#   BOT_TOKEN      — у @MasterBot в MAX
#   BOT_USERNAME   — username бота без «@»
#   JWT_SECRET     — python -c "import secrets; print(secrets.token_urlsafe(48))"

# 4. БД, администратор и реальные события МИРЭА
make bootstrap        # init_db + admin@mirea.ru + iptip@mirea.ru + парсинг событий

# 5. Запуск
make dev              # backend :8000 + frontend dev :5173
```

После запуска доступно:

* `http://localhost:5173/` — React SPA (dev-сервер Vite)
* `http://localhost:5173/login` — вход в админку
* `http://localhost:8000/docs` — Swagger UI (напрямую к backend)
* `http://localhost:8000/api/v1/healthz` — liveness-проверка

Через docker-compose (nginx): `http://localhost/` и `/login`, Swagger — `/docs`.

Бот — в режиме long polling. HTTPS не нужен, ngrok не нужен.

## Прод-режим

Стандартная схема: Nginx (frontend-контейнер) → uvicorn (backend) → PostgreSQL.

### 1. Подготовка хоста

```bash
# Системные пакеты
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm nginx

# Юзер для сервиса
sudo useradd --system --shell /bin/false mirea
sudo mkdir -p /opt/mirea-events-bot
sudo chown mirea:mirea /opt/mirea-events-bot
```

### 2. Установка кода

```bash
sudo -u mirea git clone <ваш-репозиторий> /opt/mirea-events-bot
cd /opt/mirea-events-bot
sudo -u mirea python3.11 -m venv .venv
sudo -u mirea .venv/bin/pip install -r backend/requirements.txt
sudo -u mirea cp .env.example .env
sudo -u mirea nano .env       # заполнить
sudo -u mirea bash -c "cd frontend && npm ci && npm run build"
sudo -u mirea .venv/bin/python -m app.db_init
sudo -u mirea .venv/bin/python -m app.cli.init_project
```

### 3. systemd unit

`/etc/systemd/system/mirea-events-bot.service`:

```ini
[Unit]
Description=mirea-events-bot backend
After=network.target postgresql.service

[Service]
User=mirea
WorkingDirectory=/opt/mirea-events-bot/backend
EnvironmentFile=/opt/mirea-events-bot/.env
ExecStart=/opt/mirea-events-bot/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mirea-events-bot
sudo systemctl status mirea-events-bot
```

Frontend static — через nginx (см. `frontend/nginx.conf` в репо) или docker-compose.

### 4. Nginx + HTTPS

```nginx
server {
    server_name abitur.example.org;
    listen 443 ssl http2;
    # ssl_certificate / ssl_certificate_key выдаст certbot

    root /opt/mirea-events-bot/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }
}
```

```bash
sudo certbot --nginx -d abitur.example.org
```

### 5. Переключение в webhook-режим

В `.env` укажите:

```
WEBHOOK_URL=https://abitur.example.org/webhook
WEBHOOK_SECRET=<любая_рандомная_строка>
```

Перезапустите сервис — приложение само зарегистрирует подписку у МАКС
при следующем старте.

## Postgres

PostgreSQL — основная БД. В docker-compose сервис `db` поднимается
автоматически (образ `postgres:17`, volume `pgdata`).

Backend читает `DATABASE_URL` из `.env`. Пример для compose:

```
DATABASE_URL=postgresql+psycopg2://mirea:mirea@db:5432/mirea_events
```

Локально без Docker:

```
DATABASE_URL=postgresql+psycopg2://mirea:mirea@127.0.0.1:5432/mirea_events
```

Инициализация схемы и seed:

```bash
cd backend && python -m app.db_init
python -m app.cli.init_project   # admin + события МИРЭА
```

## Бэкапы

* Postgres — `pg_dump` (volume `pgdata` в compose).
* QR-кеш в `data/qr/` восстановим из БД (`qr_token` → перерисовать) —
  бэкапить необязательно.

## Что мониторить в проде

* `/api/v1/healthz` — раз в 30 секунд (балансировщик).
* `/api/v1/readyz` — раз в 60 секунд (Kubernetes readiness).
* `/api/v1/stats` (с токеном) — раз в 5 минут для дашборда.
* Логи systemd: `journalctl -u mirea-events-bot -f`.

## Что нужно усилить перед продом

| Зачем                              | Что делать                                                          |
|------------------------------------|---------------------------------------------------------------------|
| Безопасность                       | Сменить `JWT_SECRET` на длинный рандом, поставить HTTPS.            |
| Производительность БД              | Postgres + connection pool tuning.                                  |
| Массовые рассылки                  | Вынести `send_broadcast` в фоновый воркер (ARQ или Celery+Redis).   |
| Многоэкземплярность                | Вынести APScheduler в отдельный воркер (иначе тики продублируются). |
| Наблюдаемость                      | Sentry / Loguru, метрики Prometheus.                                |
| Юрлицо МАКС                        | Верификация для прод-публикации (требование МАКС).                  |
