"""Logout — React SPA кнопка «Выйти»."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Browser, Page

from config.settings import Settings
from core.auth_helper import admin_client
from core.spa_auth import inject_spa_auth, resolve_organizer


@pytest.mark.ui
@pytest.mark.pos
def test_logout_clears_auth_and_redirects_to_login(
    browser: Browser, settings: Settings, sut_ready: bool,
) -> None:
    client = admin_client(settings)
    token = client.token
    assert token
    base = str(settings.base_url)
    organizer = resolve_organizer(client, settings.admin_email, role="admin")

    ctx = browser.new_context(locale="ru-RU", ignore_https_errors=True)
    ctx.set_default_timeout(settings.ui_default_timeout_ms)
    inject_spa_auth(ctx, token, organizer)
    try:
        page: Page = ctx.new_page()
        page.goto(f"{base}/events")
        page.locator('[data-testid="btn-logout"]').click()
        page.wait_for_url(re.compile(r"/login"), timeout=settings.ui_default_timeout_ms)
        auth_state = page.evaluate("() => localStorage.getItem('mirea-auth')")
        assert auth_state is None or '"token":null' in auth_state.replace(" ", "")
    finally:
        ctx.close()
        client.close()


@pytest.mark.ui
@pytest.mark.neg
def test_logout_api_endpoint_removed(settings: Settings) -> None:
    """POST /admin/logout удалён вместе с Jinja — SPA чистит state локально."""
    import httpx

    with httpx.Client(base_url=str(settings.base_url).rstrip("/"), timeout=5.0) as client:
        resp = client.post("/admin/logout")
    assert resp.status_code in (404, 405)
