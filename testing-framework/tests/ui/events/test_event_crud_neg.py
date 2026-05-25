"""Negative: создание мероприятия через React SPA."""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx
from playwright.sync_api import Page

from config.settings import Settings
from config.urls import path_events
from pages.event_form_page import EventFormPage


def _future_starts_at(days: int = 365) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


def test_create_event_title_too_short_blocked_by_html5(
    logged_in_organizer_page: Page, settings: Settings,
) -> None:
    form = EventFormPage(logged_in_organizer_page, str(settings.base_url))
    form.open()
    form.fill_title("ab")
    form.fill_capacity(50)
    form.fill_starts_at(_future_starts_at())
    form.submit()

    assert "/events" in logged_in_organizer_page.url
    assert form.modal_is_open()
    assert form.title_is_invalid()


def test_create_event_capacity_zero_blocked_by_html5(
    logged_in_organizer_page: Page, settings: Settings,
) -> None:
    form = EventFormPage(logged_in_organizer_page, str(settings.base_url))
    form.open()
    form.fill_title("Нормальное название")
    form.fill_capacity(0)
    form.fill_starts_at(_future_starts_at())
    form.submit()

    assert form.modal_is_open()
    assert form.capacity_is_invalid()


def test_api_create_without_token_returns_401(settings: Settings) -> None:
    with httpx.Client(base_url=str(settings.base_url).rstrip("/"), timeout=5.0) as client:
        resp = client.post(
            path_events(),
            json={
                "title": "Без токена",
                "starts_at": _future_starts_at(),
                "capacity": 10,
            },
        )
    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"
