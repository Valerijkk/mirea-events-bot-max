"""Positive: страница карточки /events/{id}."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

from config.settings import Settings
from pages.event_detail_page import EventDetailPage
from steps.ui.event_steps import create_draft_via_ui


@pytest.mark.regression
def test_publish_draft_changes_status_to_published(
    logged_in_organizer_page: Page, settings: Settings,
) -> None:
    page = logged_in_organizer_page
    create_draft_via_ui(page, settings, title_prefix="UI Detail")

    detail = EventDetailPage(page, str(settings.base_url))
    assert detail.has_publish_button(), "Черновик должен иметь кнопку публикации"

    detail.click_publish()
    page.wait_for_load_state("networkidle")
    assert not detail.has_publish_button()
