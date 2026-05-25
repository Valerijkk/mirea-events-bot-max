# Best practices применённые в фреймворке

Документ — компаньон `architecture.md`. Здесь — какие практики мы
применяем и **где конкретно** их искать в кодовой базе. Чек-лист
соответствия для разработчика.

---

## 1. OOP

| Где                                   | Как используем                                                                 |
|---------------------------------------|--------------------------------------------------------------------------------|
| `pages/base_page.py`                  | `BasePage` — общий базовый класс с навигацией, ожиданиями, скриншотами.        |
| `pages/*.py`                          | Наследники `BasePage` (LoginPage, DashboardPage, EventFormPage и т.д.).        |
| `pages/components/*.py`               | Композиция: `LoginPage.flash` возвращает `FlashMessage`-объект.                |
| `core/api_client.py`                  | `ApiClient` — класс с состоянием (токен, base_url, session).                   |
| `core/api_client.py`                  | Context manager (`__enter__`/`__exit__`) — корректное закрытие httpx-сессии.   |
| `factories/event_factory.py`          | `EventFactory(factory.DictFactory)` + `EventBuilder` для сложных кейсов.       |
| `core/exceptions.py`                  | Иерархия `QaError → ApiError, UiError, ConfigError`.                           |

Принципы:

- Инкапсуляция: селекторы — приватные атрибуты класса, токен внутри
  `ApiClient` — приватный.
- Полиморфизм: все Page-классы взаимозаменяемы там, где принимается
  `BasePage` (например, `screenshot_on_failure`).
- Композиция > наследование: компоненты UI (`FlashMessage`, `NavBar`)
  не наследуют от `BasePage`, а получают `Page` через конструктор.

---

## 2. SOLID

### Single Responsibility (SRP)

- `LoginPage` — только селекторы и действия страницы логина. Не
  знает про учётки. Учётки — в `config/credentials.py`.
- `ApiClient` — только HTTP. Не валидирует ответы (это `steps/`),
  не помнит, под кем залогинен в UI (это `BrowserContext`).
- `EventFactory` — только payload. POST в SUT — это `steps/api/event_steps.py`.

### Open/Closed (OCP)

- Добавление новой страницы → новый класс в `pages/`. Существующие
  классы не трогаем.
- Добавление нового эндпоинта → новая функция в
  `steps/api/<domain>_steps.py`. `ApiClient.post_json` не меняется.
- Новый Trait фабрики (например, `EventFactory(in_the_past=True)`) —
  добавляется как параметр, существующие тесты продолжают работать.

### Liskov (LSP)

- Все Page-классы соблюдают контракт `BasePage`: `open()` возвращает
  `self`, `current_url()` возвращает `str`, `screenshot()` возвращает
  `Path`. Подкласс не сужает входы и не расширяет исключения.

### Interface Segregation (ISP)

- `ApiClient` имеет **узкие** методы (`get`, `post_json`, `patch_json`,
  `put_json`, `delete`), а не один универсальный `request(method, ...)`.
- Тесты, которым нужен только GET, не зависят от методов записи.

### Dependency Inversion (DIP)

- Тесты зависят от фикстур (`api_as_admin`, `logged_in_organizer_page`),
  а не от конкретных классов. Фикстуры — точка инъекции.
- `Settings` инжектируется как фикстура; никто не вызывает
  `Settings()` напрямую в тестах — только через `get_settings()` или
  фикстуру `settings`.

---

## 3. DRY

| Где переиспользуем                        | Что                                                                        |
|-------------------------------------------|----------------------------------------------------------------------------|
| `pages/`                                  | Селекторы — один раз на странице, тесты их не дублируют.                   |
| `pages/components/csrf_form.py`           | Legacy (Jinja2 admin удалена); SPA auth — JWT. |
| `steps/ui/auth_steps.py`                  | Логин-флоу (заполнить-нажать-ждать-вернуть) — один на все UI-тесты.        |
| `config/credentials.py`                   | Seed-учётки в одном месте, не разбросаны по тестам.                        |
| `core/api_client.py`                      | Заголовки авторизации инжектятся автоматически.                            |
| `factories/event_factory.py`              | Валидный payload `EventCreate` — один источник правды.                     |

### Где **не** применяем DRY (осознанно)

- Payload-литералы в pos- и neg-тестах: дублировать ради
  читабельности теста — нормально. Тест должен читаться без переходов
  в helper.
- Маленькие assert-ы (`assert resp.status_code == 200`) не выносим в
  helper — это не дублирование, это контракт теста.

