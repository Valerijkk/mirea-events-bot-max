"""Positive: слоты на /events/{id}/slots."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from playwright.sync_api import Page

from config.settings import Settings
from pages.slots_page import SlotsPage
from steps.ui.event_steps import create_draft_via_ui


@pytest.mark.regression
@pytest.mark.pos
def test_add_slot_via_form_increments_slot_count(
    logged_in_organizer_page: Page, settings: Settings,
) -> None:
    page = logged_in_organizer_page
    _, event_id = create_draft_via_ui(page, settings, title_prefix="UI Slots", days_ahead=30)

    slots = SlotsPage(page, str(settings.base_url)).open_for_event(event_id)
    initial = slots.slot_count()

    slot_start = (datetime.now() + timedelta(days=31)).strftime("%Y-%m-%dT%H:%M")
    slots.fill_slot_form(starts_at=slot_start, capacity=20, label="Группа A")
    slots.submit_slot_form()
    # Ждём появления нового слота в DOM (TanStack Query invalidation)
    page.wait_for_function(
        "() => document.querySelectorAll('[data-testid^=\"btn-delete-slot-\"]').length > 0",
        timeout=8000,
    )

    assert slots.slot_count() == initial + 1


@pytest.mark.regression
@pytest.mark.pos
def test_add_slot_with_capacity_zero_rejected_by_html5(
    logged_in_organizer_page: Page, settings: Settings,
) -> None:
    page = logged_in_organizer_page
    _, event_id = create_draft_via_ui(page, settings, title_prefix="UI Slots", days_ahead=30)

    slots = SlotsPage(page, str(settings.base_url)).open_for_event(event_id)
    initial_count = slots.slot_count()
    initial_url = page.url

    slot_start = (datetime.now() + timedelta(days=32)).strftime("%Y-%m-%dT%H:%M")
    slots.fill_slot_form(starts_at=slot_start, capacity=0)
    with page.expect_response(
        lambda r: "/slots" in r.url and r.request.method == "POST",
        timeout=5000,
    ) as response_info:
        slots.submit_slot_form()
    assert response_info.value.status == 422

    assert page.url == initial_url
    assert slots.slot_count() == initial_count
