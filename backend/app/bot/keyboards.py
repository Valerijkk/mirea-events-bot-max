"""Конструкторы inline-клавиатур для MAX Bot API.

MAX-формат attachment'а — `{"type": "inline_keyboard", "payload": {"buttons": [[...]]}}`.
Callback-payload компактный — у MAX лимит на длину.

Словарь payload'ов:
    event:<id>           — карточка мероприятия
    details:<id>         — «Подробнее»
    signup:<id>          — записаться (открывает выбор слота или сводку)
    slot:<id>:<slot_id>  — выбран слот
    confirm:<id>[:<slot>]— подтверждение записи после сводки
    waitlist:<id>        — встать в лист ожидания
    cancel:<reg_id>      — открыть подтверждение отмены
    cancel_yes/no:<reg>  — подтвердить/отказаться
    notif_off/on:<reg>   — переключить уведомления по записи
    ics:<reg_id>         — ссылка в календарь
    consent              — согласие на обработку данных
    menu                 — главное меню
"""
from __future__ import annotations

from typing import Any

from app.bot.texts import BTN


def _callback(text: str, payload: str) -> dict[str, Any]:
    return {"type": "callback", "text": text, "payload": payload}


def _link(text: str, url: str) -> dict[str, Any]:
    return {"type": "link", "text": text, "url": url}


def _inline_keyboard(rows: list[list[dict[str, Any]]]) -> dict[str, Any]:
    return {"type": "inline_keyboard", "payload": {"buttons": rows}}


# MAX не поддерживает «постоянную reply-клавиатуру внизу» — рендерим inline.

def main_menu_kb() -> dict[str, Any]:
    return _inline_keyboard([
        [_callback(BTN.EVENTS, "events"), _callback(BTN.MY, "my")],
        [_callback(BTN.HELP, "help")],
    ])


def event_card_kb(
    event_id: int,
    has_free_slots: bool,
    *,
    registration_open: bool = True,
    show_details_button: bool = True,
) -> dict[str, Any]:
    """`registration_open=False` — ТЗ-статус «Регистрация закрыта»: оставляем
    только «Подробнее» и «В меню», действия записи скрываем.
    """
    rows: list[list[dict[str, Any]]] = []
    if registration_open:
        if has_free_slots:
            rows.append([_callback(BTN.SIGNUP, f"signup:{event_id}")])
        else:
            rows.append([_callback("🚫 Мест нет", "noop")])
            rows.append([_callback("⏳ Встать в очередь", f"waitlist:{event_id}")])
    if show_details_button:
        rows.append([_callback(BTN.DETAILS, f"details:{event_id}")])
    rows.append([_callback(BTN.BACK, "menu")])
    return _inline_keyboard(rows)


def slot_picker_kb(event_id: int, slots_with_free: list[tuple]) -> dict[str, Any]:
    """Слот с `free=0` помечаем «нет мест», но клик ставит в waitlist."""
    rows: list[list[dict[str, Any]]] = []
    for slot, free in slots_with_free:
        label = slot.label or slot.starts_at.strftime("%d.%m %H:%M")
        suffix = " — нет мест" if free == 0 else f" — свободно {free}"
        rows.append([_callback(label + suffix, f"slot:{event_id}:{slot.id}")])
    rows.append([_callback(BTN.BACK, f"event:{event_id}")])
    return _inline_keyboard(rows)


def signup_summary_kb(event_id: int, slot_id: int | None) -> dict[str, Any]:
    payload = f"confirm:{event_id}" if slot_id is None else f"confirm:{event_id}:{slot_id}"
    return _inline_keyboard([
        [_callback("✅ Подтверждаю", payload)],
        [_callback(BTN.BACK, f"event:{event_id}")],
    ])


def consent_kb() -> dict[str, Any]:
    return _inline_keyboard([
        [_callback("✅ Я согласен", "consent")],
    ])


def events_list_kb(events: list) -> dict[str, Any]:
    rows = [[_callback(f"{e.title}  ›", f"event:{e.id}")] for e in events]
    rows.append([_callback(BTN.BACK, "menu")])
    return _inline_keyboard(rows)


def my_registration_kb(
    registration_id: int,
    can_cancel: bool,
    *,
    notifications_enabled: bool = True,
) -> dict[str, Any]:
    """`notifications_enabled` — per-event флаг (ТЗ требует именно per-event)."""
    rows: list[list[dict[str, Any]]] = []
    rows.append([_callback("🎫 Получить QR", f"qr:{registration_id}")])
    if can_cancel:
        rows.append([_callback(BTN.CANCEL, f"cancel:{registration_id}")])
    rows.append([_callback(BTN.ADD_TO_CALENDAR, f"ics:{registration_id}")])
    if notifications_enabled:
        rows.append([_callback("🔕 Тише по этому", f"notif_off:{registration_id}")])
    else:
        rows.append([_callback("🔔 Снова с уведомлениями", f"notif_on:{registration_id}")])
    return _inline_keyboard(rows)


def cancel_confirm_kb(registration_id: int) -> dict[str, Any]:
    return _inline_keyboard([
        [_callback(BTN.CONFIRM_CANCEL, f"cancel_yes:{registration_id}")],
        [_callback(BTN.KEEP, f"cancel_no:{registration_id}")],
    ])


def calendar_link_kb(url: str) -> dict[str, Any]:
    """Инлайн-клавиатура со ссылкой на Google Calendar."""
    return _inline_keyboard([[_link("📅 Открыть Google Calendar", url)]])
