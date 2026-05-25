"""POM для модальной формы создания/редактирования мероприятия (React EventForm)."""
from __future__ import annotations

from pages.base_page import BasePage
from pages.components.flash_message import FlashMessage
from pages.events_list_page import EventsListPage


class EventFormPage(BasePage):
    _title = '[data-testid="input-event-title"]'
    _description = '[data-testid="input-event-description"]'
    _event_type = '[data-testid="select-event-type"]'
    _capacity = '[data-testid="input-event-capacity"]'
    _starts_at = '[data-testid="input-event-starts"]'
    _format = '[data-testid="select-event-format"]'
    _location = '[data-testid="input-event-location"]'
    _meeting_url = '[data-testid="input-event-meeting-url"]'
    _submit = '[data-testid="btn-save-event"]'

    @property
    def flash(self) -> FlashMessage:
        return FlashMessage(self._page)

    def open(self, path: str | None = None) -> EventFormPage:  # type: ignore[override]
        EventsListPage(self._page, self._base_url).open()
        self._page.locator('[data-testid="btn-create-event"]').click()
        self._page.locator(self._title).wait_for(state="visible")
        return self

    def fill_title(self, value: str) -> EventFormPage:
        self._page.fill(self._title, value)
        return self

    def fill_description(self, value: str) -> EventFormPage:
        self._page.fill(self._description, value)
        return self

    def _select_custom(self, trigger_testid: str, value: str) -> None:
        """Выбор значения в кастомном Select-компоненте (button + ul/li)."""
        self._page.locator(f'[data-testid="{trigger_testid}"]').click()
        # Ждём появления хотя бы одного option
        self._page.locator('[role="option"]').first.wait_for(state="visible", timeout=3000)
        # Ищем по data-value (надёжнее отображаемого текста)
        opt = self._page.locator(f'[role="option"][data-value="{value}"]')
        if opt.count() > 0:
            opt.first.click()
        else:
            # Fallback: любой option с совпадающим текстом
            self._page.locator('[role="option"]').filter(has_text=value).first.click()

    def select_event_type(self, value: str) -> EventFormPage:
        self._select_custom("select-event-type", value)
        return self

    def fill_capacity(self, value: int) -> EventFormPage:
        self._page.fill(self._capacity, str(value))
        return self

    def fill_starts_at(self, iso_local: str) -> EventFormPage:
        self._page.fill(self._starts_at, iso_local)
        return self

    def select_format(self, fmt: str) -> EventFormPage:
        self._select_custom("select-event-format", fmt)
        return self

    def fill_location(self, value: str) -> EventFormPage:
        self._page.fill(self._location, value)
        return self

    def fill_meeting_url(self, value: str) -> EventFormPage:
        self._page.fill(self._meeting_url, value)
        return self

    def submit(self) -> None:
        self._page.click(self._submit)

    def title_is_invalid(self) -> bool:
        return self._page.locator(f"{self._title}:invalid").count() > 0

    def capacity_is_invalid(self) -> bool:
        return self._page.locator(f"{self._capacity}:invalid").count() > 0

    def modal_is_open(self) -> bool:
        return self._page.locator(self._title).count() > 0
