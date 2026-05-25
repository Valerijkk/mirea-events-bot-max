"""POM для React SPA /events."""
from __future__ import annotations

from pages.base_page import BasePage


class EventsListPage(BasePage):
    URL_PATH = "/events"

    _events_table = '[data-testid="events-page"]'
    _create_button = '[data-testid="btn-create-event"]'
    _event_link = '[data-testid^="event-link-"]'

    def open(self, path: str | None = None) -> EventsListPage:  # type: ignore[override]
        self._page.goto(self.url_for(path))
        # Ждём пока SPA завершит загрузку данных через API
        try:
            self._page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        self.is_loaded()
        return self

    def is_loaded(self, timeout: int = 8000) -> bool:
        try:
            self._page.locator(self._events_table).wait_for(state="visible", timeout=timeout)
            return "/events" in self._page.url
        except Exception:
            return False

    def click_create_button(self) -> None:
        self._page.locator(self._create_button).first.click()

    def card_titles(self) -> list[str]:
        links = self._page.locator(self._event_link)
        return [links.nth(i).text_content() or "" for i in range(links.count())]

    def card_count(self) -> int:
        return self._page.locator(self._event_link).count()

    def has_card_with_title(self, title: str) -> bool:
        return any(title.lower() in t.lower() for t in self.card_titles())

    def open_card_by_title(self, title: str) -> None:
        self._page.locator(self._event_link).filter(has_text=title).first.click()

    def event_id_by_title(self, title: str) -> int | None:
        link = self._page.locator(self._event_link).filter(has_text=title).first
        if link.count() == 0:
            return None
        testid = link.get_attribute("data-testid") or ""
        if not testid.startswith("event-link-"):
            return None
        return int(testid.removeprefix("event-link-"))
