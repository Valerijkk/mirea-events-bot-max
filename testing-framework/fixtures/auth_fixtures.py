"""Фикстуры залогиненных UI-сессий.

Авторизация один раз за session через API (POST /api/v1/auth/login):
JWT кладём в localStorage (`mirea-auth`) — React SPA читает zustand persist.
Cookie `admin_token` тоже выставляем для совместимости с page.request.

* избегает rate-limit на UI-логине (5/мин/IP);
* module-scoped browser/context — Playwright не держит event loop до unit-тестов;
* function-scoped page — независимые тесты с общим кэшем auth-state внутри модуля.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Browser, BrowserContext, Page

from config.settings import Settings
from core.auth_helper import (
    admin_client as _admin_client,
)
from core.auth_helper import (
    organizer_client,
)
from core.spa_auth import inject_spa_auth, resolve_organizer


def _jwt_cookie(token: str, base_url: str) -> Any:
    netloc = urlparse(base_url).netloc.split(":")[0]
    return {
        "name": "admin_token",
        "value": token,
        "domain": netloc,
        "path": "/",
        "httpOnly": True,
        "secure": False,
        "sameSite": "Lax",
    }


def _make_auth_context(
    browser: Browser,
    settings: Settings,
    *,
    email: str,
    role: str,
    client_factory: Any,
) -> BrowserContext:
    client = client_factory(settings)
    token = client.token
    assert token, "auth_helper client должен вернуть клиент с токеном"
    organizer = resolve_organizer(client, email, role=role)

    ctx = browser.new_context(
        viewport={"width": settings.viewport_width, "height": settings.viewport_height},
        locale="ru-RU",
        ignore_https_errors=True,
    )
    ctx.set_default_timeout(settings.ui_default_timeout_ms)
    inject_spa_auth(ctx, token, organizer)
    ctx.add_cookies([_jwt_cookie(token, str(settings.base_url))])
    ctx._qa_client = client  # type: ignore[attr-defined]
    return ctx


@pytest.fixture(scope="module")
def admin_context(
    browser: Browser, settings: Settings, sut_ready: bool,
) -> Iterator[BrowserContext]:
    ctx = _make_auth_context(
        browser,
        settings,
        email=settings.admin_email,
        role="admin",
        client_factory=_admin_client,
    )
    yield ctx
    ctx.close()
    ctx._qa_client.close()  # type: ignore[attr-defined]


@pytest.fixture(scope="module")
def organizer_context(
    browser: Browser, settings: Settings, sut_ready: bool,
) -> Iterator[BrowserContext]:
    ctx = _make_auth_context(
        browser,
        settings,
        email=settings.organizer_email,
        role="organizer",
        client_factory=organizer_client,
    )
    yield ctx
    ctx.close()
    ctx._qa_client.close()  # type: ignore[attr-defined]


@pytest.fixture
def logged_in_admin_page(admin_context: BrowserContext) -> Iterator[Page]:
    page = admin_context.new_page()
    yield page
    page.close()


@pytest.fixture
def logged_in_organizer_page(organizer_context: BrowserContext) -> Iterator[Page]:
    page = organizer_context.new_page()
    yield page
    page.close()
