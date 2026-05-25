"""Negative: UI-логин React SPA /login."""
from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page

from config.settings import Settings
from config.urls import path_events, ui_login
from pages.login_page import LoginPage

_ERROR_LOCATOR = '[data-testid="login-error"], .text-red-600'


@pytest.mark.parametrize(
    ("email_key", "password"),
    [
        pytest.param("admin", "definitely-wrong", id="wrong-password"),
        pytest.param("unknown", "anything12345", id="unknown-email"),
    ],
)
def test_invalid_credentials_show_error(
    page: Page,
    settings: Settings,
    email_key: str,
    password: str,
) -> None:
    base = str(settings.base_url)
    email = settings.admin_email if email_key == "admin" else "nobody@nope.ru"
    login = LoginPage(page, base)
    login.login_with(email, password)
    page.locator(_ERROR_LOCATOR).wait_for(state="visible", timeout=5000)
    assert "/login" in page.url
    error = login.error_text() or login.flash.error_text() or ""
    assert "Неверный email" in error


def test_empty_email_blocked_by_html5(page: Page, settings: Settings) -> None:
    base = str(settings.base_url)
    login = LoginPage(page, base)
    login.open()
    login.fill_password("anything")
    login.submit()
    assert "/login" in page.url


def test_protected_api_without_token_returns_401(settings: Settings) -> None:
    with httpx.Client(base_url=str(settings.base_url).rstrip("/"), timeout=5.0) as client:
        resp = client.get(path_events())
    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


def test_login_page_renders_without_csrf_cookie(settings: Settings) -> None:
    with httpx.Client(timeout=5.0, follow_redirects=False) as client:
        resp = client.get(ui_login())
    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert "csrf_token" not in resp.cookies
