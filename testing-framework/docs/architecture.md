# Архитектура testing-framework для mirea-events-bot

Документ описывает архитектурное решение для black-box тестового
фреймворка над SUT `mirea-events-bot` (REST API + админ-UI). Любые отклонения
от дизайна — через PR с обоснованием.

---

## 1. Обзор

testing-framework — внешний автоматизированный тестовый комплекс над
FastAPI-приложением `mirea-events-bot` (REST API `/api/v1/*` и React SPA
`/login`, `/events`, …). Тестирование — строго чёрный ящик: только HTTP
через `httpx` и UI через `Playwright`. Импорт из `app/...` в **api/ui**
тестах запрещён (unit-слой — исключение: in-memory TestClient).

Что решает фреймворк:

- проверка REST-контракта `/api/v1/*` (pos + neg по доменам);
- проверка React SPA: логин, список events, CRUD, сканер, organizers (admin);
- интеграционные кейсы «API создал → UI показал»;
- E2E-сценарии организатора — **только локально**, в CI отключены;
- регрессионная сетка: `smoke`, `regression`, `api`, `ui`, `unit`.

Что фреймворк **не** делает: не тестирует MAX-бот (это покрыто 303
unit-тестами в самом проекте), не использует моки внутренней БД, не
читает исходники SUT.

---

## 2. Слоистая структура

Поток вызова от теста к SUT идёт строго сверху вниз. Каждый слой
имеет один публичный контракт и не знает о слое выше.

```
+--------------------------------------------------------------+
|  tests/         pytest-функции, assert-ы, маркеры             |
+--------------------------------------------------------------+
|  steps/         бизнес-шаги (SOM) — оперируют POM и API       |
+--------------------------------------------------------------+
|  pages/         POM-классы              core/api_client.py    |
|  components/    переиспользуемые UI-блоки                     |
+--------------------------------------------------------------+
|  factories/     factory-boy + Faker(ru_RU)                    |
|  fixtures/      pytest-фикстуры (DI)                          |
+--------------------------------------------------------------+
|  config/        Settings (Singleton), URL builders             |
|  core/          логгер, исключения, auth helper                |
+--------------------------------------------------------------+
                           |
                           v
                   SUT (FastAPI :8080)
```

Правила зависимостей:

- `tests/` → `steps/`, `factories/`, фикстуры. Прямой вызов POM или
  `ApiClient` из теста — допустим только для тривиальных smoke.
- `steps/` → `pages/`, `core/api_client.py`, `factories/`.
- `pages/` → `core/`, `config/`. Не знают про `steps/` и `factories/`.
- `core/api_client.py` → `httpx`, `config/`. Ничего из вышестоящих
  слоёв не импортирует.
- `factories/` → `config/`, `Faker`. Не знают про `pages/`.
- `config/` — лист зависимостей: без зависимостей внутри проекта.

---

## 3. Layout проекта (дерево файлов)

