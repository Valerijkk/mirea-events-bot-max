# 📋 Каталог тест-кейсов

Документ описывает все нетривиальные тест-кейсы фреймворка, **кроме unit-тестов**
(они тестируют внутренности SUT в in-memory и описаны в самом коде — docstring'ом
у каждой функции).

Каждый кейс:

- **ID** — стабильный идентификатор для трекинга в баг-репортах и Allure.
- **Файл** — где живёт реализация.
- **Что проверяем** — бизнес-смысл, не «вызов метода X».
- **Ожидаемо** — критерий приёмки.

Запуск отдельного кейса:

```bash
cd testing-framework
pytest tests/api/auth/test_login_pos.py::test_login_admin_returns_bearer_token -v
```

Маркеры (из `pyproject.toml`):

| Маркер | Когда применяется |
|--------|-------------------|
| `smoke` | Самый критичный путь — лежит → SUT не годен |
| `regression` | Полный регресс — поверхность фич |
| `api` / `ui` / `e2e` / `integration` | Слой пирамиды |
| `pos` / `neg` | Положительная / негативная ветка |
| `slow` | Долгие тесты (UI, фабрики массово) |

---

## 🔌 API — REST-контракт `/api/v1/*`

Чёрный ящик через `httpx`. SUT поднят на `:8080`, фикстуры подкладывают
JWT-токены из `/api/v1/auth/login`.

### `tests/api/auth/test_login_pos.py` — успешный логин

Логин — это вход во всю админку. Если он сломался — каскад падает.

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-AUTH-001** | Админ с верным паролем получает JWT | `200`, `token_type=bearer`, `expires_in=28800` (480 мин), `access_token` непустой |
| **TC-API-AUTH-002** | Организатор с верным паролем получает JWT | `200`, `access_token` присутствует |

### `tests/api/auth/test_login_neg.py` — отказы логина

Стратегия — единое сообщение `«Неверный …»` для всех 401-ветвей: защита от
**user enumeration** (нельзя угадать существующий email по разнице ответа).

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-AUTH-101** | Верный email + неверный пароль | `401`, `detail` содержит «Неверный» |
| **TC-API-AUTH-102** | Неизвестный email | **то же** `401` и тот же текст |
| **TC-API-AUTH-103** | Pydantic-валидация payload (пустой пароль, кривой email, пустое тело, нет пароля) | `422` (4 параметризации) |

### `tests/api/health/` — `/healthz` и `/readyz`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-HEALTH-001** | `GET /healthz` отвечает «alive» | `200`, `{"status": "alive"}` |
| **TC-API-HEALTH-002** | `GET /readyz` отвечает «ready» (БД доступна) | `200`, `{"status": "ready"}` |
| **TC-API-HEALTH-101** | `POST /healthz` запрещён | `405 Method Not Allowed` |

### `tests/api/events/test_events_crud_pos.py` — CRUD-позитив

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-EVT-001** | `POST /events` минимально валидным телом → `201` + новый id | Объект в ответе содержит присланный title, format, capacity |
| **TC-API-EVT-002** | `GET /events/{id}` владельцем — полный объект | Все обязательные поля, `organizer_id` совпадает с владельцем токена |
| **TC-API-EVT-003** | `PATCH /events/{id}` частично — обновляется только переданное поле | Остальные поля не тронуты |
| **TC-API-EVT-004** | `DELETE /events/{id}` → потом `GET` → `404` | Удалён физически, не «soft» |
| **TC-API-EVT-005** | `POST /events` builder-ом в формате `online` | Поле `format = "online"`, `location` может быть пустым |

### `tests/api/events/test_events_crud_neg.py` — CRUD-негатив

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-EVT-101** | `POST /events` без токена | `401` |
| **TC-API-EVT-102** | `POST /events` с битым payload | `422` (несколько параметризаций) |
| **TC-API-EVT-103** | `GET /events/{несуществующий_id}` | `404` |
| **TC-API-EVT-104** | `GET /events/{чужой_id}` под организатором | `403` (IDOR-защита) |
| **TC-API-EVT-105** | `DELETE` несуществующего | `404` |

