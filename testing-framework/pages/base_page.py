"""Базовый POM — общие операции (open, screenshot, wait_for_url)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import TypeVar

from playwright.sync_api import Page

from core.artifacts import screenshot_path

TPage = TypeVar("TPage", bound="BasePage")


class BasePage:
    URL_PATH: str = ""

    def __init__(self, page: Page, base_url: str) -> None:
        self._page = page
        self._base_url = base_url.rstrip("/")

    @property
    def page(self) -> Page:
        return self._page

    @property
    def base_url(self) -> str:
        return self._base_url

    def url_for(self, path: str | None = None) -> str:
        suffix = path if path is not None else self.URL_PATH
        if suffix and not suffix.startswith("/"):
            suffix = "/" + suffix
        return self._base_url + suffix

    def open(self: TPage, path: str | None = None) -> TPage:
        self._page.goto(self.url_for(path))
        return self

    def wait_for_url(self, pattern: str | re.Pattern[str], timeout: int = 5000) -> None:
        self._page.wait_for_url(pattern, timeout=timeout)

    def current_url(self) -> str:
        return self._page.url

    def screenshot(self, name: str) -> Path:
        target = screenshot_path(name, "snapshot")
        self._page.screenshot(path=str(target), full_page=True)
        return target

    def has_text(self, text: str) -> bool:
        return self._page.get_by_text(text).count() > 0