```
testing-framework/
|-- README.md                       # запуск с нуля, на русском
|-- pyproject.toml                  # single source of truth: deps, pytest, ruff, mypy
|-- requirements.txt                # pin-версии для CI
|-- requirements-dev.txt            # ruff, mypy, types
|-- .env.example                    # шаблон, коммитим
|-- .env                            # реальные значения, gitignore
|-- .gitignore
|-- conftest.py                     # корневой conftest: глобальные фикстуры
|
|-- config/
|   |-- __init__.py
|   |-- settings.py                 # Settings (pydantic-settings) + Singleton
|   |-- urls.py                     # URL builder-ы (api_url, admin_url)
|   `-- credentials.py              # seed-учётки (демо, не секреты)
|
|-- core/
|   |-- __init__.py
|   |-- api_client.py               # ApiClient: httpx обёртка с auth state
|   |-- auth_helper.py              # login_api / login_ui хелперы
|   |-- logger.py                   # настройка logging + structlog-friendly
|   |-- exceptions.py               # ApiError, UiError, ConfigError
|   `-- artifacts.py                # пути для screenshot/trace/HAR
|
|-- pages/                          # POM
|   |-- __init__.py
|   |-- base_page.py                # BasePage: page, ожидания, screenshot
|   |-- login_page.py
|   |-- dashboard_page.py
|   |-- events_list_page.py
|   |-- event_detail_page.py
|   |-- event_form_page.py
|   |-- scanner_page.py
|   |-- organizers_page.py
|   `-- components/
|       |-- __init__.py
|       |-- flash_message.py        # success / error / warn баннеры
|       |-- nav_bar.py              # боковая навигация
|       `-- csrf_form.py            # legacy; SPA не использует CSRF

|-- steps/                          # SOM
|   |-- __init__.py
|   |-- ui/
|   |   |-- __init__.py
|   |   |-- auth_steps.py           # login_as_admin/organizer, logout
|   |   |-- event_steps.py          # create_event, publish, cancel
|   |   `-- scanner_steps.py        # scan_manual
|   `-- api/
|       |-- __init__.py
|       |-- auth_steps.py           # get_token
|       |-- event_steps.py          # create_event_via_api, change_status
|       |-- registration_steps.py   # list_registrations, find_by_code
|       |-- broadcast_steps.py
|       |-- scan_steps.py
|       |-- stats_steps.py
|       `-- integration_steps.py    # sync, health
|
|-- factories/
|   |-- __init__.py
|   |-- event_factory.py            # EventFactory + Trait-ы
|   |-- integration_event_factory.py
|   |-- registration_factory.py     # для будущих расширений
|   `-- user_factory.py             # для seed/импорта учёток
|
|-- fixtures/                       # модули, импортируются в conftest
|   |-- __init__.py
|   |-- api_fixtures.py             # api_client, auth_token_admin, ...
|   |-- ui_fixtures.py              # browser, context, page, traced_context
|   |-- auth_fixtures.py            # logged_in_admin_page, logged_in_organizer
|   |-- data_fixtures.py            # seed_loaded, created_event
|   `-- sut_fixtures.py             # ожидание /readyz, опциональный spawn uvicorn
|
|-- data/                           # gitignore; примеры в data/.example/
|   `-- .gitkeep
|
|-- tests/
|   |-- conftest.py                 # импорт фикстур из ../fixtures/*
|   |-- api/
|   |   |-- conftest.py
|   |   |-- auth/
|   |   |   |-- test_login_pos.py
|   |   |   `-- test_login_neg.py
|   |   |-- health/
|   |   |   |-- test_health_pos.py
|   |   |   `-- test_health_neg.py
|   |   |-- events/
|   |   |   |-- test_events_crud_pos.py
|   |   |   |-- test_events_crud_neg.py
|   |   |   |-- test_events_filters_pos.py
|   |   |   |-- test_events_filters_neg.py
|   |   |   |-- test_event_status_pos.py
|   |   |   `-- test_event_status_neg.py
|   |   |-- registrations/
|   |   |   |-- test_registrations_pos.py
|   |   |   `-- test_registrations_neg.py
|   |   |-- broadcasts/
|   |   |   |-- test_broadcasts_pos.py
|   |   |   `-- test_broadcasts_neg.py
|   |   |-- scan/
|   |   |   |-- test_scan_pos.py
|   |   |   `-- test_scan_neg.py
|   |   |-- stats/
|   |   |   |-- test_stats_pos.py
|   |   |   `-- test_stats_neg.py
|   |   `-- integration/
|   |       |-- test_integration_sync_pos.py
|   |       |-- test_integration_sync_neg.py
|   |       `-- test_integration_health.py
|   |-- ui/
|   |   |-- conftest.py
|   |   |-- auth/
|   |   |   |-- test_login_pos.py    # обязательно по требованию заказчика
|   |   |   |-- test_login_neg.py
|   |   |   `-- test_logout.py
|   |   |-- dashboard/
|   |   |   `-- test_dashboard_pos.py
|   |   |-- events/
|   |   |   |-- test_event_crud_pos.py
|   |   |   `-- test_event_crud_neg.py
|   |   `-- scanner/
|   |       `-- test_scanner_pos.py
|   |-- integration/
|   |   `-- test_api_creates_ui_shows.py
|   `-- e2e/
|       `-- test_organizer_full_flow.py
|
|-- docs/
|   |-- architecture.md             # этот файл
|   |-- best-practices.md
|   |-- writing-tests.md            # гайд по добавлению тестов
|   `-- troubleshooting.md          # типичные ошибки и решения
|
`-- reports/                        # gitignore содержимое; .gitkeep
    |-- .gitkeep
    |-- allure-raw/                 # gitignore
    |-- allure-report/              # gitignore
    |-- html/                       # pytest-html
    |-- playwright/                 # screenshots, traces, videos
    `-- junit.xml
```