### `tests/api/events/test_events_filters_pos.py`, `_neg.py`, `_mirea_pos.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-FLT-001** | `GET /events` — массив (даже если пуст) | `200`, тип list |
| **TC-API-FLT-002** | `?limit=1` отдаёт **ровно один** элемент | len == 1 |
| **TC-API-FLT-003** | `?status=published` — только published в выборке | Все элементы со `status == "published"` |
| **TC-API-FLT-004** | `?only_upcoming=true` — только будущие | Все `starts_at` > now |
| **TC-API-FLT-005** | `?type=olympiad` — **только** олимпиады (регресс реального бага SUT) | Все `event_type == "olympiad"` |
| **TC-API-FLT-006** | `?format=online` — включает онлайн-события МИРЭА | Каждый element имеет `format == "online"` |
| **TC-API-FLT-007** | `?status=published` — нет draft в ответе | Никакой `draft` не утекает |
| **TC-API-FLT-008** | Каталог МИРЭА: ни одного пустого title | `len(e["title"].strip()) > 0` для всех |
| **TC-API-FLT-101** | `GET /events` без токена | `401` |
| **TC-API-FLT-102** | `?limit=10000` — out of range | `422` |
| **TC-API-FLT-103** | Битый токен | `401` |

### `tests/api/events/test_event_status_pos.py`, `_neg.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-STA-001** | `draft → published` через POST `/events/{id}/status` | Поле `status = "published"`, событие в каталоге |
| **TC-API-STA-002** | `published → cancelled` — идемпотентно (повтор не падает) | Второй вызов возвращает уже `cancelled`, не 409 |
| **TC-API-STA-101** | Чужой организатор пытается сменить статус | `403` |
| **TC-API-STA-102** | Неизвестное значение статуса | `422` |

### `tests/api/events/test_events_put_method.py` — REST-семантика

SUT использует `PATCH` для частичных правок; `PUT` явно не объявлен.
Гарантия: PUT нигде не выдаёт 200 случайно.

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-PUT-001** | PATCH для частичного апдейта работает | `200` |
| **TC-API-PUT-101..104** | PUT на `/events`, `/events/{id}`, `/auth/login`, `/healthz` | `405 Method Not Allowed` |

### `tests/api/registrations/test_registrations_pos.py`, `_neg.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-REG-001** | `GET /events/{id}/registrations` владельцем — массив | `200`, тип list |
| **TC-API-REG-002** | `?status=confirmed` — только confirmed | Все `status == "confirmed"` |
| **TC-API-REG-003** | Формат кода записи `RG-XXXXXX` | Каждый элемент `re.match(r"^RG-[A-Z0-9]{6}$", code)` |
| **TC-API-REG-101** | Без токена | `401` |
| **TC-API-REG-102** | Чужой организатор | `403` |
| **TC-API-REG-103** | Несуществующее event_id | `404` |

### `tests/api/broadcasts/test_broadcasts_pos.py`, `_neg.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-BRD-001** | `POST /events/{id}/broadcasts` — кол-во доставленных | `200`, `delivered >= 0` |
| **TC-API-BRD-002** | `GET /events/{id}/broadcasts` — история | `200`, list |
| **TC-API-BRD-101** | Чужой организатор | `403` |
| **TC-API-BRD-102** | Пустое сообщение | `422` |
| **TC-API-BRD-103** | История без токена | `401` |

### `tests/api/scan/test_scan_pos.py`, `_neg.py`

`/api/v1/scan` — единственная ручка, доступная сканеру; должна одинаково
отвечать на «несуществующий код» и «не твой код» (защита от user-enumeration
RG-кодов).

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-SCN-001** | Валидный код: первый скан → `ok`, второй → `already_attended` | `status` меняется на «уже был» |
| **TC-API-SCN-101** | Несуществующий код | `not_found` (НЕ 404, чтобы не утекала разница) |
| **TC-API-SCN-102** | Слишком короткий токен | `422` |
| **TC-API-SCN-103** | Без авторизации | `401` |

### `tests/api/stats/test_stats_pos.py`, `_neg.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-STT-001** | `GET /stats` — счётчики (global) | `total_events`, `total_registrations`, `events_published` присутствуют, тип int |
| **TC-API-STT-002** | `GET /events/{id}/stats` — воронка | `confirmed`, `waitlist`, `cancelled`, `attended`, `late_cancelled` |
| **TC-API-STT-101** | global stats без токена | `401` |
| **TC-API-STT-102** | event stats — чужой организатор | `403` |
| **TC-API-STT-103** | event stats несуществующего event | `404` |

