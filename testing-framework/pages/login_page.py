"""POM для React SPA /login."""
from __future__ import annotations

from pages.base_page import BasePage
from pages.components.flash_message import FlashMessage


class LoginPage(BasePage):
    URL_PATH = "/login"

    _email_input = '[data-testid="input-email"]'
    _password_input = '[data-testid="input-password"]'
    _submit_button = '[data-testid="btn-login"]'
    _error_text = '[data-testid="login-error"], div[class*="bg-red-50"], form p.text-red-600'

    @property
    def flash(self) -> FlashMessage:
        return FlashMessage(self._page)

    def fill_email(self, value: str) -> LoginPage:
        self._page.fill(self._email_input, value)
        return self

    def fill_password(self, value: str) -> LoginPage:
        self._page.fill(self._password_input, value)
        return self

    def submit(self) -> None:
        self._page.click(self._submit_button)

    def is_displayed(self) -> bool:
        return self._page.locator(self._email_input).count() > 0

    def login_with(self, email: str, password: str) -> None:
        self.open()
        self.fill_email(email)
        self.fill_password(password)
        self.submit()

    def email_input_is_invalid(self) -> bool:
        return self._page.locator(f"{self._email_input}:invalid").count() > 0

    def error_text(self, timeout: int = 3000) -> str | None:
        try:
            loc = self._page.locator(self._error_text).first
            loc.wait_for(state="visible", timeout=timeout)
            return loc.text_content()
        except Exception:
            return None