Обоснование решений:

- Иерархия `tests/api/<domain>/test_*_{pos,neg}.py` — выполняет
  буквальное требование заказчика «pos + neg отдельно» и даёт
  гранулярный отбор: `pytest tests/api/auth -m smoke`.
- `fixtures/` отдельной директорией (а не только в conftest) —
  переиспользование фикстур API между разными conftest без
  копипасты.
- `pages/components/` — переиспользуемые UI-блоки (flash, nav, csrf),
  чтобы не дублировать селекторы между страницами.

---

## 4. Слои в деталях

### 4.1 Config (`config/settings.py`)

Singleton через `@lru_cache` поверх `pydantic-settings.BaseSettings`.
Источники в порядке приоритета: env-vars > `.env` > defaults.

Контракт класса:

```python
class Settings(BaseSettings):
    # SUT
    base_url: AnyHttpUrl                    # http://localhost:8080
    sut_mode: Literal["external", "spawn"]  # см. п.10.2
    sut_ready_timeout: int                  # сек, ожидание /readyz

    # Учётки
    admin_email: EmailStr
    admin_password: SecretStr
    organizer_email: EmailStr               # iptip@mirea.ru по умолчанию (из init_project)
    organizer_password: SecretStr
    second_organizer_email: EmailStr        # qa-second@mirea.ru — для owner-scope neg
    second_organizer_password: SecretStr

    # Интеграция
    integration_api_key: SecretStr | None   # формат source.random

    # Браузер
    browser: Literal["chromium", "firefox", "webkit"]  # default chromium
    headless: bool
    slow_mo_ms: int
    viewport_width: int
    viewport_height: int

    # Таймауты
    http_timeout_s: float                   # 10.0
    ui_default_timeout_ms: int              # 5000

    # Артефакты
    artifacts_dir: Path                     # reports/playwright
    capture_video: bool
    capture_trace: bool
    capture_har: bool

    # Логи
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QA_",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

`config/urls.py` — функции-билдеры:

```python
def api_url(path: str) -> str: ...
def admin_url(path: str) -> str: ...
def login_page_url() -> str: ...
```

`config/credentials.py` — статические dataclass-ы под seed-учётки
(не секреты — те же значения, что и в `app/cli/init_project.py`).
Используются как fallback и как источник для параметризации
«логин под admin / под organizer».

### 4.2 Core / ApiClient (`core/api_client.py`)

Класс с состоянием (токен), один экземпляр на сессию или один на
пользователя. Возвращает сырой `httpx.Response`, валидация схем — на
стороне Steps (через `pydantic`-модели), чтобы тест мог проверить и
`response.status_code`, и payload.

Контракт:

```python
class ApiClient:
    """HTTP-клиент SUT поверх httpx.

    Хранит JWT и/или X-API-Key. Логирует каждый запрос-ответ.
    Не валидирует схему — это задача вызывающего кода (Steps/тесты).
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        token: str | None = None,
        api_key: str | None = None,
    ) -> None: ...

    @property
    def token(self) -> str | None: ...

    def authenticate(self, email: str, password: str) -> str:
        """POST /api/v1/auth/login. Возвращает access_token, сохраняет в self.token."""

    def with_token(self, token: str) -> "ApiClient":
        """Возвращает копию клиента с заданным токеном (для DI в тестах)."""

    def with_api_key(self, api_key: str) -> "ApiClient": ...

    # Узкие методы (ISP): не один request(), а несколько по семантике.
    def get(self, path: str, *, params: dict | None = None, headers: dict | None = None) -> httpx.Response: ...
    def post_json(self, path: str, *, json: dict, headers: dict | None = None) -> httpx.Response: ...
    def patch_json(self, path: str, *, json: dict, headers: dict | None = None) -> httpx.Response: ...
    def put_json(self, path: str, *, json: dict, headers: dict | None = None) -> httpx.Response: ...
    def delete(self, path: str, *, headers: dict | None = None) -> httpx.Response: ...
    def close(self) -> None: ...

    # context manager
    def __enter__(self) -> "ApiClient": ...
    def __exit__(self, *exc: object) -> None: ...
```

Внутри:

- единый `httpx.Client(base_url=..., timeout=...)`;
- инжект `Authorization: Bearer ...` если есть `self.token` и в
  `headers` нет своего `Authorization`;
- инжект `X-API-Key` аналогично;
- логирование method/path/status/elapsed на INFO; payload — на DEBUG
  (с маскированием `password`/`access_token`).

### 4.3 Pages — POM (`pages/`)

`BasePage` — общая база, инкапсулирует `playwright.sync_api.Page`,
тайминги и навигацию:

```python
class BasePage:
    """Базовый POM. Не знает про бизнес-логику логина."""

    URL_PATH: str = ""  # переопределяется наследниками

    def __init__(self, page: Page, base_url: str) -> None:
        self._page = page
        self._base_url = base_url

    @property
    def page(self) -> Page: return self._page

    def open(self) -> "BasePage":
        self._page.goto(self._base_url.rstrip("/") + self.URL_PATH)
        return self

    def wait_for_url(self, pattern: str | re.Pattern[str], timeout: int = 5000) -> None: ...
    def screenshot(self, name: str) -> Path: ...
    def current_url(self) -> str: ...
```

`LoginPage` (пример контракта):

```python
class LoginPage(BasePage):
    URL_PATH = "/login"

    _email_input = '[data-testid="input-email"]'
    _password_input = '[data-testid="input-password"]'
    _submit_button = '[data-testid="btn-login"]'
    _error_banner = '[data-testid="login-error"]'

    def fill_email(self, value: str) -> "LoginPage": ...
    def fill_password(self, value: str) -> "LoginPage": ...
    def submit(self) -> None: ...
    def get_error_text(self) -> str | None: ...
    def is_displayed(self) -> bool: ...
```

Селекторы — из React SPA (`data-testid` где возможно). Fallback —
role/name-based селекторы, не CSS-классы Tailwind.

Правила POM:

- Локаторы — приватные атрибуты класса (`_email_input`), никогда не
  всплывают в Steps/тестах.
- Один метод = одно действие или одно чтение состояния. Методы-сеттеры
  возвращают `self` для chaining; методы перехода возвращают новый
  Page-объект (`submit() -> DashboardPage` — допустимо для финальных
  переходов с гарантированным редиректом).
- В POM **запрещены** `assert`-ы. Состояние возвращается, проверяется
  снаружи.
- Конструктор принимает `Page` и `base_url`, не делает `goto`.
  Отдельный `open()`.
- Если страница имеет компоненты (flash, nav-bar, csrf-form) — они
  возвращаются как объекты из соответствующих свойств (`page.flash`,
  `page.nav`).

### 4.4 Steps — SOM (`steps/`)

Шаги — бизнес-операции. Тест читается как сценарий: «логин как
организатор → создать мероприятие → опубликовать → проверить
статистику». Шаги композируют POM и/или `ApiClient`, но не оба сразу
(UI-шаги работают через POM, API-шаги — через клиент).

Пример UI-шага:

```python
def login_as_organizer(page: Page, settings: Settings) -> DashboardPage:
    """Логин под seed-организатором. Возвращает DashboardPage в стейте 'после редиректа'."""
    login = LoginPage(page, str(settings.base_url)).open()
    login.fill_email(settings.organizer_email)
    login.fill_password(settings.organizer_password.get_secret_value())
    login.submit()
    dashboard = DashboardPage(page, str(settings.base_url))
    dashboard.wait_for_url(re.compile(r"/events/?$"))
    return dashboard
```

Пример API-шага:

```python
def create_event(api: ApiClient, payload: dict) -> dict:
    """POST /api/v1/events. Возвращает JSON-тело при 201, иначе бросает ApiError."""
    resp = api.post_json("/api/v1/events", json=payload)
    if resp.status_code != 201:
        raise ApiError(resp)
    return resp.json()
```

Шаги **не делают assert-ы**, кроме защитных (raise ApiError при
неожиданном статусе в pos-сценарии). Это позволяет переиспользовать
шаг и в neg-тестах, где ожидается ошибка (там тест вызывает
`api.post_json` напрямую или ловит исключение).

### 4.5 Factories (`factories/`)

`factory_boy` + `Faker("ru_RU")`. Каждая фабрика возвращает словарь,
готовый для POST в SUT. Builder-паттерн через Trait-ы и метод
`.build_payload()`:

```python
class EventFactory(factory.DictFactory):
    title = factory.Faker("sentence", nb_words=4, locale="ru_RU")
    description = factory.Faker("paragraph", locale="ru_RU")
    event_type = "open_day"
    capacity = factory.Faker("random_int", min=20, max=200)
    duration_minutes = 90
    format = "onsite"
    starts_at = factory.LazyFunction(
        lambda: (datetime.now() + timedelta(days=14)).isoformat(timespec="seconds")
    )

    class Params:
        published = factory.Trait()  # маркер; статус ставится отдельным шагом
        online = factory.Trait(format="online", meeting_url="https://meet.example/room")
```

Используется как:

```python
payload = EventFactory.build()                    # дефолт
payload = EventFactory.build(capacity=1)          # с явным значением
payload = EventFactory.build(online=True)         # trait
```

`IntegrationEventFactory` — генерирует один `EventSyncItem` с
уникальным `external_id` (`uuid4().hex`). Для тестов идемпотентности
фабрика умеет «зафиксировать» `external_id` через параметр.

Builder-обёртка для сложных кейсов (опционально, если простой
`build(**kwargs)` тесен):

```python
class EventBuilder:
    def __init__(self) -> None: self._data = EventFactory.build()
    def with_capacity(self, n: int) -> "EventBuilder": self._data["capacity"] = n; return self
    def in_the_past(self) -> "EventBuilder": ...
    def online(self) -> "EventBuilder": ...
    def build(self) -> dict: return dict(self._data)
```

### 4.6 Fixtures — DI (`fixtures/` + `conftest.py`)

Иерархия conftest:

| Уровень            | Что объявляет                                              |
|--------------------|------------------------------------------------------------|
| `conftest.py` (корень testing-framework) | `settings`, `logger`, артефакт-директории; импорт фикстур из `fixtures/*` через `pytest_plugins`. |
| `tests/conftest.py`        | `sut_ready` (ждёт `/readyz`), `seed_loaded` (запускает seed один раз). |
| `tests/api/conftest.py`    | `api_client`, `auth_token_admin`, `auth_token_organizer`, `api_as_admin`, `api_as_organizer`, `api_as_second_organizer`, `api_as_integration`. |
| `tests/ui/conftest.py`     | `browser`, `context_factory`, `traced_context`, `page`, `logged_in_admin_page`, `logged_in_organizer_page`. |

Scope-плитка:

| Scope     | Фикстура                                                        |
|-----------|------------------------------------------------------------------|
| `session` | `settings`, `sut_ready`, `seed_loaded`, `playwright`, `browser`.  |
| `module`  | `module_event` (создаваемое одним модулем, не каждым тестом).     |
| `function`| `api_client`, `context`, `page`, `event_factory_with_cleanup`.    |

Авто-фикстура `_cleanup_created_events` — удаляет всё, что
зарегистрировано через `event_factory_with_cleanup`, через `DELETE
/api/v1/events/{id}` в teardown.

Авто-фикстура `_capture_on_failure` — в `pytest_runtest_makereport`
снимает скриншот, останавливает Playwright tracing, сохраняет
`trace.zip` и прикрепляет к Allure.

### 4.7 Tests (`tests/`)

Правила:

- Один тест — один сценарий. Никаких многошаговых assert-портянок
  без логических разделителей.
- Pos и neg — в раздельных файлах (требование заказчика).
- Параметризация — для data-driven (например, neg-логин с 4 разными
  невалидными payload-ами в одном тесте).
- Каждый тест помечен как минимум двумя маркерами: «область» (`api`
  / `ui` / `e2e` / `integration`) и «тип» (`pos` / `neg`). Дополнительно
  `smoke` / `slow` где уместно.

Пример:

```python
@pytest.mark.api
@pytest.mark.pos
@pytest.mark.smoke
def test_login_admin_returns_token(api_client: ApiClient, settings: Settings) -> None:
    resp = api_client.post_json(
        "/api/v1/auth/login",
        json={"email": settings.admin_email,
              "password": settings.admin_password.get_secret_value()},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 28800
    assert body["access_token"]
```

---

## 5. Принципы качества

### 5.1 SOLID — конкретно

- **S (SRP).** `BasePage` не знает про логин — это `LoginPage`.
  `ApiClient` отвечает только за HTTP, не за валидацию схем (этим
  занимается Steps). Фабрика отвечает только за payload, не за
  POST.
- **O (OCP).** Добавление новой страницы = новый класс-наследник
  `BasePage`. Существующие POM не меняются. Добавление нового
  эндпоинта в API-Step — новая функция в `steps/api/<domain>_steps.py`.
- **L (LSP).** Все Page-классы соблюдают контракт `BasePage`
  (`open()`, `screenshot()`, `current_url()`). Подкласс не ужесточает
  предусловия и не ослабляет постусловия.
- **I (ISP).** `ApiClient` имеет узкие методы (`get`, `post_json`,
  `patch_json`, `put_json`, `delete`) вместо одного `request(method,
  path, ...)`. Тест зависит только от тех методов, которые ему
  реально нужны.
- **D (DIP).** Тесты зависят от фикстур (`api_as_admin`,
  `logged_in_organizer_page`), не от конструкторов `ApiClient` /
  `LoginPage` напрямую. Фикстуры инкапсулируют конкретные реализации.

### 5.2 DRY / KISS

- **DRY:** общие селекторы — в Page, не в тестах. Общая логика логина —
  в Steps, не в каждом тесте. Учётки — в `config/credentials.py`,
  не разбросаны по тестам.
- **KISS:** один тип фабрики на сущность (Event, IntegrationEvent,
  User). Не делаем абстрактные фабрики фабрик. `ApiClient` — синхронный,
  без асинхронной обёртки (SUT снаружи async-ность не требует, тесты
  читаются проще). Async включаем только если профайл покажет
  необходимость.
- **Граница DRY:** дублирование payload-литералов между pos- и
  neg-тестами иногда полезнее, чем общая фабрика — тест должен
  читаться без переходов в helper-ы. Решается по месту, ситуативно.

### 5.3 Тест-дизайн техники — где применены

| Техника                         | Где                                              |
|---------------------------------|--------------------------------------------------|
| Page Object Model               | `pages/`, `pages/components/`                    |
| Step Object Model               | `steps/ui/`, `steps/api/`                        |
| Singleton                       | `config/settings.py` (`@lru_cache get_settings`) |
| Factory                         | `factories/event_factory.py` и др.               |
| Builder                         | `factories/*` — `Trait`-ы + опциональный `EventBuilder.with_xxx().build()` |
| Dependency Injection            | pytest-fixtures (`api_client`, `page`, `settings`) |
| Layered architecture            | config → core → pages/steps → factories → tests   |
| Strategy (вспом.)               | `sut_mode` в `sut_fixtures.py` (external / spawn) |
| Context manager                 | `ApiClient.__enter__/__exit__`, Playwright trace  |

---

## 6. Покрытие — что и как

### 6.1 API (`/api/v1/*`)

Покрытие по доменам: `tests/api/{auth,health,events,registrations,broadcasts,scan,stats,integration,security,audit,organizers,slots}/`.
Каждый домен — `test_*_pos.py` / `test_*_neg.py`. IDOR: organizer не видит
чужой `GET /events/{id}` → 403 (TC-API-EVT-104).

### 6.2 UI (React SPA)

`tests/ui/auth/` — логин `/login`, JWT в `localStorage` (`mirea-auth`):

- `test_login_pos.py`:
  - дисклеймер хакатона на странице логина;
  - admin → редирект `/events`, token в localStorage;
  - organizer → `/events`.
- `test_login_neg.py`:
  - неверный пароль — текст ошибки;
  - unknown email — тот же текст (anti-enumeration);
  - HTML5 validation на пустом email;
  - защищённый URL без auth → `/login`.
- `test_logout.py`:
  - кнопка «Выйти» очищает auth и редиректит на `/login`.

`tests/ui/dashboard/` — после логина виден список events (`/events`).

`tests/ui/events/` — CRUD, слоты, рассылки, export (если есть в SPA).

`tests/ui/organizers/` — только admin (`/organizers`).

`tests/ui/scanner/` — `/events/{id}/scanner`.

Страница wall и тесты `test_wall_pos.py` **удалены** вместе с фичей.

### 6.3 Integration

`tests/integration/test_api_creates_ui_shows.py`:

- `POST /api/v1/events` (draft) → UI `/events` показывает карточку;
- publish через API → бейдж «Опубликовано» на `/events/{id}`;
- integration sync → событие видно в SPA.

### 6.4 E2E

`tests/e2e/` — полные сценарии (organizer flow, real MIREA data).
**Не гоняются в CI** (`pytest --ignore=tests/e2e` в `qa.yml`): нужен
стабильный seed, дольше по времени, риск засорить БД.

---

## 7. Конфигурация и запуск

### 7.1 Локально с нуля

```
# 1) Поднимаем SUT
cd C:\Users\Valerii\Desktop\mirea-events-bot
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m app.cli.init_project
uvicorn app.main:app --host 0.0.0.0 --port 8080

# 2) В отдельной консоли — testing-framework
cd C:\Users\Valerii\Desktop\mirea-events-bot\testing-framework
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt
playwright install --with-deps chromium
copy .env.example .env
# отредактировать .env при необходимости

# 3) Запуск
pytest -m smoke
pytest -m "api and pos"
pytest -m e2e --headed
pytest --alluredir=reports/allure-raw --html=reports/html/report.html --junitxml=reports/junit.xml
allure generate reports/allure-raw -o reports/allure-report --clean
```

### 7.2 Переменные окружения (`.env.example`)

Минимальный набор:

```
QA_BASE_URL=http://localhost:8080
QA_SUT_MODE=external
QA_SUT_READY_TIMEOUT=30

QA_ADMIN_EMAIL=admin@mirea.ru
QA_ADMIN_PASSWORD=admin12345
QA_ORGANIZER_EMAIL=iptip@mirea.ru
QA_ORGANIZER_PASSWORD=organizer12345
QA_SECOND_ORGANIZER_EMAIL=qa-second@mirea.ru
QA_SECOND_ORGANIZER_PASSWORD=organizer12345

QA_INTEGRATION_API_KEY=

QA_BROWSER=chromium
QA_HEADLESS=true
QA_SLOW_MO_MS=0
QA_VIEWPORT_WIDTH=1366
QA_VIEWPORT_HEIGHT=768

QA_HTTP_TIMEOUT_S=10
QA_UI_DEFAULT_TIMEOUT_MS=5000

QA_ARTIFACTS_DIR=reports/playwright
QA_CAPTURE_VIDEO=true
QA_CAPTURE_TRACE=true
QA_CAPTURE_HAR=false

QA_LOG_LEVEL=INFO
```

### 7.3 SUT lifecycle

Реализуем два режима:

- `QA_SUT_MODE=external` (default) — фикстура `sut_ready` опрашивает
  `GET /api/v1/readyz`, ждёт до `QA_SUT_READY_TIMEOUT` секунд.
- `QA_SUT_MODE=spawn` — фикстура `sut_ready` стартует `uvicorn
  app.main:app --port 8080` через `subprocess.Popen`, ждёт `/readyz`,
  гасит в teardown сессии. Полезно для CI без Docker.

Режим `docker` оставляем на будущее (если потребуется).

---

## 8. CI-ready

### 8.1 Маркеры (объявляются в `pyproject.toml`)

```
[tool.pytest.ini_options]
markers = [
    "smoke: критический минимум, < 30 сек суммарно",
    "regression: полный набор для регрессии",
    "api: HTTP-тесты под /api/v1/*",
    "ui: Playwright-тесты React SPA (/login, /events, …)",
    "integration: связка API + UI или /api/v1/integration/*",
    "e2e: сквозные пользовательские сценарии",
    "pos: положительный сценарий",
    "neg: негативный сценарий",
    "slow: > 5 сек или зависит от rate-limit/таймаутов",
    "serial: нельзя гонять параллельно с другими тестами",
]
addopts = "-ra --strict-markers --strict-config"
```

### 8.2 Команды

- `pytest -m smoke` — < 30 сек, гонит smoke-сабсет в CI на каждый push.
- `pytest -m "api and not slow"` — API без rate-limit-кейсов.
- `pytest -m "ui and pos"` — позитивные UI.
- `pytest -m e2e --headed` — локальная отладка E2E.
- `pytest -m regression -n auto` — параллельный регресс через xdist
  (по умолчанию последовательно, активируется флагом `-n auto`; тесты,
  трогающие глобальный seed, помечены маркером `serial`).
- `pytest --collect-only -m smoke` — проверка discovery.

### 8.3 GitHub Actions (`.github/workflows/qa.yml`)

Jobs:

1. **frontend-build** — `npm ci && npm run build`.
2. **lint** — ruff + mypy testing-framework.
3. **unit** — `pytest -m unit -n auto` (in-memory SQLite в unit-слое).
4. **api-and-smoke** — bootstrap backend, uvicorn `:8080`, Playwright,
   `pytest -m "api or (ui and smoke)" --ignore=tests/e2e`.

E2E и `--ignore=tests/unit` в api-job — чтобы не дублировать unit и не
тянуть e2e в CI. UI smoke **без xdist** (Playwright + session fixtures).

Артефакты: `sut.log`, Allure raw, pytest-html, playwright traces.

---

## 9. Отчётность

### 9.1 Allure (основной отчёт)

`allure-pytest` — каждый шаг (`steps/`) оборачивается в
`@allure.step("Логин как организатор")`. Атрибуты: `epic`, `feature`,
`story`, `severity`. Прикрепления при failure: screenshot, trace,
HAR, request/response API.

### 9.2 pytest-html (резервный)

Однофайловый отчёт `reports/html/report.html` — отдаётся «ссылкой»
без необходимости иметь allure CLI. Уровень детализации — базовый.

### 9.3 JUnit XML

`reports/junit.xml` — для импорта в TeamCity / GitHub Actions
test-summary.

### 9.4 Скриншоты, traces, HAR

Через autouse fixture в корневом conftest + хук
`pytest_runtest_makereport`:

```python
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        # достаём page из request.node.funcargs если есть
        # делаем screenshot, останавливаем trace, прикрепляем
```

Артефакты по умолчанию — в `reports/playwright/<test_name>/`.

---

## 10. Ключевые архитектурные решения

| #  | Вопрос                                            | Решение                                                                                                                            |
|----|---------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| 1  | Расположение фреймворка                            | Внутри проекта, директория `testing-framework/` рядом с `app/`. CI видит SUT и тесты в одном репо; нет нужды синхронизировать `.env` между репозиториями. |
| 2  | Запуск SUT для тестов                              | Два режима: `QA_SUT_MODE=external` (default — ждём `/readyz`) и `QA_SUT_MODE=spawn` (фикстура поднимает uvicorn). Docker — позже. |
| 3  | Параллелизм                                        | Первая итерация — последовательно. `pytest-xdist` установлен, активируется флагом `-n auto`. Тесты, трогающие глобальный seed, помечаем `@pytest.mark.serial` и исключаем из параллельного прогона. |
| 4  | `pos` vs `neg`: файлы или маркеры                  | **И то, и другое.** Отдельные файлы (`test_*_pos.py` / `test_*_neg.py`) — буквальное требование заказчика. Маркеры `pos`/`neg` — для выбора через `-m`. |
| 5  | Регистрации через API                              | Seed-only (read-only тесты). `POST /api/v1/integration/events/sync` создаёт события, но не регистрации. Не модифицируем prod-код ради test-only ручки. |
| 6  | Сценарии MAX-бота                                  | Unit в `tests/unit/test_bot_*.py`. Black-box e2e бота — out of scope. |
| 7  | Auth SPA                                           | JWT в localStorage; logout через UI-кнопку, не CSRF-form. |
| 8  | Версия Playwright и chromium                       | Pin-им только pip-версию `playwright==1.48.0` (Playwright сам пин-ит совместимый chromium). В CI — `playwright install --with-deps chromium`. |
| 9  | Лицензия и `CONTRIBUTING.md`                       | MIT (как у SUT). `CONTRIBUTING.md` — минимальный, описывает запуск тестов и стиль (ruff, mypy). |
| 10 | Структура pos/neg в одном домене                   | Иерархическая: `tests/api/<domain>/test_*_{pos,neg}.py`. Даёт гранулярный отбор: `pytest tests/api/auth -m smoke`. |

---

## 11. Правила изменений архитектуры

Допускаются мелкие правки без согласования:

- именах конкретных методов внутри POM (например, `fill_email` vs
  `enter_email`) — фиксируем в docstring/коммитe;
- наборе Trait-ов фабрик (можно добавить новые по мере необходимости);
- внутренней реализации `ApiClient` (логирование, retry-логика) — но
  публичный контракт класса не меняется.

Что **не делаем** без согласования:

- не переименовываем слои и директории;
- не объединяем `pages/` и `steps/`;
- не делаем `ApiClient` асинхронным;
- не убираем разделение pos/neg файлов;
- не добавляем в SUT test-only ручки.

Все код-комментарии и docstring-и — на русском, имена — на английском,
без AI-style фраз (см. `docs/best-practices.md`, секция «Анти-AI чеклист»).