### `tests/api/integration/` — `/api/v1/integration/*`

X-API-Key-аутентификация (отдельный поток, не JWT). Поведение: идемпотентный
upsert по `(external_source, external_id)`.

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-INT-001** | `GET /integration/health` с валидным ключом | `200`, источник эхом возвращается |
| **TC-API-INT-002** | `POST /integration/events/sync` одно событие → `created` | `summary.created == 1` |
| **TC-API-INT-003** | Повторный sync того же `external_id` → `updated`, не дубликат | `summary.updated >= 1`, число строк в БД не выросло |
| **TC-API-INT-101** | Без ключа | `401` |
| **TC-API-INT-102** | С невалидным ключом | `401` |
| **TC-API-INT-103** | Пустой батч `events: []` | `422` |
| **TC-API-INT-104** | Пустой `external_id` | `422` |

### `tests/api/security/` — безопасность HTTP-слоя

#### `test_security_headers.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-SEC-001** | `X-Frame-Options: DENY` на админке | заголовок присутствует |
| **TC-API-SEC-002** | `X-Content-Type-Options: nosniff` | присутствует |
| **TC-API-SEC-003** | `Permissions-Policy` запрещает `microphone`, `geolocation` | директивы в заголовке |
| **TC-API-SEC-004** | `Server`-заголовок без версии (`uvicorn/0.32` не светим) | пустой или `mirea-events-bot` |

#### `test_jwt_tampering.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-SEC-101** | Пустой `Authorization` | `401` |
| **TC-API-SEC-102** | `Authorization: Bearer garbage` | `401` |
| **TC-API-SEC-103** | Подменённый payload (правильная структура, чужой sub) | `401` (подпись не сходится) |
| **TC-API-SEC-104** | Просроченный JWT | `401` |
| **TC-API-SEC-105** | Неверная схема (`Basic xxx` вместо `Bearer`) | `401` |
| **TC-API-SEC-106** | Отсутствие заголовка вообще | `401` |

#### `test_pii_leak.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-API-SEC-201** | `/healthz` не содержит секретов в теле/заголовках | regex по `JWT_SECRET`, `DATABASE_URL` — пусто |
| **TC-API-SEC-202** | Публичный каталог не содержит номера телефонов абитуриентов | `re.search(r"\+?7?\d{10}")` пусто |

---

## 🌐 E2E — сценарии целиком

Пробегают весь путь пользователя. **Локально only** — в CI (`qa.yml`)
исключены через `--ignore=tests/e2e`.

### `tests/e2e/test_organizer_full_flow.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-E2E-001** | Организатор: логин → создать event → опубликовать → проверить stats → отменить → проверить stats повторно | На каждом шаге `200`/`201`; статусы и счётчики сходятся со здравым смыслом (после публикации событие появилось в каталоге; после отмены — статус `cancelled`, регистрации помечены `cancelled_by_organizer`). |

### `tests/e2e/test_mirea_real_data_flow.py`

Прогон на **реальных** мероприятиях МИРЭА (загружены `init_project.py` из
`mirea.ru/eventspage/`).

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-E2E-002** | Все импортированные события МИРЭА имеют непустые осмысленные title (не «Без названия», не URL-slug) | Каждый title из snapshot встречается в `/events` |
| **TC-E2E-003** | Полный flow на реальном событии: листинг → детали → запись → отмена | Запись проходит, отмена возвращает место в waitlist (если был) |

---

## 🔗 Integration — «API создал → SPA показал»

`tests/integration/test_api_creates_ui_shows.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-INT-001** | `POST /api/v1/events` — title виден на `/events` | Карточка в React SPA |
| **TC-INT-002** | Publish через API — статус на `/events/{id}` | Бейдж «Опубликовано» |

---

## 🖥️ UI — Playwright (React SPA)

JWT инжектится через `localStorage` (`mirea-auth`) или логин на `/login`.
Cookie/CSRF из Jinja2-админки **не используются**.

### `tests/ui/auth/`

#### `test_login_pos.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-AUTH-001** | Дисклеймер хакатона на `/login` | Текст про неофициальность МАКС |
| **TC-UI-AUTH-002** | Admin логин → `/events` + JWT в localStorage | `mirea-auth` не пуст |
| **TC-UI-AUTH-003** | Organizer логин → `/events` | Без 403 |

