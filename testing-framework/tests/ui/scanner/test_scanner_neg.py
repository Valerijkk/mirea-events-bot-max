"""Negative: ручной ввод на /events/{id}/scanner."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page

from config.settings import Settings
from core.api_client import ApiClient
from pages.scanner_page import ScannerPage
from utils.test_helpers import first_owned_event


@pytest.mark.neg
def test_scanner_rejects_invalid_qr_code(
    logged_in_organizer_page: Page,
    settings: Settings,
    api_as_organizer: ApiClient,
) -> None:
    event = first_owned_event(api_as_organizer)
    if event is None:
        pytest.skip("Нет событий для сканера.")

    page = ScannerPage(logged_in_organizer_page, str(settings.base_url)).open_for_event(
        event["id"]
    )
    page.submit_code("INVALID-NONEXISTENT-CODE-99999")
    logged_in_organizer_page.locator('[data-testid="scanner-result"]').first.wait_for(
        state="visible", timeout=settings.ui_default_timeout_ms,
    )
    text = page.result_text().lower()
    assert any(
        marker in text
        for marker in ("не найден", "не валид", "ошибк", "error", "погашен", "отмен")
    ), f"Ожидалась ошибка, получено: {text!r}"


@pytest.mark.neg
def test_scanner_rejects_empty_input(
    logged_in_organizer_page: Page,
    settings: Settings,
    api_as_organizer: ApiClient,
) -> None:
    event = first_owned_event(api_as_organizer)
    if event is None:
        pytest.skip("Нет событий для сканера.")

    ScannerPage(logged_in_organizer_page, str(settings.base_url)).open_for_event(event["id"])
    initial_url = logged_in_organizer_page.url

    logged_in_organizer_page.locator('[data-testid="btn-manual-scan"]').first.click()
    logged_in_organizer_page.locator('[data-testid="input-manual-code"]').wait_for(
        state="visible", timeout=settings.ui_default_timeout_ms,
    )

    assert logged_in_organizer_page.url == initial_url
