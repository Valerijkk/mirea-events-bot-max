# Контрибьютинг

Проект — учебный, написан под хакатон. Если решите развивать дальше — вот правила.

## Локальная настройка

**Быстрый старт через Docker (рекомендуется):**

```bash
git clone https://github.com/Valerijkk/mirea-events-bot-max.git
cd mirea-events-bot-max
cp .env.example .env          # заполнить BOT_TOKEN, BOT_USERNAME, JWT_SECRET
docker compose build
docker compose up -d
docker compose exec backend python -m app.cli.init_project
```

**Без Docker (Python 3.11+ и Node.js 18+):**

```bash
# Терминал 1 — бэкенд
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env    # заполнить DATABASE_URL, BOT_TOKEN и др.
python -m app.cli.init_project
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Терминал 2 — фронтенд
cd frontend
npm install
npm run dev                   # dev-сервер на http://localhost:5173
```

## Перед PR — обязательно

1. **Тесты зелёные:** `cd testing-framework && pytest -m unit` — все passed.
2. **Линтер чист:** `python -m ruff check app/ testing-framework/`.
3. **Типы чистые:** `python -m mypy app` — без ошибок.
4. **Безопасность:** `python -m bandit -r app/` без HIGH/MEDIUM.
5. **Зависимости:** `python -m pip_audit -r requirements.txt` — без новых CVE.
6. **Новый код — новые тесты:** покрытие позитивного и негативного кейса.

## Стиль

* Линия: 100 символов (ruff `line-length = 100`).
* Имена файлов — английский snake_case, комментарии/docstring — русский.
* Принципы: SOLID, DRY, KISS — не плодим абстракции «на будущее».
* Public-функции — с docstring (зачем, не что).
* Каждая новая REST-ручка — с примером в `docs/05-api.md`.

## Архитектура

См. `docs/02-architecture.md`. Главное:

* `backend/app/api/v1/` — REST-ручки (тонкий слой, делегирует в `services/`).
* `backend/app/services/` — вся бизнес-логика: capacity, идемпотентность, slots.
* `backend/app/models.py` — единственный источник правды по схеме (SQLAlchemy 2.0).
* `backend/app/bot/` — клиент МАКС, handlers, dispatcher.
* `frontend/src/` — React SPA (Vite + TypeScript + Tailwind + TanStack Query + Zustand).
* `testing-framework/` — black-box QA: unit, api (httpx), ui (Playwright), e2e.

Не размазывайте бизнес-логику по роутам — выносите в `services/`.
Бизнес-логику не пишите во фронтенде — только отображение данных из API.

## Коммиты

Conventional Commits на русском:

```
feat(integration): bulk-импорт событий из ИС вуза
fix(scan): защита от повторного гашения QR
docs(api): пример запроса для /broadcasts
refactor(admin): вынос форм участников в отдельный модуль
test(slots): негативные кейсы переполнения слота
```

## Что НЕ принимаем

* Зависимости без CVE-аудита.
* Мок'и БД в интеграционных тестах (была инцидент с расхождением миграций).
* Тяжёлые либы там, где хватит 30 строк (см. `app/services/ics.py`).
* PR без описания «зачем» — изменение без мотивации не пройдёт ревью.
