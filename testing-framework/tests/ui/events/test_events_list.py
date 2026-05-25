"""Список событий React SPA /events."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

from config.settings import Settings
from pages.events_list_page import EventsListPage


@pytest.mark.smoke
def test_events_list_page_renders(
    logged_in_admin_page: Page, settings: Settings,
) -> None:
    page = EventsListPage(logged_in_admin_page, str(settings.base_url)).open()
    assert page.is_loaded()


@pytest.mark.regression
def test_organizer_events_list_renders(
    logged_in_organizer_page: Page, settings: Settings,
) -> None:
    page = EventsListPage(logged_in_organizer_page, str(settings.base_url)).open()
    assert page.is_loaded()


@pytest.mark.regression
def test_create_button_visible_on_events_list(
    logged_in_organizer_page: Page, settings: Settings,
) -> None:
    EventsListPage(logged_in_organizer_page, str(settings.base_url)).open()
    assert logged_in_organizer_page.locator('[data-testid="btn-create-event"]').count() >= 1
