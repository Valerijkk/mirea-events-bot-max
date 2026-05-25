"""POM для React SPA /organizers (только admin)."""
from __future__ import annotations

from pages.base_page import BasePage
from pages.components.flash_message import FlashMessage


class OrganizersPage(BasePage):
    URL_PATH = "/organizers"

    _heading = "h1"
    _create_button = '[data-testid="btn-create-organizer"]'
    _table = '[data-testid="organizers-table"]'
    _email_input = '[data-testid="input-organizer-email"]'
    _password_input = '[data-testid="input-organizer-password"]'
    _name_input = '[data-testid="input-organizer-name"]'
    _dept_input = '[data-testid="input-organizer-department"]'
    _role_select = '[data-testid="select-organizer-role"]'
    _submit_button = '[data-testid="btn-save-organizer"]'

    @property
    def flash(self) -> FlashMessage:
        return FlashMessage(self._page)

    def open(self, path: str | None = None) -> OrganizersPage:  # type: ignore[override]
        self._page.goto(self.url_for(path))
        self.is_loaded()  # ждём загрузки данных после SPA API-запроса
        return self

    def is_loaded(self, timeout: int = 8000) -> bool:
        try:
            # Ждём появления хотя бы одной кнопки редактирования (данные загружены)
            self._page.locator('[data-testid^="btn-edit-organizer-"]').first.wait_for(
                state="visible", timeout=timeout
            )
            return "/organizers" in self._page.url
        except Exception:
            return False

    def has_create_form(self) -> bool:
        return self._page.locator(self._create_button).count() > 0

    def open_create_modal(self) -> None:
        self._page.locator(self._create_button).click()
        self._page.locator(self._email_input).wait_for(state="visible")

    def fill_create_form(
        self,
        email: str,
        password: str,
        name: str = "",
        department: str = "",
        role: str = "organizer",
    ) -> None:
        self.open_create_modal()
        self._page.locator(self._email_input).fill(email)
        self._page.locator(self._password_input).fill(password)
        if name:
            self._page.locator(self._name_input).fill(name)
        if department:
            self._page.locator(self._dept_input).fill(department)
        # select-organizer-role — кастомный Select (button + ul), не нативный <select>
        self._page.locator(self._role_select).click()
        # Ждём рендера dropdown (React state update асинхронный)
        self._page.locator('[role="option"]').first.wait_for(state="visible", timeout=3000)
        # Ищем по data-value (надёжнее отображаемого текста)
        opt = self._page.locator(f'[role="option"][data-value="{role}"]')
        if opt.count() > 0:
            opt.first.click()
        else:
            # Fallback: первый доступный option
            self._page.locator('[role="option"]').first.click()

    def submit_create(self) -> None:
        self._page.locator(self._submit_button).click()

    def organizer_count(self) -> int:
        return self._page.locator(f"{self._table} tbody tr").count()

    def has_organizer_with_email(self, email: str) -> bool:
        return self._page.locator(f"{self._table} tbody tr").filter(has_text=email).count() > 0

    def edit_buttons_visible(self) -> int:
        return self._page.locator('[data-testid^="btn-edit-organizer-"]').count()
