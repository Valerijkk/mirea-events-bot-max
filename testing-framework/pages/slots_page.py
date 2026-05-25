"""POM для React SPA /events/{id}/slots."""
from __future__ import annotations

from pages.base_page import BasePage


class SlotsPage(BasePage):
    _slots_list = '[data-testid="slots-list"]'
    _slot_starts = '[data-testid="input-slot-starts"]'
    _slot_ends = '[data-testid="input-slot-ends"]'
    _slot_capacity = '[data-testid="input-slot-capacity"]'
    _slot_label = '[data-testid="input-slot-label"]'
    _slot_submit = '[data-testid="btn-add-slot"]'

    def open_for_event(self, event_id: int) -> SlotsPage:
        self._page.goto(self.url_for(f"/events/{event_id}/slots"))
        try:
            self._page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        return self

    def is_loaded(self, timeout: int = 8000) -> bool:
        try:
            self._page.locator(self._slot_submit).wait_for(state="visible", timeout=timeout)
            return "/slots" in self._page.url
        except Exception:
            return False

    def slot_count(self) -> int:
        # Считаем только реальные слоты (с кнопкой удаления), не placeholder "Слотов пока нет"
        selector = f'{self._slots_list} > li [data-testid^="btn-delete-slot-"]'
        return self._page.locator(selector).count()

    def fill_slot_form(
        self,
        starts_at: str,
        capacity: int,
        label: str = "",
        ends_at: str = "",
    ) -> None:
        self._page.locator(self._slot_starts).fill(starts_at)
        if ends_at:
            self._page.locator(self._slot_ends).fill(ends_at)
        self._page.locator(self._slot_capacity).fill(str(capacity))
        if label:
            self._page.locator(self._slot_label).fill(label)

    def submit_slot_form(self) -> None:
        self._page.locator(self._slot_submit).click()