---

## 4. KISS

- `ApiClient` — синхронный. Async нам снаружи не нужен; синхронный
  код читается линейно.
- Одна фабрика на сущность. Никаких «фабрик фабрик».
- Один Singleton — `Settings`. Не плодим менеджеров конфигов.
- Pos и neg — раздельные файлы. Никакой магии с параметризацией,
  если параметризация не короче двух простых функций.
- `BasePage` не реализует магических универсальных `find_anything()`.
  Каждая страница знает только свои элементы.
- Логгер — стандартный `logging`. Без `structlog` в первой итерации
  (можно добавить позже без ломания контракта `core/logger.py`).

---

## 5. Тест-дизайн техники — где применены

| Техника                       | Файл / директория                          | Пример использования                                                                            |
|-------------------------------|--------------------------------------------|--------------------------------------------------------------------------------------------------|
| Page Object Model             | `pages/login_page.py`                      | `LoginPage` инкапсулирует селекторы и действия страницы логина.                                  |
| Step Object Model             | `steps/ui/auth_steps.py`                   | `login_as_organizer(page, settings)` объединяет открыть страницу + заполнить + submit + ждать.   |
| Factory                       | `factories/event_factory.py`               | `EventFactory.build()` отдаёт валидный payload `EventCreate` с Faker(ru_RU).                     |
| Singleton                     | `config/settings.py`                       | `@lru_cache` на `get_settings()` — один экземпляр на процесс.                                    |
| Builder                       | `factories/event_factory.py::EventBuilder` | `EventBuilder().with_capacity(1).online().in_the_past().build()`.                                |
| Dependency Injection          | `fixtures/*.py`, `tests/conftest.py`       | Тест получает `api_as_admin`, `logged_in_organizer_page` через сигнатуру.                        |
| Layered architecture          | вся структура `testing-framework/`         | Зависимости только сверху вниз: tests → steps → pages/core → factories → config.                 |
| Strategy                      | `fixtures/sut_fixtures.py`                 | `QA_SUT_MODE=external|spawn` выбирает стратегию подготовки SUT.                                  |
| Context manager               | `core/api_client.py`, Playwright tracing   | `with ApiClient(...) as api:`; автоматическое закрытие сессии и сохранение trace.                |
| Parametrize (data-driven)     | `tests/api/auth/test_login_neg.py`         | Один тест-функция → 4 невалидных payload через `pytest.parametrize`.                             |

---

## 6. Pytest-best practices

### Маркеры (объявлены в `pyproject.toml`)

`smoke`, `regression`, `api`, `ui`, `integration`, `e2e`, `pos`, `neg`,
`slow`, `serial`. Каждый тест помечен минимум двумя маркерами:
область (`api`/`ui`/`integration`/`e2e`) + тип (`pos`/`neg`).
`--strict-markers` включён — опечатка в маркере падает сразу.

### Иерархия conftest

```
conftest.py (корень testing-framework) # глобальные: settings, logger, артефакты
tests/conftest.py               # sut_ready, seed_loaded
tests/api/conftest.py           # api-клиенты, токены
tests/ui/conftest.py            # browser, context, page, traced
tests/e2e/conftest.py           # композитные фикстуры
```

### Scope-плитка

- `session`: `settings`, `playwright`, `browser`, `sut_ready`, `seed_loaded`.
- `module`: тяжёлые данные модуля (например, `module_event`).
- `function`: `api_client`, `context`, `page`, `event_factory_with_cleanup`.
- `function` (autouse): `_cleanup_created_events`, `_capture_on_failure`.

### Параметризация

- `pytest.parametrize` для data-driven (neg-кейсы логина).
- `parametrize` через `pytest.param(..., id="bad-email")` — id-шники
  ставим явно, чтобы Allure показывал читаемые имена.
- `indirect=True` для фикстур, зависящих от параметра (например,
  `api_as_role` принимает `"admin"`/`"organizer"`).

### Допустимые анти-паттерны → не делаем

- Никаких `time.sleep` (есть `page.wait_for_*` и `expect()`).
- Никаких глобальных переменных-«общая БД фикстур» — только через
  fixtures.
- Никаких `os.environ` в коде теста — только через `Settings`.

---

## 7. Type hints и mypy

- Type hints — везде, включая фикстуры.
- `mypy --strict` для `core/`, `config/`, `pages/`, `steps/`,
  `factories/`. Для `tests/` допустимо более мягкое (`--ignore-missing-imports`).
