"""UI-шаги CRUD мероприятий."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from playwright.sync_api import Page

from config.settings import Settings
from pages.event_detail_page import EventDetailPage
from pages.event_form_page import EventFormPage
from pages.events_list_page import EventsListPage


def _future_iso_local(days_ahead: int = 21) -> str:
    return (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M")


def fill_event_form(page: Page, settings: Settings, **overrides: Any) -> EventFormPage:
    form = EventFormPage(page, str(settings.base_url))
    form.open()
    payload = {
        "title": overrides.get("title", "Тест UI создание мероприятия"),
        "description": overrides.get("description", "Описание тестового события."),
        "event_type": overrides.get("event_type", "open_day"),
        "capacity": overrides.get("capacity", 50),
        "starts_at": overrides.get("starts_at", _future_iso_local()),
        "format": overrides.get("format", "onsite"),
        "location": overrides.get("location", "ауд. 301"),
    }
    form.fill_title(payload["title"])
    form.fill_description(payload["description"])
    form.select_event_type(payload["event_type"])
    form.fill_capacity(payload["capacity"])
    form.fill_starts_at(payload["starts_at"])
    form.select_format(payload["format"])
    if payload["format"] == "onsite":
        form.fill_location(payload["location"])
    return form


def create_draft_via_ui(
    page: Page,
    settings: Settings,
    *,
    title_prefix: str = "UI Draft",
    days_ahead: int = 21,
) -> tuple[str, int]:
    """Создать черновик через модалку на /events и вернуть `(title, id)`.

    После submit React закрывает модалку и остаётся на списке — id берём
    из data-testid event-link-{id}, затем открываем карточку.
    """
    title = f"{title_prefix} #{uuid.uuid4().hex[:6]}"
    starts_at = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M")

    form = fill_event_form(page, settings, title=title, starts_at=starts_at)
    form.submit()

    listing = EventsListPage(page, str(settings.base_url))
    page.wait_for_function(
        f"() => document.body.innerText.includes({title!r})",
        timeout=settings.ui_default_timeout_ms,
    )
    event_id = listing.event_id_by_title(title)
    if event_id is None:
        raise AssertionError(f"событие {title!r} не появилось в таблице /events")

    EventDetailPage(page, str(settings.base_url)).open_for_event(event_id)
    page.wait_for_url(re.compile(rf"/events/{event_id}"), timeout=settings.ui_default_timeout_ms)
    return title, event_id
