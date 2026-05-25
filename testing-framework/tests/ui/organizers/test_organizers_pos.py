"""Positive: /organizers — только admin."""
from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import Page

from config.settings import Settings
from pages.organizers_page import OrganizersPage


@pytest.mark.smoke
def test_admin_can_open_organizers_page(
    logged_in_admin_page: Page, settings: Settings,
) -> None:
    page = OrganizersPage(logged_in_admin_page, str(settings.base_url)).open()
    assert page.is_loaded()
    assert page.has_create_form()
    assert page.organizer_count() >= 2


@pytest.mark.regression
def test_admin_creates_new_organizer(
    logged_in_admin_page: Page, settings: Settings,
) -> None:
    page = OrganizersPage(logged_in_admin_page, str(settings.base_url)).open()
    new_email = f"qa-org-{uuid.uuid4().hex[:8]}@mirea.ru"

    initial = page.organizer_count()
    page.fill_create_form(
        email=new_email,
        password="testpass1234",
        name="QA Тестовый Организатор",
        department="Кафедра тестирования",
        role="organizer",
    )
    page.submit_create()
    # Ждём появления нового организатора в таблице (TanStack Query инвалидирует и перезагружает)
    logged_in_admin_page.wait_for_function(
        f"() => document.body.innerText.includes({new_email!r})",
        timeout=8000,
    )

    refreshed = OrganizersPage(logged_in_admin_page, str(settings.base_url))
    assert refreshed.organizer_count() == initial + 1
    assert refreshed.has_organizer_with_email(new_email)


@pytest.mark.regression
def test_admin_sees_edit_buttons(
    logged_in_admin_page: Page, settings: Settings,
) -> None:
    page = OrganizersPage(logged_in_admin_page, str(settings.base_url)).open()
    assert page.edit_buttons_visible() >= 1
