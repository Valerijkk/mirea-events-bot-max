# 🧪 testing-framework

Black-box QA-комплекс для **mirea-events-bot**: REST API (`/api/v1/*`) и React SPA
(`/login`, `/events`, `/organizers`, …). Внутрь SUT не лезет — только HTTP (httpx)
и Chromium (Playwright).

## Что покрывается

| Маркер | Уровень | Нужен SUT | Описание |
|--------|---------|-----------|----------|
| `unit` | in-memory TestClient | нет | модели, сервисы, бот, утилиты backend |
| `api` | httpx REST | да (:8080) | CRUD, auth, scan, security, edge-cases |
| `ui` | Playwright | да + `frontend/dist` | React SPA, data-testid-селекторы |
| `integration` | API + UI | да | «API создал → UI показал» |
| `e2e` | сквозные | да | organizer_full_flow, mirea_real_data |
| `smoke` | подмножество | зависит | критический минимум (< 30 с) |
| `pos` / `neg` | полярность | — | позитив / негатив (auto из `_pos`/`_neg` в имени) |
| `edge` | граничные | зависит | сценарии из `docs/diagrams/*.puml` |
| `security` | доступ | зависит | JWT, IDOR, rate-limit, headers |
| `serial` | порядок | — | нельзя гонять параллельно (rate-limit login) |
| `slow` | > 5 с | — | e2e, rate-limit |

## Быстрый старт

### 1. SUT (backend)

```powershell
cd C:\Users\Valerii\Desktop\abitur-bot
python -m venv .venv-sut
.venv-sut\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m app.cli.init_project
# React SPA (для UI-тестов):
cd frontend
npm ci
npm run build
cd ..
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Проверка: `curl http://127.0.0.1:8080/api/v1/healthz`

Или через Makefile из корня: `make bootstrap` + `make dev`.

### 2. testing-framework

```powershell
cd testing-framework
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m playwright install chromium
copy .env.example .env
```

### 3. Прогон

```powershell
python -m pytest -m unit -q
python -m pytest -m api -q
python -m pytest -m "ui and smoke" -q
python -m pytest -n auto -m "not serial"
```

## Маркеры (полная таблица)

| Маркер | Описание |
|--------|----------|
| `unit` | In-memory white-box: моки БД, uvicorn не нужен |
| `api` | REST через httpx, JWT Bearer |
| `ui` | Playwright Chromium, React SPA |
| `integration` | Связка API + UI или `/api/v1/integration/*` |
| `e2e` | Полные пользовательские сценарии |
| `smoke` | Быстрая регрессия перед деплоем |
| `regression` | Расширенное покрытие |
| `pos` | Успешный путь |
| `neg` / `negative` | Ошибки, 401/403/422 |
| `edge` | Corner-cases из UML |
| `security` | JWT, IDOR, CSRF (legacy), rate-limit |
| `slow` | Долгие тесты |
| `serial` | Общий rate-limit / seed — без xdist |

`--strict-markers` включён — опечатка в `-m` падает на коллекции.

## SUT

- **URL по умолчанию:** `http://127.0.0.1:8080` (`QA_BASE_URL` в `.env`)
- **Готовность:** фикстура `sut_ready` ждёт `/api/v1/readyz`
- **UI auth:** session-scoped JWT в `localStorage` (`mirea-auth`) через `core/spa_auth.py`
- **Integration key:** `QA_INTEGRATION_API_KEY` — иначе integration-тесты SKIP

## Примеры запуска

```powershell
# unit — без сервера
python -m pytest -m unit -q

# API smoke
python -m pytest -m "api and smoke" -v

# UI smoke (нужен SUT + frontend/dist)
python -m pytest -m "ui and smoke" --headed

# edge-cases из PUML
python -m pytest -m edge -v

# security
python -m pytest -m security -v

# один домен
python -m pytest tests/api/auth -v

# параллельно
python -m pytest -n auto -m "not serial"

# collect-only
python -m pytest --collect-only -q
```

## Структура

```
testing-framework/
├── config/        Settings, URL-билдеры, seed-учётки
├── core/          ApiClient, auth_helper, spa_auth, logger
├── pages/         POM (Login, Events, Scanner, …)
│   └── components/
├── steps/         SOM — api/* + ui/*
├── factories/     factory-boy + EventBuilder
├── fixtures/      sut, api, ui, auth, data, mirea
├── utils/         assertions, bug_report, timings, allure_helpers
├── tests/
│   ├── unit/      in-memory backend
│   ├── api/       REST black-box
│   ├── ui/        Playwright React SPA
│   ├── integration/
│   └── e2e/
├── docs/          architecture.md, best-practices.md, test-cases.md
└── reports/       allure, html, bugs, timings (gitignored)
```

## Allure

```powershell
python -m pytest --alluredir=reports/allure-raw
allure serve reports/allure-raw
```

Нужны Java 8+ и [Allure CLI](https://docs.qameta.io/allure/).

HTML-отчёт:

```powershell
python -m pytest --html=reports/html/report.html --self-contained-html
```

## Линт

```powershell
python -m ruff check .
python -m mypy .
```

## Troubleshooting

| Симптом | Решение |
|---------|---------|
| `httpx.ConnectError` | SUT не поднят — `make dev` |
| UI-тесты SKIP / пустая страница | Собери `frontend/dist`: `cd frontend && npm run build` |
| `ModuleNotFoundError: app.*` | `conftest.py` добавляет `../backend` в `sys.path` |
| integration SKIP | Задай `QA_INTEGRATION_API_KEY` |
| Rate-limit 429 на UI login | `-m "not serial"` или подожди 60 с |
| Allure «java not found» | JDK + `scoop install allure` |

Подробнее: `docs/architecture.md`, `docs/best-practices.md`, `docs/test-cases.md`.
