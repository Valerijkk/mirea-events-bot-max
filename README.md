# 🎓 mirea-events-bot

### Запись абитуриентов на мероприятия РТУ МИРЭА через мессенджер МАКС


[![Stack: Python 3.11 · FastAPI · maxapi · SQLAlchemy 2.0](https://img.shields.io/badge/stack-Python%203.11%20%C2%B7%20FastAPI%20%C2%B7%20maxapi-4f46e5)]()
[![CI: qa](https://img.shields.io/badge/CI-qa-10b981)]()

> ⚠️ **Дисклеймер.** Этот сервис разработан студенческой командой хакатона
> «Весенний код» (РТУ МИРЭА × VK) и **не является официальной функцией
> платформы МАХ**. По вопросам обработки данных — РТУ МИРЭА.

Бот для мессенджера **МАКС**, который позволяет **абитуриентам и студентам
РТУ МИРЭА** записываться на мероприятия университета (дни открытых дверей,
мастер-классы, олимпиады, экскурсии, консультации), а сотрудникам университета
(приёмная комиссия, факультеты, кафедры, студсовет) — вести эти мероприятия
из веб-админки.

Проект подготовлен к хакатону **«Весенний код» РТУ МИРЭА × VK × 1С × МКСКОМ**,
трек **«МАКС»**, **кейс №2** — «Запись абитуриента на мероприятие университета».

---

## Что в коробке

**Для абитуриента (бот):**

* **Согласие на обработку данных** при первом запуске — с версией документа и
  меткой времени (ТЗ §«Пользовательский процесс»). После согласия бот запрашивает
  ФИО пользователя (ФЗ-152: идентификация субъекта персональных данных).
* **Запись на мероприятие** через каталог или deeplink с афиши/QR.
* **Слоты** — несколько временных окон у одного мероприятия с независимой
  вместимостью.
* **«Подробнее»** в карточке — расширенное описание, требования к участникам,
  условия отмены.
* **Сводка перед подтверждением** записи — все существенные параметры.
* **Человекочитаемый код записи** `RG-XXXXXX` + QR-пропуск.
* **Повторный QR** — кнопка «Получить QR» в разделе «Мои записи» для каждой активной записи.
* **Отмена** записи с автопромоушеном следующего из листа ожидания.
* **Поздняя отмена** после старта — по политике мероприятия (запретить или
  отметить как «Поздняя отмена»).
* **Per-event уведомления** — отключить напоминания по конкретной записи,
  не отписываясь от бота целиком.

**Для организатора (React-админка):**

* **Дашборд** со счётчиками и баннером «требует внимания».
* **Управление мероприятиями** — создать, опубликовать, отменить целиком,
  **закрыть регистрацию** вручную, **дублировать** для серийных событий.
* **Слоты** — добавить/удалить временные окна внутри события.
* **Список участников** на странице события (с кодом, слотом).
* **Поиск по коду записи** для быстрой проверки на входе.
* **Изменить статус записи** прямо из карточки: «отметить пришедшим»,
  «отменить запись» — пользователю придёт уведомление, waitlist промотируется.
* **Сегментированная рассылка** только в рамках одного мероприятия (ТЗ
  ограничивает: «не модуль массовых рассылок»). Шаблоны автоподставляют title/время.
* **QR-сканер** на входе мероприятия через камеру (jsQR) + ручной ввод RG-XXXXXX.
* **Многократный проход** по QR (`max_entries`: 1 / 2 / 5 / безлимит) — для туров с обедом, многодневных мероприятий.
* **Постер A4 PNG** с QR на deeplink — печатается из админки одним кликом.
* **CSV-экспорт** реестра участников (UTF-8 BOM для Excel + защита от CSV-injection).
* **Управление ролями** (для role=admin): создать организатора, поменять
  роль. Multi-tenant: organizer видит только свои мероприятия, admin — все.
* **Audit-log** — журнал действий организаторов (только admin).
* **Премиум-UX**: тёмная тема, mobile-меню, toast после действий, confirm-modal вместо системного `alert()`.

**Интеграция с ИС вуза:**

* **Bulk-импорт событий** через одну ручку `POST /api/v1/integration/events/sync` —
  ИС вуза (priem.mirea.ru, 1С, основной сайт) шлёт нам JSON-батч событий,
  идемпотентно обрабатывается по паре `(source, external_id)`. Повторный POST
  того же события = `updated`, не дубликат. Один невалидный элемент не валит batch.
* **Отдельная auth по X-API-Key** (не JWT), ключ хранится bcrypt-хешем,
  привязан к организатору-владельцу — события через ключ принадлежат строго ему.
* **Safe-mode**: новые события приходят как `draft` и ждут проверки оператором.
  Можно включить `auto_publish` на ключе или в конкретном запросе.
* **Сохранение ручных решений**: если оператор отменил событие — повторный sync
  его не воскрешает (внешняя система не перетирает решения людей).
* **В проде** ИС вуза кладёт события напрямую через `POST /api/v1/integration/events/sync`
  — никакого скрейпинга. Для **локальной разработки и QA** есть test-only парсер
  `scripts/fetch_mirea_events.py`, который тянет страницы `mirea.ru/eventspage/`,
  фильтрует на 30 дней вперёд и отправляет в локальный SUT той же ручкой.

**Безопасность:**

* JWT в HttpOnly cookie + Bearer для REST. Валидация секрета на старте.
* Rate-limit: login 5/мин/IP, `/v1/scan` и админ-сканер 60/мин/организатор.
* XSS-защита: React SPA + typed API-клиент.
* `with_for_update` в `sign_up` и `scan_lookup` — защита от race condition на capacity и от двойного прохода.
* Oracle-mitigation: сканер возвращает одинаковый `not_found` для 403/404, чтобы нельзя было брутить чужие RG-коды по разнице ответов.
* CSV-injection: ячейки, начинающиеся с `= + - @ \t \r`, префиксуются одинарной кавычкой.
* Security headers (X-Frame-Options DENY, nosniff, Referrer-Policy strict-origin, Permissions-Policy `camera=(self), microphone=(), geolocation=()`).
* IDOR-защита на всех REST-роутах через единый `assert_event_owned`/`get_owned_event_by_id`.

**Инфраструктура:**

* **REST API** `/api/v1/*` со Swagger UI `/docs` и ReDoc `/redoc`.
* **Планировщик** — авто-напоминания за 24 часа и 1 час до старта (учитывают
  slot, late-cancel, отписку).
* **Docker + docker-compose** — postgres:16 + backend + frontend (nginx).
* **Полное покрытие тестами** — unit, integration, API (httpx), UI (Playwright), E2E на реальных данных МИРЭА.
* **SQLite** для локальной разработки, **PostgreSQL 16** — в docker-compose и одной строкой в `.env`.
* **Авто-миграция схемы** на старте — недостающие колонки добавляются ALTER'ом без alembic.
* **Security headers** (X-Frame-Options, nosniff, Permissions-Policy) и rate-limit на login/scan.

Подробнее — в **[docs/](docs/README.md)**.

## Стек

**Backend:** Python 3.11 · FastAPI 0.121 · Uvicorn · SQLAlchemy 2.0 · APScheduler · maxapi ·
qrcode + Pillow · PyJWT + bcrypt · PostgreSQL 16 · pytest · Playwright.

**Frontend:** React 18 · Vite 5 · TypeScript · Tailwind CSS 4 · TanStack Query · Zustand · React Router v6 · jsQR.

## Быстрый старт

### Вариант 1 — Docker (postgres + backend + frontend)

```bash
cp .env.example .env
# Заполни BOT_TOKEN, BOT_USERNAME, JWT_SECRET

make docker-up
docker compose exec backend python -m app.cli.init_project
```

После старта:

| Что | Адрес |
|-----|-------|
| React-админка | http://localhost |
| Backend API | http://localhost:8000/api/v1/ |
| Swagger UI | http://localhost:8000/docs |

### Вариант 2 — локально (без Docker)

Требуется Python 3.11+ и Node.js 18+.

**Backend** (терминал 1):

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env
# Заполни BOT_TOKEN, BOT_USERNAME, JWT_SECRET, DATABASE_URL (SQLite или Postgres)

python -m app.cli.init_project   # один раз: БД + admin + integration-keys
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend** (терминал 2):

```bash
cd frontend
npm install
npm run dev
```

После старта:

| Что | Адрес |
|-----|-------|
| React-админка (dev) | http://localhost:5173 |
| Backend API | http://localhost:8000/api/v1/ |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Healthcheck | http://localhost:8000/api/v1/healthz |

Короткие команды через Makefile (из корня репо): `make bootstrap`, `make dev` (backend на :8080), `make test`.

`make bootstrap` запускает `python -m app.cli.init_project`. Скрипт:

1. Создаёт таблицы (`init_db`).
2. Заводит администратора `admin@mirea.ru` / `admin12345`.
3. Заводит организатора факультета **ИПТИП** `iptip@mirea.ru` / `organizer12345`.
4. Заводит второго организатора `qa-second@mirea.ru` (для cross-tenant QA-тестов).
5. Создаёт `IntegrationKey` для двух источников:
   * **`mirea_main`** — для ИС вуза в проде;
   * **`qa`** — для локального парсера и QA-фреймворка.
   Plaintext ключи выводятся **один раз** при первой инициализации.

События в БД **не наполняются** — их кладёт либо ИС вуза в проде через REST,
либо локальный парсер `scripts/fetch_mirea_events.py` (test-only).

Пароли можно переопределить через `ADMIN_PASSWORD` / `ORG_PASSWORD` / `SECOND_ORG_PASSWORD` в env.

Бот в `dev`-режиме сразу принимает сообщения через long polling — ngrok и
HTTPS не нужны. Перевод на webhook см. в [docs/07-deployment.md](docs/07-deployment.md).

## API

Все REST-ручки под префиксом **`/api/v1/`**. Интерактивная документация:

* **Swagger UI** — `/docs`
* **ReDoc** — `/redoc`

Основные группы: `auth`, `events`, `slots`, `registrations`, `organizers`, `scan`, `broadcasts`, `stats`, `audit`, `integration`, `health`. Полный список — в [docs/05-api.md](docs/05-api.md).

## Тесты

```bash
make test                                  # unit-тесты SUT (in-memory)
```

Все тесты живут в `testing-framework/tests/`. Группы:

**Unit (in-memory, без сервера)** — `testing-framework/tests/unit/`:

* Бизнес-логика — `test_registration.py`, `test_slots.py`, `test_consent.py`,
  `test_late_cancel.py`, `test_close_registration.py`, `test_registration_code.py`,
  `test_scan_max_entries.py`, `test_cancel_by_organizer.py`.
* Безопасность — `test_auth.py`, `test_api_ownership.py`, `test_slot_idor.py`,
  `test_security.py`, `test_regressions_final.py`.
* Уведомления — `test_notifications.py`, `test_bot_handlers.py`,
  `test_bot_handlers_views.py`, `test_bot_client.py`.
* Интеграционные через `TestClient` — `unit/integration/test_rest_api.py`,
  `test_landing.py`, `test_integration_sync.py`.
* Утилиты фреймворка — `test_utils_*.py`, `test_bug_report.py`, `test_timings.py`,
  property-based `test_property_event_dates.py`, бенчмарки `test_perf_*.py`.

**API + smoke UI (нужен поднятый SUT)** — `testing-framework/tests/api/`,
`tests/ui/`, `tests/integration/`, `tests/e2e/`:

* `tests/api/<домен>/test_*_{pos,neg}.py` — REST-контракт по доменам
  (auth, events, registrations, broadcasts, scan, stats, integration, health, security).
* `tests/ui/<домен>/test_*.py` — Playwright Chromium (auth, dashboard,
  events, organizers, scanner).
* `tests/integration/` — «API создал → UI показал» и обратно.
* `tests/e2e/` — полный flow организатора + E2E на реальных событиях МИРЭА.

См. **[testing-framework/docs/test-cases.md](testing-framework/docs/test-cases.md)**
— ручной каталог тест-кейсов с ID, сценариями и критериями приёмки.

## Структура проекта

```
mirea-events-bot/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI + lifespan (бот, планировщик, миграции, SPA mount)
│   │   ├── config.py           # настройки из .env
│   │   ├── db.py / db_init.py  # SQLAlchemy + create_all + ALTER auto-migration
│   │   ├── models.py           # ORM-модели (User, Organizer, Event, EventSlot,
│   │   │                       #   Registration, Broadcast, Consent, Reminder,
│   │   │                       #   IntegrationKey, AuditLog)
│   │   ├── scheduler.py        # APScheduler + process_due_reminders
│   │   ├── bot/                # хендлеры, тексты, клавиатуры, нотификации, MAX-клиент
│   │   ├── core/               # rate_limit, security_headers, formatting
│   │   ├── services/           # registration, scan, broadcast, qr, poster, ics,
│   │   │                       # stats, slots, consent, audit, integration
│   │   ├── admin/              # JWT/bcrypt-утилиты (HTML-админка удалена)
│   │   ├── api/                # REST API /api/v1/
│   │   │   ├── deps.py         # CurrentOrganizer, DbSession, OwnedEvent
│   │   │   └── v1/             # auth, events, slots, registrations, organizers,
│   │   │                       # scan, broadcasts, stats, audit, integration, health
│   │   ├── schemas/            # Pydantic-схемы (для Swagger)
│   │   └── cli/init_project.py # CLI: bootstrap (DB + admin + integration-keys)
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/              # Login, Events, EventDetail, Slots, Scanner,
│   │   │                       # Broadcasts, Organizers, Audit, Stats
│   │   ├── api/                # typed REST-клиент (axios + TanStack Query)
│   │   ├── components/         # Layout, Modal, Select, ProtectedRoute, AdminRoute
│   │   ├── stores/             # Zustand (authStore)
│   │   └── router.tsx          # React Router v6
│   ├── Dockerfile              # nginx + SPA build
│   ├── nginx.conf              # proxy /api/ → backend
│   └── package.json
├── scripts/
│   └── fetch_mirea_events.py   # test-only парсер mirea.ru → REST sync
├── testing-framework/          # black-box QA: api, ui (Playwright), e2e, integration
├── docs/                       # русскоязычная документация
├── data/                       # БД, QR-кеш — в .gitignore
├── docker-compose.yml          # postgres:16 + backend + frontend
├── .env.example
├── Makefile
├── LICENSE                     # MIT
└── README.md
```

## Куда смотреть дальше

| Хочу…                                              | Открой                                                |
|----------------------------------------------------|-------------------------------------------------------|
| Понять архитектуру в целом                         | [docs/02-architecture.md](docs/02-architecture.md)    |
| Разобраться, как устроены таблицы                  | [docs/03-data-model.md](docs/03-data-model.md)        |
| Изучить все сценарии бота                          | [docs/04-bot-scenarios.md](docs/04-bot-scenarios.md)  |
| Посмотреть API с примерами curl                    | [docs/05-api.md](docs/05-api.md)                      |
| Развернуть на прод за HTTPS                        | [docs/07-deployment.md](docs/07-deployment.md)        |
| Расширить функциональность                         | [docs/08-development.md](docs/08-development.md)      |
| Когда что-то не работает                           | [docs/09-faq.md](docs/09-faq.md)                      |

## Команды Makefile

```
make install        — pip install в backend/
make bootstrap      — БД + admin + integration-keys
make run            — uvicorn backend (prod-режим, :8080)
make dev            — uvicorn backend с auto-reload (:8080)
make test           — unit-тесты
make clean          — снести локальную БД, QR-кеш и ics
make reset          — clean + bootstrap

make docker-build   — собрать Docker-образы
make docker-up      — поднять postgres + backend + frontend
make docker-down    — остановить docker compose
make docker-logs    — логи всех сервисов
make docker-db      — psql в контейнер postgres
```

## Полезные ссылки

* Документация МАКС Bot API: https://dev.max.ru/docs-api
* Подготовка бота в МАКС: https://dev.max.ru/docs/chatbots/bots-coding/prepare
* maxapi на PyPI: https://pypi.org/project/maxapi/
