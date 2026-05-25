"""Хелпер для извлечения скрытого _csrf-поля из формы."""
from __future__ import annotations

from playwright.sync_api import Page


class CsrfForm:
    def __init__(self, page: Page) -> None:
        self._page = page

    def csrf_token(self) -> str | None:
        loc = self._page.locator('input[name="_csrf"]').first
        if loc.count() == 0:
            return None
        try:
            return loc.get_attribute("value", timeout=1000)
        except Exception:
            return None

    def csrf_cookie(self) -> str | None:
        # csrf_token также дублируется в cookie с тем же именем.
        for cookie in self._page.context.cookies():
            if cookie.get("name") == "csrf_token":
                return cookie.get("value")
        return None
