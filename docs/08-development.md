# 8. Разработка

## Структура каталогов

```
mirea-events-bot/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI, lifespan, webhook/polling, static SPA
│       ├── config.py            # Pydantic Settings из .env
│       ├── db.py                # SQLAlchemy 2.0 engine + session factory
│       ├── db_init.py           # create_all + ALTER ADD COLUMN
│       ├── models.py            # ORM-модели (Mapped[], select()-friendly)
│       ├── scheduler.py         # APScheduler + process_due_reminders
│       │
│       ├── bot/                 # МАКС-бот
│       │   ├── handlers.py      # хендлеры + answer_callback ACK
│       │   ├── texts.py         # тексты (правь здесь!)
│       │   ├── keyboards.py
│       │   └── client.py        # httpx-обёртка MAX API
│       │
│       ├── services/            # бизнес-логика (общая для бота и REST)
│       │   ├── registration.py
│       │   ├── broadcast.py
│       │   ├── qr.py
│       │   ├── stats.py
│       │   └── audit.py
│       │
│       ├── admin/               # JWT + bcrypt (без HTML-роутов)
│       │   └── auth.py
│       │
│       ├── api/                 # REST /api/v1/*
│       │   ├── deps.py          # Bearer JWT, OwnedEvent, AdminOrganizer
│       │   └── v1/
│       │
│       ├── schemas/             # Pydantic v2
│       └── cli/init_project.py  # bootstrap: БД + admin + парсинг МИРЭА
│
├── frontend/                  # React SPA (Vite)
│   └── src/
│       ├── router.tsx           # маршруты + ProtectedRoute / AdminRoute
│       ├── pages/               # Login, Events, Stats, Audit, …
│       ├── api/                 # TanStack Query hooks
│       └── stores/              # Zustand
│
├── testing-framework/           # black-box QA (pytest + Playwright + httpx)
├── docs/
├── docker-compose.yml           # db + backend + frontend
├── Makefile
└── README.md
```

Jinja2 HTML-админка удалена (#183). UI — только React SPA.

## Стиль кода

* Python 3.11+, `from __future__ import annotations`, type hints на публичное API.
* SQLAlchemy 2.0: `select()`, `session.scalars()`, `Mapped[]` — не `session.query()`.
* Комментарии — на русском, объясняют **почему**.
* Имена — английские; тексты пользователю — в `backend/app/bot/texts.py`.

## Сессии БД

* FastAPI: `Depends(get_session)` + явный `commit()` в успехе.
* Бот / scheduler: `with session_scope() as session:`.
* **Не держите сессию открытой во время сетевых вызовов** (MAX API).

## Как добавить новую REST-ручку

1. Pydantic-схема в `backend/app/schemas/`.
2. Обработчик в `backend/app/api/v1/`.
3. Бизнес-логика в `backend/app/services/` — переиспользуется ботом и SPA.
4. Для event-scoped ручек — dependency `OwnedEvent` или `assert_event_owned`.
5. Для admin-only — `AdminOrganizer`.
6. Обновить `docs/05-api.md` и при необходимости React-страницу.

## Как добавить сценарий бота

1. Тексты — `backend/app/bot/texts.py`.
2. Клавиатуры — `backend/app/bot/keyboards.py`.
3. Хендлер — `backend/app/bot/handlers.py` (тонкий: callback → service → send).
4. На callback не забыть: ACK уже в `on_callback`, новые ветки — после consent-check.

## Как добавить страницу SPA

1. Компонент в `frontend/src/pages/`.
2. Маршрут в `frontend/src/router.tsx` (`ProtectedRoute` / `AdminRoute`).
3. API-hook в `frontend/src/api/`.
4. Пункт меню в `frontend/src/components/Layout.tsx` (если нужен).
5. `docs/06-admin-panel.md`.

## Как добавить тип мероприятия

1. Константа в `backend/app/models.py` (`EventType`).
2. Literal в `backend/app/schemas/event.py`.
3. Select в форме на `frontend/src/pages/` (EventDetail / create modal).
4. Фильтры в `services/registration.py` при необходимости.

## Логирование

`LOG_LEVEL=DEBUG|INFO|WARNING` в `.env`. Модульный `logging.getLogger(__name__)`.

## Тестирование

Каталог `testing-framework/tests/`:

| Слой | Маркер | Что нужно |
|------|--------|-----------|
| `tests/unit/` | `unit` | in-memory SQLite, импорт `app/*`, без сервера |
| `tests/api/` | `api` | SUT на `:8080`, httpx |
| `tests/ui/` | `ui` | + Playwright Chromium |
| `tests/integration/` | `integration` | API + UI |
| `tests/e2e/` | `e2e` | полные сценарии (локально; **не в CI**) |

CI (`.github/workflows/qa.yml`): `unit` + `api or (ui and smoke)`, E2E
исключены (`--ignore=tests/e2e`), чтобы не засорять БД и не требовать бота.

```bash
cd testing-framework
pytest -m unit                          # ~70 с, параллельно
pytest -m "api or (ui and smoke)"       # нужен SUT на :8080
```

Подробнее — `testing-framework/docs/architecture.md`,
`testing-framework/docs/test-cases.md`.

## CI/CD

GitHub Actions `qa.yml`:

1. `frontend-build` — `npm run build`.
2. `lint` — ruff + mypy testing-framework.
3. `unit` — `pytest -m unit -n auto`.
4. `api-and-smoke` — поднимает uvicorn, bootstrap, Playwright, прогон
   `pytest -m "api or (ui and smoke)"` без e2e.

Артефакты: Allure raw, pytest-html, sut.log.