- Pydantic-модели — для DTO ответов (опционально, не везде).

---

## 8. Линт и форматирование

- `ruff` — основной линтер. Конфиг в `pyproject.toml`. Включены:
  `E`, `W`, `F`, `I` (isort), `B` (bugbear), `UP` (pyupgrade), `RUF`.
- Длина строки — 100.
- Импорты — отсортированы (`ruff` делает).
- Pre-commit (опционально): `ruff check`, `ruff format`, `mypy`.

---

## 9. Безопасность и секреты

- `.env` — gitignored. В `.env.example` — заглушки.
- Пароли в `Settings` — `SecretStr` (pydantic). При логировании
  маскируются автоматически.
- В логах request/response — `password`, `access_token`, `_csrf`
  маскируются вручную в `core/api_client.py`.
- `data/` — gitignored. Сюда фикстуры могут писать локально, в
  репозиторий не попадает.

---

## 10. Артефакты и отчёты

- `reports/.gitkeep` коммитим, всё содержимое — gitignore.
- Allure: `pytest --alluredir=reports/allure-raw` + `allure generate`.
- pytest-html: `--html=reports/html/report.html --self-contained-html`.
- JUnit XML: `--junitxml=reports/junit.xml`.
- Playwright trace/video/screenshot — `reports/playwright/<test_id>/`.

При failure:

- screenshot — PNG, прикрепляется к Allure step;
- trace.zip — открывается `playwright show-trace`;
- последние 50 строк лога теста — атачится к Allure;
- request/response API — атачатся как JSON.

---

## 11. Документация

- `README.md` (корень `testing-framework/`) — как запустить с нуля, на русском.
- `docs/architecture.md` — слои, контракты, дерево файлов.
- `docs/best-practices.md` — настоящий файл (чек-листы соответствия).
- `docs/test-cases.md` — ручной каталог тест-кейсов (ID, сценарии, ожидания).
- Docstring-и — на русском, имена — на английском.

---

## 12. Анти-AI чеклист

Запрещённое (отлавливаем грепом при ревью):

- Фразы: «Generated by», «Based on», «AI-generated», «Created with
  help of», «As an experienced engineer», «Best practices say»,
  «Note that», «Please remember», «Here's a test that...», «I'll
  create...», «Let me...», «As requested...».
- Эмодзи в коде и комментариях. Исключение — проверка эмодзи в
  UI-текстах SUT (`assert "✅" in flash_text`).
- Длинные блочные комментарии «вступление + кейс + резюме».
  Комментарий длиннее 2 строк — повод подумать, не вынести ли в
  docstring или readme.
- Имена переменных вроде `my_var`, `some_value`, `temp_data`,
  `result_data`. Имя должно быть бизнес-смысловое: `published_event`,
  `confirmed_registration_code`, `organizer_token`.
- Docstring «This function does X». Пишем по делу: «Возвращает токен
  организатора. Кэшируется на сессию.»

Стиль комментариев — как в `app/api/v1/events.py:155`:

> Capacity не опускаем ниже confirmed — иначе overbook и инварианты
> sign_up/free_slots сломаются.

Коротко. Факт + причина. Без вступительной воды.

---

## 13. Чек-лист «реализация соответствует архитектуре»

Перед коммитом проверить:

- [ ] REST `/api/v1/*` — pos+neg по доменам (auth, events, stats, audit, …).
- [ ] `tests/ui/auth/` — pos+neg логин React SPA `/login`.
- [ ] `pages/base_page.py` существует, остальные Page — наследники.
- [ ] `steps/ui/` и `steps/api/` разделены.
- [ ] `factories/event_factory.py` использует Faker(ru_RU) и Trait-ы.
- [ ] `config/settings.py` — `@lru_cache` Singleton.
- [ ] Все маркеры объявлены в `pyproject.toml`.
- [ ] Иерархия conftest: корень → tests → tests/api → tests/ui.
- [ ] `.env.example` коммитится, `.env` — в `.gitignore`.
- [ ] `reports/.gitkeep` есть, остальное в `reports/` — gitignored.
- [ ] `ruff check` и `mypy core config pages steps factories` — чисто.
- [ ] Type hints везде в `core/`, `config/`, `pages/`, `steps/`.
- [ ] Docstring-и на русском, имена на английском.
- [ ] Нет ссылок на удалённые тесты: `test_admin_html`, `test_wall_pos`, `test_poster_csv`.
- [ ] Grep по запретным фразам из §12 — пусто.
