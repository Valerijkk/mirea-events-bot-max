"""API создал → UI показывает. Связка REST + Playwright."""
from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page

from config.settings import Settings
from config.urls import path_event_status
from core.api_client import ApiClient
from pages.event_detail_page import EventDetailPage
from pages.events_list_page import EventsListPage


@pytest.mark.pos
def test_post_event_via_api_shows_in_admin_events_list(
    api_as_organizer: ApiClient,
    event_factory_with_cleanup,
    logged_in_organizer_page: Page,
    settings: Settings,
) -> None:
    title = f"Интеграция API→UI #{uuid.uuid4().hex[:6]}"
    event_factory_with_cleanup(title=title)

    events_list = EventsListPage(logged_in_organizer_page, str(settings.base_url)).open()

    assert events_list.has_card_with_title(title), (
        f"карточка с title={title!r} не найдена; реальные: {events_list.card_titles()}"
    )


@pytest.mark.pos
def test_publish_via_api_changes_status(
    api_as_organizer: ApiClient,
    event_factory_with_cleanup,
    logged_in_organizer_page: Page,
    settings: Settings,
) -> None:
    title = f"Публикация API→UI #{uuid.uuid4().hex[:6]}"
    event = event_factory_with_cleanup(title=title)

    api_as_organizer.post_json(
        path_event_status(event["id"]),
        json={"status": "published"},
    )

    detail = EventDetailPage(logged_in_organizer_page, str(settings.base_url)).open_for_event(
        event["id"],
    )

    assert detail.is_loaded(), "страница события не загрузилась после API-публикации"
    detail.wait_for_status("Опубликовано")
    assert detail.has_status("Опубликовано")