#### `test_login_neg.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-AUTH-101** | Пустой email — HTML5 validation | Submit не уходит |
| **TC-UI-AUTH-102** | Неверный пароль | Сообщение об ошибке |
| **TC-UI-AUTH-103** | Unknown email — тот же текст | anti-enumeration |
| **TC-UI-AUTH-104** | `/events` без auth → `/login` | Редирект |

#### `test_logout.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-AUTH-201** | Logout очищает localStorage | Редирект на `/login` |

### `tests/ui/dashboard/`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-DASH-001** | После логина виден список events | `/events`, элементы в DOM |
| **TC-UI-DASH-101** | Анонимный → `/login` | Редирект |

### `tests/ui/events/`

#### `test_events_list.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-LST-001** | Каталог seed-событий на `/events` | >= 1 карточка |
| **TC-UI-LST-002** | Кнопка создания видна | data-testid или аналог |
| **TC-UI-LST-003** | Organizer видит только свои events | multi-tenant |

#### `test_event_crud_pos.py`, `_neg.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-CRD-001** | Создание через форму — событие появляется в списке | После submit URL = list, новая карточка |
| **TC-UI-CRD-101** | capacity > лимита — ошибка валидации | UI или API 422 |
| **TC-UI-CRD-102** | Title < 3 символов — HTML5 блок | Submit не уходит |

#### `test_event_detail_pos.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-DTL-001** | Кнопка «Опубликовать» меняет статус draft → published в карточке | Бэдж статуса обновился |
| **TC-UI-DTL-002** | «Дублировать» создаёт новый event с тем же title и оффсетом даты | На странице нового события подставлен title старого |

#### `test_event_slots_pos.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-SLT-001** | Добавление слота через форму увеличивает счётчик слотов | Счётчик +1 |
| **TC-UI-SLT-101** | Слот с `capacity=0` — HTML5 блок | submit не уходит |

#### `test_broadcast.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-BRD-001** | Форма рассылки без выбранных получателей → отправляет всем зарегистрированным | toast «отправлено» |
| **TC-UI-BRD-101** | Пустое сообщение — HTML5 required блокирует | submit не уходит |

#### `test_export.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-EXP-001** | Экспорт CSV своего event (если кнопка в SPA) | CSV скачивается |

> **Удалено:** `test_wall_pos.py` (стена явки), `test_poster_csv` (Jinja poster routes).

### `tests/ui/organizers/`

#### `test_organizers_pos.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-ORG-001** | Admin открывает `/organizers` | Список без 403 |
| **TC-UI-ORG-002** | Admin создаёт нового организатора через форму | Новый email в списке после submit |
| **TC-UI-ORG-003** | Admin видит кнопки переключения роли | DOM содержит элементы переключения |

#### `test_organizers_neg.py`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-ORG-101** | Анонимный → редирект на login | финальный URL — login |
| **TC-UI-ORG-102** | Organizer (не admin) → `403` или редирект | страница не доступна |

### `tests/ui/scanner/`

| ID | Что проверяем | Ожидаемо |
|----|---------------|----------|
| **TC-UI-SCN-001** | Страница сканера загружается, форма ручного ввода присутствует | элементы в DOM |
| **TC-UI-SCN-101** | Пустой ввод — submit не уходит / показывает ошибку | UI-валидация |
| **TC-UI-SCN-102** | Невалидный QR-формат (не `RG-XXXXXX`) | UI отвергает / сервер `422` |

---

## 🧪 Unit — in-memory тесты SUT

In-memory SQLite, без поднятого сервера. Запуск: `pytest -m unit`.

### `tests/unit/` — бизнес-логика и инварианты

