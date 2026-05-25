"""Алерты React SPA — error/success через Tailwind-классы и text-red-600."""
from __future__ import annotations

from playwright.sync_api import Page


class FlashMessage:
    _error_selector = 'p.text-red-600, div.text-red-600, div[class*="bg-red-50"]'
    _warn_selector = 'div.bg-amber-50, div[class*="bg-amber-50"], p.text-amber-700'
    _success_selector = 'div.bg-emerald-50, div[class*="bg-emerald-50"], div[class*="bg-green-50"]'

    def __init__(self, page: Page) -> None:
        self._page = page

    def error_text(self) -> str | None:
        loc = self._page.locator(self._error_selector).first
        if loc.count() == 0:
            return None
        try:
            return loc.text_content(timeout=1000)
        except Exception:
            return None

    def warn_text(self) -> str | None:
        loc = self._page.locator(self._warn_selector).first
        if loc.count() == 0:
            return None
        try:
            return loc.text_content(timeout=1000)
        except Exception:
            return None

    def has_error(self) -> bool:
        return self._page.locator(self._error_selector).count() > 0

    def has_warn(self) -> bool:
        return self._page.locator(self._warn_selector).count() > 0
