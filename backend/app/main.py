"""Точка входа FastAPI-приложения.

Один процесс обслуживает:

1. **MAX-бот** — long polling в режиме разработки, webhook в проде.
2. **REST API** — `/api/v1/...`, документация на `/docs` (Swagger UI) и `/redoc`.
3. **React SPA** — `frontend/dist` (если собран), fallback на `index.html`.

Запуск:
    uvicorn app.main:app --host 0.0.0.0 --port 8080            # прод
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8080   # разработка
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_v1_router
from app.bot import handlers  # noqa: F401 — импорт регистрирует хендлеры в диспетчере
from app.bot.instance import bot, dp
from app.config import get_settings
from app.core.security_headers import SecurityHeadersMiddleware
from app.scheduler import start_scheduler, stop_scheduler

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Подъём фоновых задач при старте и аккуратное гашение при остановке."""
    polling_task: asyncio.Task | None = None
    stop_event = asyncio.Event()

    # Лёгкая авто-миграция: добавляем недостающие колонки в существующие
    # таблицы. Нужно для случая «БД создана старой версией кода». Без этого
    # любой sign_up / scan на старой БД упадёт с OperationalError.
    try:
        from app.db_init import init_db
        init_db()
    except Exception:
        logger.exception("Не удалось применить авто-миграции схемы БД")

    # Проверка токена при старте: получаем /me. Если упадёт — приложение
    # запустится всё равно (чтобы можно было открыть админку), но в логе
    # появится понятное предупреждение.
    try:
        me = await bot.get_me()
        logger.info("Bot online: username=%s, user_id=%s", me.get("username"), me.get("user_id"))
    except Exception:
        logger.exception("Не удалось проверить токен MAX (GET /me)")

    if settings.is_webhook_mode:
        # Webhook-режим: регистрируем подписку у MAX. Сам endpoint объявлен
        # ниже, в этом же файле.
        assert settings.webhook_url is not None  # is_webhook_mode => webhook_url truthy
        logger.info("Bot mode: webhook → %s", settings.webhook_url)
        try:
            await bot.set_webhook(url=settings.webhook_url, secret=settings.webhook_secret)
        except Exception:
            logger.exception("Не удалось зарегистрировать webhook у MAX")
    else:
        # Long polling — фоновая корутина на весь жизненный цикл приложения.
        logger.info("Bot mode: long polling")
        polling_task = asyncio.create_task(dp.run_polling(bot, stop_event=stop_event))

    start_scheduler()
    logger.info("Application started")

    yield

    logger.info("Shutting down…")
    stop_scheduler()
    if polling_task is not None:
        stop_event.set()
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    await bot.close()
    logger.info("Goodbye")


OPENAPI_DESCRIPTION = """
REST API сервиса **mirea-events-bot** — бота МАКС для записи абитуриентов и студентов
на мероприятия университета. Документация ниже сгруппирована по подсистемам:

* **auth** — получение JWT-токена организатора;
* **events** — CRUD мероприятий;
* **registrations** — список записей по мероприятию;
* **scan** — сканер QR-кодов на входе;
* **broadcasts** — рассылки участникам по сегментам;
* **stats** — сводная статистика для дашбордов;
* **health** — liveness / readiness.

Все ручки (кроме `health` и `auth/login`) защищены Bearer-токеном —
получите его через `POST /api/v1/auth/login` и подставьте в заголовок
`Authorization: Bearer <token>`.

Веб-админка для организаторов — React SPA из `frontend/dist` (если собрана).
""".strip()

OPENAPI_TAGS = [
    {"name": "health", "description": "Проверки доступности процесса и зависимостей."},
    {"name": "auth", "description": "Авторизация организаторов и выдача JWT."},
    {"name": "events", "description": "Управление мероприятиями (создание, публикация, отмена)."},
    {"name": "slots", "description": "Временные окна (слоты) мероприятия."},
    {"name": "registrations", "description": "Списки записей участников по мероприятию."},
    {"name": "organizers", "description": "Управление организаторами (только admin)."},
    {"name": "scan", "description": "Отметка посещения по QR-коду на входе мероприятия."},
    {"name": "broadcasts", "description": "Управляемые рассылки участникам по сегментам."},
    {"name": "stats", "description": "Сводные счётчики и воронки для дашбордов."},
    {"name": "audit", "description": "Журнал аудита действий (только admin)."},
]


app = FastAPI(
    title="mirea-events-bot API",
    summary="Бот МАКС для записи абитуриентов на мероприятия университета",
    description=OPENAPI_DESCRIPTION,
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "Команда mirea-events-bot"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS для Vite dev-сервера (React SPA на :5173 / :3000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Security headers идут самыми внешними — они должны проставиться на любой
# ответ, включая исключения / редиректы / static-файлы.
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(api_v1_router)

# Статика для QR-картинок. Mount нужен, чтобы send_photo_url мог отправлять
# абсолютную ссылку на наш же сервер вместо неконсистентного upload'а в МАКС
# (см. `app/bot/notifications.py:send_photo`).
# Безопасность: имена файлов — это `qr_token` (32 hex без угадывания),
# что эквивалентно непредсказуемой уникальной ссылке.
_qr_dir = Path(settings.qr_dir)
_qr_dir.mkdir(parents=True, exist_ok=True)
app.mount("/qr", StaticFiles(directory=str(_qr_dir)), name="qr")

# Favicon-заглушка: иначе каждый браузер плюсует 404 в логи на ровном месте.
_FAVICON_SVG = (
    b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>"
    b"<rect width='24' height='24' rx='6' fill='#4f46e5'/>"
    b"<path d='M7 8h10M7 12h10M7 16h6' stroke='white' stroke-width='2' stroke-linecap='round'/>"
    b"</svg>"
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(content=_FAVICON_SVG, media_type="image/svg+xml")


@app.post("/webhook", include_in_schema=False)
async def webhook(
    request: Request,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> dict:
    # Проверяем секрет, если он задан в конфиге. На стороне MAX заголовок
    # называется по-разному в разных версиях API — берём из docs тот, что
    # отдаёт сервер. Если MAX будет слать другой — поправим в одном месте.
    if settings.webhook_secret and x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad secret")

    try:
        update = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc

    await dp.handle_update(update, bot)
    return {"ok": True}


# Раздаём скомпилированный React SPA. Mount последним — API/бот/webhook уже
# зарегистрированы выше и не перехватываются StaticFiles.
# Для статики (js/css/images) монтируем /assets, а корневые роуты SPA
# (/login, /events, /organizers и т.д.) обслуживает catch-all ниже,
# который всегда отдаёт index.html — это эквивалент nginx try_files $uri /index.html.
_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    _assets_dir = _dist / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    _index_html = _dist / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        from fastapi.responses import FileResponse, Response

        candidate = _dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        if _index_html.exists():
            return FileResponse(str(_index_html))
        return Response(status_code=404)