| Файл | Что покрыто |
|------|-------------|
| `test_registration.py` | sign_up, cancel, waitlist promotion, mark_attended, double-cancel идемпотентность |
| `test_slots.py` | capacity per-slot, изоляция waitlist между слотами, sign_up в полный слот → waitlist |
| `test_consent.py` | версионирование согласия, идемпотентность grant, revoke, has_active_consent |
| `test_audit.py` | запись и выборка audit_log, фильтры |
| `test_late_cancel.py` | политики `disallow` и `allow_marked`, `forbidden_late`, `LATE_CANCELLED` статус |
| `test_close_registration.py` | `registration_open`/`can_accept_registrations`, signup после старта |
| `test_registration_code.py` | формат `RG-XXXXXX`, уникальность, отсутствие `0/O/1/I`, регистр |
| `test_scan_max_entries.py` | multi-pass проходы (max_entries 1/2/5/безлимит) |
| `test_cancel_by_organizer.py` | отмена организатором, mark_attended_by_id, waitlist promotion, after-start |

### `tests/unit/` — безопасность и multi-tenancy

| Файл | Что покрыто |
|------|-------------|
| `test_auth.py` | bcrypt, JWT roundtrip, expired/bad tokens, current_organizer dependency |
| `test_api_ownership.py` | `get_owned_event`, admin bypass, foreign organizer 403, missing 404 |
| `test_slot_idor.py` | IDOR через `slot_id` (slot принадлежит чужому event'у) |
| `test_security.py` | rate-limiter sliding window, CSRF dep, security headers |
| `test_regressions_final.py` | 5 P0-регрессий: CSV-injection, race-condition, oracle-mitigation, re-signup reset, XSS в JS-литералах |

### `tests/unit/integration/` — TestClient

| Файл | Что покрыто |
|------|-------------|
| `test_rest_api.py` | healthz/readyz, фильтры events, PII-leak |
| `test_integration_sync.py` | bulk sync X-API-Key |

> **Удалено:** `test_admin_html.py`, `test_landing.py`, `test_poster_csv_*.py` — HTML-админка снята.

### `tests/unit/` — бот и хендлеры

| Файл | Что покрыто |
|------|-------------|
| `test_bot_client.py` | maxapi-обёртка: send_message, get_updates, set/delete webhook, 4xx ошибки, photo upload |
| `test_bot_handlers.py` | consent, ФИО после согласия, per-event notif, deeplink, слоты |
| `test_bot_handlers_views.py` | menu callback, unknown text → UNKNOWN, форматирование карточек |

### `tests/unit/` — утилиты фреймворка

| Файл | Что покрыто |
|------|-------------|
| `test_utils_assertions.py` | `assert_status`, `assert_problem_details`, `assert_iso_8601`, `assert_event_shape`, `assert_no_secret_leak`, `assert_pagination_meta`, `assert_subset` |
| `test_utils_wait_retry.py` | `wait_for`, `wait_until_equal`, `retry` с DEFAULT_RETRY_STATUSES |
| `test_utils_time_diff.py` | `in_minutes/in_hours/in_days`, `tomorrow_at`, `split_into_slots`, `index_by`, `diff_collections` |
| `test_utils_schema_check.py` | `check_keys`, `check_types`, `check_enum`, `check_event_response` |
| `test_bug_report.py` | рендер MD-репорта, `from_pytest_item`, traceback truncation, env-метаданные |
| `test_timings.py` | `TestTiming`, `dump_json`, `dump_markdown` с top-N slow + failed |
| `test_mirea_adapter.py` | snapshot loader + live parser (JSON-LD + OpenGraph + fallback) |
| `test_property_event_dates.py` | hypothesis-генератор дат событий, инвариант starts_at < ends_at |
| `test_perf_snapshot_load.py` | pytest-benchmark на загрузке snapshot и сериализации в EventSyncItem |

---

## 📊 Маркировка по ролям

| Роль теста | Какой стенд нужен |
|------------|-------------------|
| `api` | SUT на `:8080`, БД с seed (`make bootstrap`) |
| `ui` + `smoke` | + установленный chromium через `playwright install` |
| `integration` | SUT + БД (общая для API и UI) |
| `e2e` | SUT + seed; **не в CI** |

## 🐞 Авто-bug-report

Падение любого теста запускает `utils/bug_report.py`, который пишет
`reports/bugs/<test_id>.md` с:

- именем кейса, маркерами, временем;
- traceback'ом;
- путями к скриншоту, видео, trace.zip;
- `env`-метаданными (Python, OS, Base-URL);
- repro-командой (`pytest <nodeid>`).

См. также: `docs/architecture.md` (контракт слоёв) и `docs/best-practices.md`
(чек-листы качества).
