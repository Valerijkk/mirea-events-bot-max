"""POM для React SPA /events/{id}/scanner."""
from __future__ import annotations

from pages.base_page import BasePage


class ScannerPage(BasePage):
    _manual_input = '[data-testid="input-manual-code"]'
    _submit_button = '[data-testid="btn-manual-scan"]'
    _result = '[data-testid="scanner-result"]'

    def open_for_event(self, event_id: int) -> ScannerPage:
        return self.open(f"/events/{event_id}/scanner")

    def is_loaded(self, timeout: int = 8000) -> bool:
        try:
            self._page.locator(self._manual_input).wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def submit_code(self, code: str) -> None:
        self._page.fill(self._manual_input, code)
        self._page.locator(self._submit_button).first.click()

    def result_text(self) -> str:
        loc = self._page.locator(self._result).first
        if loc.count() == 0:
            return ""
        return loc.text_content() or ""
