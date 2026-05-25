"""Positive: главная после логина — /events."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

from config.settings import Settings
from pages.dashboard_page import DashboardPage


@pytest.mark.smoke
@pytest.mark.pos
def test_dashboard_shows_heading_and_create_button(
    logged_in_admin_page: Page, settings: Settings,
) -> None:
    dashboard = DashboardPage(logged_in_admin_page, str(settings.base_url)).open()
    assert dashboard.is_loaded()
    assert dashboard.has_create_button()
