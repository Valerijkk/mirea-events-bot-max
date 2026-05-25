"""POM для React SPA /events/{id}."""
from __future__ import annotations

from pages.base_page import BasePage
from pages.components.flash_message import FlashMessage


class EventDetailPage(BasePage):
    _root = '[data-testid="event-detail"]'
    _publish_button = '[data-testid="btn-publish"]'
    _cancel_button = '[data-testid="btn-cancel-event"]'
    _duplicate_button = '[data-testid="btn-duplicate-event"]'
    _participants_table = '[data-testid="participants-table"]'
    _code_search = '[data-testid="input-reg-code-search"]'

    @property
    def flash(self) -> FlashMessage:
        return FlashMessage(self._page)

    def open_for_event(self, event_id: int) -> EventDetailPage:
        return self.open(f"/events/{event_id}")

    def is_loaded(self, timeout: int = 8000) -> bool:
        try:
            self._page.locator(self._root).wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def wait_for_status(self, label: str, timeout: int = 10000) -> None:
        root = self._page.locator(self._root)
        root.wait_for(state="visible", timeout=timeout)
        root.get_by_text(label, exact=True).wait_for(state="visible", timeout=timeout)

    def has_status(self, label: str) -> bool:
        return self._page.locator(self._root).get_by_text(label, exact=True).count() > 0

    def has_publish_button(self) -> bool:
        return self._page.locator(self._publish_button).count() > 0

    def has_cancel_button(self) -> bool:
        return self._page.locator(self._cancel_button).count() > 0

    def has_duplicate_button(self) -> bool:
        return self._page.locator(self._duplicate_button).count() > 0

    def click_publish(self) -> None:
        self._page.locator(self._publish_button).first.click()

    def click_cancel(self) -> None:
        self._page.locator(self._cancel_button).first.click()

    def click_duplicate(self) -> None:
        self._page.locator(self._duplicate_button).first.click()

    def search_participant(self, code: str) -> None:
        self._page.locator(self._code_search).fill(code)

    def participant_row_count(self) -> int:
        return self._page.locator(f"{self._participants_table} tbody tr").count()

    def go_to_slots(self) -> None:
        self._page.get_by_role("link", name="Слоты").click()

    def go_to_scanner(self) -> None:
        self._page.get_by_role("link", name="Сканер").click()
