"""E2E: организатор создаёт через UI → публикует через API → проверяет статистику → отменяет."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

from config.settings import Settings
from config.urls import path_event
from core.api_client import ApiClient
from pages.events_list_page import EventsListPage
from steps.api.event_steps import change_status, delete_event
from steps.ui.event_steps import create_draft_via_ui


@pytest.mark.slow
def test_organizer_full_flow(
    logged_in_organizer_page: Page,
    api_as_organizer: ApiClient,
    settings: Settings,
) -> None:
    page = logged_in_organizer_page
    base = str(settings.base_url)
    title, event_id = create_draft_via_ui(page, settings, title_prefix="E2E поток")

    try:
        change_status(api_as_organizer, event_id, "published")

        # событие появилось в списке как опубликованное
        listing = EventsListPage(page, base).open()

        assert listing.has_card_with_title(title)

        stats = api_as_organizer.get(f"{path_event(event_id)}/stats")

        assert stats.status_code == 200, f"Ожидали 200, получили {stats.status_code}: {stats.text}"

        change_status(api_as_organizer, event_id, "cancelled")
        current = api_as_organizer.get(path_event(event_id)).json()

        assert current["status"] == "cancelled"
    finally:
        # удалить event, даже если упали
        try:
            delete_event(api_as_organizer, event_id)
        except Exception:
            pass
