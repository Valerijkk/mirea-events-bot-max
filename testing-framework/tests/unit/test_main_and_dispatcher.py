"""Тесты `app/main.py` lifespan и `app/bot/dispatcher.py`.

Lifespan стартует бот + scheduler + webhook — всё это заглушаем на no-op,
чтобы FastAPI поднимался в TestClient без сети и фоновых задач.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def patched_app(monkeypatch):
    """`app.main:app` с замоканными бот/scheduler — без сети и фон-thread'ов."""
    async def fake_get_me():
        return {"user_id": 1, "username": "test_bot"}

    async def fake_close():
        return None

    async def fake_run_polling(_bot, stop_event=None):
        if stop_event is not None:
            stop_event.set()

    monkeypatch.setattr("app.bot.instance.bot.get_me", fake_get_me)
    monkeypatch.setattr("app.bot.instance.bot.close", fake_close)
    monkeypatch.setattr("app.bot.instance.dp.run_polling", fake_run_polling)
    monkeypatch.setattr("app.main.start_scheduler", lambda: None)
    monkeypatch.setattr("app.main.stop_scheduler", lambda: None)

    # Импорт main ПОСЛЕ подмены — lifespan подхватит мок-функции.
    from app.main import app
    return app


def test_app_lifespan_starts_and_stops_cleanly(patched_app):
    """TestClient поднимает реальный lifespan и гасит его. Если бы что-то
    из фоновых вызовов реально полезло в сеть — тест бы завис.
    """
    with TestClient(patched_app) as client:
        resp = client.get("/api/v1/healthz")
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"


def test_spa_login_page_when_dist_built(patched_app):
    """GET /login отдаёт index.html, если frontend/dist собран и SPA смонтирован."""
    from pathlib import Path

    dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if not (dist / "index.html").exists():
        pytest.skip("frontend/dist не собран — SPA не смонтирован")

    with TestClient(patched_app) as client:
        resp = client.get("/login")
        if resp.status_code == 404:
            pytest.skip(
                "SPA mount недоступен — app.main импортирован до сборки frontend/dist; "
                "перезапусти pytest после npm run build",
            )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        # SPA — HTML-шаблон, русский текст рендерится React'ом через JS-бандл,
        # поэтому проверяем только то, что в статике реально присутствует.
        assert 'id="root"' in resp.text


def test_api_events_requires_auth(patched_app):
    with TestClient(patched_app) as client:
        resp = client.get("/api/v1/events")
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


def test_webhook_endpoint_rejects_bad_secret(patched_app, monkeypatch):
    """С заданным webhook_secret чужой/пустой секрет → 401."""
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "webhook_secret", "expected-secret")

    with TestClient(patched_app) as client:
        resp = client.post(
            "/webhook",
            json={"update_type": "test"},
            headers={"X-Webhook-Secret": "wrong"},
        )
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


def test_webhook_endpoint_rejects_invalid_json(patched_app, monkeypatch):
    """Невалидный JSON → 400, а не 500."""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "webhook_secret", None)
    with TestClient(patched_app) as client:
        resp = client.post(
            "/webhook",
            content=b"not-a-json{",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400, f"Ожидали 400, получили {resp.status_code}: {resp.text}"


# ===========================================================================
# Dispatcher — long polling marker + хендлер-роутинг
# ===========================================================================

class TestDispatcher:
    """`Dispatcher` — map(update_type → callable), регистрация через `@dp.on()`."""

    def test_dispatcher_registers_and_dispatches(self):
        from app.bot.dispatcher import Dispatcher
        dp = Dispatcher()

        calls = []

        @dp.on("message_created")
        async def handler(update, client):
            calls.append(update)

        asyncio.run(dp.handle_update(
            {"update_type": "message_created", "x": 1}, client=object(),
        ))
        assert len(calls) == 1
        assert calls[0]["x"] == 1

    def test_dispatcher_ignores_unknown_update_type(self):
        """Для незнакомого update_type — тихий no-op, не исключение."""
        from app.bot.dispatcher import Dispatcher
        dp = Dispatcher()
        asyncio.run(dp.handle_update({"update_type": "no_such"}, client=object()))

    def test_dispatcher_multiple_handlers_for_same_type(self):
        from app.bot.dispatcher import Dispatcher
        dp = Dispatcher()

        calls = []

        @dp.on("bot_started")
        async def h1(update, client):
            calls.append("h1")

        @dp.on("bot_started")
        async def h2(update, client):
            calls.append("h2")

        asyncio.run(dp.handle_update({"update_type": "bot_started"}, client=object()))
        # Порядок регистрации сохраняется.
        assert calls == ["h1", "h2"]
