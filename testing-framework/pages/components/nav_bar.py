"""Навбар React SPA — переходы по тексту ссылок."""
from __future__ import annotations

from playwright.sync_api import Page


class NavBar:
    def __init__(self, page: Page) -> None:
        self._page = page

    def go_to_events(self) -> None:
        self._page.get_by_role("link", name="Мероприятия").click()

    def go_to_organizers(self) -> None:
        self._page.get_by_role("link", name="Организаторы").click()

    def has_organizers_link(self) -> bool:
        return self._page.get_by_role("link", name="Организаторы").count() > 0
