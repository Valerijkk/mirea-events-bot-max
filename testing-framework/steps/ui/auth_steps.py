"""UI-шаги авторизации поверх LoginPage."""
from __future__ import annotations

import re

from playwright.sync_api import Page

from config.credentials import ADMIN, ORGANIZER_IPTIP, Credential
from config.settings import Settings
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage


def login_with(page: Page, settings: Settings, credential: Credential) -> DashboardPage:
    base = str(settings.base_url)
    login = LoginPage(page, base)
    login.open()
    login.fill_email(credential.email)
    login.fill_password(credential.password)
    login.submit()
    page.wait_for_url(re.compile(r"/events/?$"), timeout=settings.ui_default_timeout_ms)
    return DashboardPage(page, base)


def login_as_admin(page: Page, settings: Settings) -> DashboardPage:
    cred = Credential(
        email=settings.admin_email,
        password=settings.admin_password_value,
        role="admin",
        label=ADMIN.label,
    )
    return login_with(page, settings, cred)


def login_as_organizer(page: Page, settings: Settings) -> DashboardPage:
    cred = Credential(
        email=settings.organizer_email,
        password=settings.organizer_password_value,
        role="organizer",
        label=ORGANIZER_IPTIP.label,
    )
    return login_with(page, settings, cred)
