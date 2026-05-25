"""Negative: /events требует auth в React SPA."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

from config.settings import Settings


@pytest.mark.neg
@pytest.mark.negative
def test_events_redirects_anonymous_to_login(
    page: Page, settings: Settings, sut_ready: bool,
) -> None:
    page.goto(f"{settings.base_url}/events")
    page.wait_for_load_state("networkidle")
    assert "/login" in page.url
