"""Negative: /organizers — AdminRoute в React SPA."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

from config.settings import Settings


@pytest.mark.neg
@pytest.mark.negative
@pytest.mark.regression
def test_organizer_redirected_from_organizers_page(
    logged_in_organizer_page: Page, settings: Settings,
) -> None:
    logged_in_organizer_page.goto(f"{settings.base_url}/organizers")
    logged_in_organizer_page.wait_for_load_state("networkidle")
    assert "/organizers" not in logged_in_organizer_page.url
    assert "/events" in logged_in_organizer_page.url


@pytest.mark.neg
@pytest.mark.negative
def test_anonymous_redirected_from_organizers_page(
    page: Page, settings: Settings, sut_ready: bool,
) -> None:
    page.goto(f"{settings.base_url}/organizers")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url
