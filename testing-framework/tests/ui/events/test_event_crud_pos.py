"""Positive: создание мероприятия через модалку React SPA."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from playwright.sync_api import Page

from config.settings import Settings
from pages.events_list_page import EventsListPage
from steps.ui.event_steps import fill_event_form


def test_create_event_via_form_appears_in_list(
    logged_in_organizer_page: Page, settings: Settings,
) -> None:
    page = logged_in_organizer_page
    base = str(settings.base_url)
    unique_title = f"UI Создание #{uuid.uuid4().hex[:6]}"
    starts_at = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M")

    form = fill_event_form(page, settings, title=unique_title, starts_at=starts_at)
    form.submit()
    page.wait_for_function(
        f"() => document.body.innerText.includes({unique_title!r})",
        timeout=settings.ui_default_timeout_ms,
    )

    events = EventsListPage(page, base)
    assert events.has_card_with_title(unique_title)
