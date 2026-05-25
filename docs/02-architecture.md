# 2. Архитектура

## Карта компонентов

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         docker compose (prod/dev)                       │
│                                                                         │
│  ┌──────────────────────┐         ┌─────────────────────────────────┐ │
│  │  frontend (nginx)    │         │  backend (uvicorn)              │ │
│  │  React SPA static    │  /api/* │                                 │ │
│  │  :80                 │ ──────► │  MAX-бот (/webhook или long-poll)│ │
│  │  try_files → index   │  proxy  │  REST API /api/v1/...           │ │
│  │  .html               │         │  /docs /redoc                   │ │
│  └──────────────────────┘         └──────────────┬──────────────────┘ │
│                                                  │                      │
│                                         ┌────────▼────────┐             │
│                                         │  PostgreSQL 16  │             │
│                                         │  (db)           │             │
│                                         └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘

Локальная разработка без Docker:
  frontend: Vite dev-server :5173  →  proxy /api → backend :8000
  backend:  uvicorn backend/app/main.py :8000
```

Три сервиса: **backend** (FastAPI API-only + бот), **frontend** (React SPA за nginx),
**db** (PostgreSQL). Монолитный uvicorn с Jinja2-админкой снят в #183.

## Слои backend

| Слой             | Куда смотреть в коде              | Что отвечает                                                            |
|------------------|-----------------------------------|-------------------------------------------------------------------------|
| Транспортный     | `backend/app/main.py`             | Подъём FastAPI, lifespan, регистрация роутеров и webhook.               |
| API REST         | `backend/app/api/`                | Pydantic-валидация входов, Swagger-описания, маппинг в сервисы.         |
| Бот              | `backend/app/bot/`                | Хендлеры, тексты, клавиатуры, отправка сообщений.                       |
| Auth (JWT)       | `backend/app/admin/auth.py`       | bcrypt, выдача/проверка JWT (Bearer для REST и SPA).                    |
| Бизнес-сервисы   | `backend/app/services/`         | Запись/отмена/waitlist, рассылки, QR, статистика, audit — переиспользуется всеми.|
| Планировщик      | `backend/app/scheduler.py`        | APScheduler, тик каждую минуту, рассылка отложенных напоминаний.        |
| Доступ к данным  | `backend/app/models.py`, `backend/app/db.py` | ORM-модели, фабрика сессий.                              |

### Frontend (React SPA)

| Слой             | Куда смотреть в коде              | Что отвечает                                                            |
|------------------|-----------------------------------|-------------------------------------------------------------------------|
| Страницы         | `frontend/src/pages/`             | Login, Events, EventDetail, Slots, Scanner, Broadcasts, Stats, Audit, Organizers. |
| API-клиент       | `frontend/src/api/`               | Axios + TanStack Query hooks.                                           |
| Состояние UI     | `frontend/src/stores/`            | Zustand (auth, тосты).                                                  |
| Маршруты         | `frontend/src/router.tsx`         | React Router v6, `ProtectedRoute` / `AdminRoute`.                       |

Сервис `backend/app/services/stats.py` — единый источник истины для дашборда
(SPA) и REST `/api/v1/stats`: один и тот же `collect_global_stats()`
и `registrations_by_day()` для графика.

## Принципы

1. **Бизнес-логика — в сервисах**, а не в обработчиках. И бот, и REST, и
   React SPA дёргают одни и те же функции из `backend/app/services/`.
2. **Сессии БД короткие**: открываются на одну операцию, закрываются перед
   тем, как лезть в сеть (MAX API). Это исключает «висящие» транзакции и
   ошибки lazy-load.
3. **Pydantic-схемы отдельно от ORM**. ORM-модели — внутреннее представление;
   схемы — внешний контракт API. Они могут эволюционировать независимо.
4. **Версионирование API в URL** (`/api/v1/...`). Когда контракт станет
   несовместимым, поднимется `/api/v2/` без слома существующих клиентов.
5. **JWT — один на всё**. React SPA (localStorage + Bearer) и REST используют
   один и тот же токен. Это упрощает работу мобильному сканеру QR — он берёт
   ровно тот же логин и получает доступ к `/api/v1/scan`.

## Технологический стек

**Backend:**

* **Python 3.11+** — типизированный современный код.
* **FastAPI** — Swagger из коробки, валидация.
* **SQLAlchemy 2.0** (sync API) — стабильно, понятно.
* **Pydantic v2** — схемы REST.
* **APScheduler** — простой и достаточный для нашей нагрузки.
* **Собственный тонкий HTTP-клиент** к MAX Bot API на `httpx` (см. `backend/app/bot/client.py`).

**Frontend:**

* **Vite + React 18 + TypeScript**
* **Tailwind CSS** (локальный билд)
* **TanStack Query** — серверное состояние
* **Zustand** — auth и UI-состояние
* **React Router v6** — маршрутизация SPA

**Инфра:**

* **PostgreSQL 17** — основная БД в docker-compose.
* **nginx** — статика SPA + reverse proxy `/api/*` → backend.

## Куда расти

| Когда                                              | Куда                                                    |
|----------------------------------------------------|---------------------------------------------------------|
| >50–100 одновременных пользователей                | async SQLAlchemy, connection pool tuning.               |
| >500 получателей в одной рассылке                  | Очередь (ARQ или Celery+Redis), пул отправок.           |
| Несколько процессов / нод                          | Вынести APScheduler в отдельный воркер, разделить лок.  |
| Подключение новой ИС вуза                          | Выдать `IntegrationKey` под source (см. `backend/app/api/v1/integration.py`). |
