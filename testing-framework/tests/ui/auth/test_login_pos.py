"""Positive: UI-логин React SPA /login."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

from config.settings import Settings
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage


@pytest.mark.smoke
def test_login_page_shows_hackathon_disclaimer(page: Page, settings: Settings) -> None:
    """TC-UI-LOGIN-001: страница логина содержит дисклеймер о хакатоне и неофициальности МАКС."""
    base = str(settings.base_url)
    LoginPage(page, base).open()
    content = page.content().lower()

    assert "хакатон" in content
    assert "не является официальной функцией" in content


@pytest.mark.smoke
@pytest.mark.serial
def test_login_admin_redirects_and_sets_cookie(page: Page, settings: Settings) -> None:
    """Успешный логин → /events + JWT в localStorage (SPA не использует cookie)."""
    base = str(settings.base_url)
    LoginPage(page, base).login_with(settings.admin_email, settings.admin_password_value)
    page.wait_for_url(re.compile(r"/events/?$"), timeout=settings.ui_default_timeout_ms)
    dashboard = DashboardPage(page, base)
    assert dashboard.is_loaded()
    auth_state = page.evaluate("() => localStorage.getItem('mirea-auth')")
    assert auth_state, "JWT токен должен быть сохранён в localStorage 'mirea-auth'"
    assert settings.admin_email in auth_state


@pytest.mark.serial
def test_login_organizer_redirects_to_events(page: Page, settings: Settings) -> None:
    base = str(settings.base_url)
    LoginPage(page, base).login_with(
        settings.organizer_email,
        settings.organizer_password_value,
    )
    page.wait_for_url(re.compile(r"/events/?$"), timeout=settings.ui_default_timeout_ms)
    assert "/events" in page.url and "login" not in page.url
