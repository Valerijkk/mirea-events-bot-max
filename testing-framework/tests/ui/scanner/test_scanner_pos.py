"""Positive: сканер /events/{id}/scanner."""
from __future__ import annotations

from playwright.sync_api import Page

from config.settings import Settings
from core.api_client import ApiClient
from pages.scanner_page import ScannerPage
from utils.test_helpers import first_owned_event


def test_scanner_page_loads_with_manual_form(
    logged_in_admin_page: Page,
    settings: Settings,
    api_as_admin: ApiClient,
) -> None:
    event = first_owned_event(api_as_admin)
    if event is None:
        import pytest
        pytest.skip("Нет событий для сканера.")

    scanner = ScannerPage(logged_in_admin_page, str(settings.base_url))
    scanner.open_for_event(event["id"])
    assert scanner.is_loaded()
