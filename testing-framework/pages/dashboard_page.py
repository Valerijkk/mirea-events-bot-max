"""POM для главной после логина — React редиректит на /events."""
from __future__ import annotations

from pages.base_page import BasePage
from pages.components.nav_bar import NavBar


class DashboardPage(BasePage):
    URL_PATH = "/events"

    # events-page — корневой контейнер /events (есть всегда, включая empty state).
    # events-grid появляется только при наличии событий — для отдельных проверок.
    _events_table = '[data-testid="events-page"]'
    _create_button = '[data-testid="btn-create-event"]'

    @property
    def nav(self) -> NavBar:
        return NavBar(self._page)

    def is_loaded(self, timeout: int = 8000) -> bool:
        try:
            self._page.locator(self._events_table).wait_for(state="visible", timeout=timeout)
            return "/events" in self._page.url and "login" not in self._page.url
        except Exception:
            return False

    def has_create_button(self) -> bool:
        return self._page.locator(self._create_button).count() > 0

    def click_create_event(self) -> None:
        self._page.click(self._create_button)
