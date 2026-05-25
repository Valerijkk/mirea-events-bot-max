"""Smoke-тесты конструкторов inline-клавиатур — фиксируют payload-формат МАКС:
`{"type": "inline_keyboard", "payload": {"buttons": [[...], ...]}}`.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.bot.keyboards import (
    cancel_confirm_kb,
    consent_kb,
    event_card_kb,
    events_list_kb,
    main_menu_kb,
    my_registration_kb,
    signup_summary_kb,
    slot_picker_kb,
)


def _is_inline_keyboard(kb: dict) -> bool:
    """МАКС-контракт: type=inline_keyboard, payload.buttons — список рядов."""
    return (
        isinstance(kb, dict)
        and kb.get("type") == "inline_keyboard"
        and isinstance(kb.get("payload", {}).get("buttons"), list)
    )


def _all_buttons(kb: dict) -> list[dict]:
    """Плоский список всех кнопок из всех рядов."""
    return [btn for row in kb["payload"]["buttons"] for btn in row]


@pytest.mark.parametrize(
    "kb_factory",
    [main_menu_kb, consent_kb],
    ids=["main_menu", "consent"],
)
def test_simple_kbs_have_valid_format(kb_factory):
    """main_menu и consent — параметров нет, проверяем только структуру."""
    kb = kb_factory()
    assert _is_inline_keyboard(kb)
    assert len(_all_buttons(kb)) >= 1


def test_event_card_kb_with_free_slots_shows_signup():
    kb = event_card_kb(event_id=42, has_free_slots=True)
    payloads = [b["payload"] for b in _all_buttons(kb) if b.get("type") == "callback"]
    assert "signup:42" in payloads


def test_event_card_kb_without_free_slots_shows_waitlist():
    kb = event_card_kb(event_id=42, has_free_slots=False)
    callbacks = [b for b in _all_buttons(kb) if b.get("type") == "callback"]
    signup_row = callbacks[:2]
    assert len(signup_row) == 2
    assert signup_row[0]["payload"] == "noop"
    assert signup_row[1]["payload"] == "waitlist:42"


@pytest.mark.pos
def test_event_card_kb_no_free_slots_shows_disabled_and_waitlist_buttons():
    """TC-UNIT-KB-001: при free_slots=0 клавиатура содержит 2 кнопки: disabled noop + активный waitlist."""
    kb = event_card_kb(event_id=42, has_free_slots=False)
    callbacks = [b for b in _all_buttons(kb) if b.get("type") == "callback"]
    signup_row = callbacks[:2]

    assert len(signup_row) == 2
    assert signup_row[0]["payload"] == "noop"
    assert "Мест нет" in signup_row[0]["text"]
    assert signup_row[1]["payload"] == "waitlist:42"
    assert signup_row[1]["payload"].startswith("waitlist:")


def test_event_card_kb_with_registration_closed_hides_signup():
    """Если регистрация закрыта вручную — обе кнопки signup/waitlist прячем."""
    kb = event_card_kb(event_id=42, has_free_slots=True, registration_open=False)
    payloads = [b["payload"] for b in _all_buttons(kb) if b.get("type") == "callback"]
    assert "signup:42" not in payloads
    assert "waitlist:42" not in payloads


def test_event_card_kb_details_button_can_be_hidden():
    """В режиме «уже на странице подробностей» кнопку Подробнее не показываем."""
    kb = event_card_kb(event_id=42, has_free_slots=True, show_details_button=False)
    payloads = [b["payload"] for b in _all_buttons(kb) if b.get("type") == "callback"]
    assert not any(p.startswith("details:") for p in payloads)


def test_events_list_kb_one_button_per_event_plus_back():
    """Список афиши: N кнопок-событий + 1 кнопка «В меню»."""
    fake_events = [
        type("E", (), {"id": i, "title": f"Event {i}"})()
        for i in range(1, 4)
    ]
    kb = events_list_kb(fake_events)
    btns = _all_buttons(kb)
    # 3 события + 1 menu
    assert len(btns) == 4
    payloads = [b["payload"] for b in btns]
    assert "event:1" in payloads and "event:2" in payloads and "event:3" in payloads
    assert "menu" in payloads


def test_my_registration_kb_can_cancel_includes_cancel_button():
    kb = my_registration_kb(registration_id=7, can_cancel=True)
    payloads = [b["payload"] for b in _all_buttons(kb) if b.get("type") == "callback"]
    assert "cancel:7" in payloads


def test_my_registration_kb_no_cancel_omits_button():
    """Для архивных записей (is_past) кнопку отмены не показываем."""
    kb = my_registration_kb(registration_id=7, can_cancel=False)
    payloads = [b["payload"] for b in _all_buttons(kb) if b.get("type") == "callback"]
    assert "cancel:7" not in payloads


@pytest.mark.parametrize(
    "notifications_enabled, expected_callback",
    [(True, "notif_off:7"), (False, "notif_on:7")],
    ids=["mute-button", "unmute-button"],
)
def test_my_registration_kb_toggles_notif_label(
    notifications_enabled: bool, expected_callback: str
):
    """В зависимости от текущего состояния — либо «🔕 Тише», либо «🔔 Снова»."""
    kb = my_registration_kb(
        registration_id=7,
        can_cancel=True,
        notifications_enabled=notifications_enabled,
    )
    payloads = [b["payload"] for b in _all_buttons(kb) if b.get("type") == "callback"]
    assert expected_callback in payloads


def test_signup_summary_kb_without_slot():
    kb = signup_summary_kb(event_id=42, slot_id=None)
    payloads = [b["payload"] for b in _all_buttons(kb) if b.get("type") == "callback"]
    assert "confirm:42" in payloads


def test_signup_summary_kb_with_slot_includes_slot_id():
    kb = signup_summary_kb(event_id=42, slot_id=7)
    payloads = [b["payload"] for b in _all_buttons(kb) if b.get("type") == "callback"]
    assert "confirm:42:7" in payloads


def test_slot_picker_kb_renders_each_slot():
    """Каждый слот → одна кнопка с callback `slot:<event>:<slot>`."""
    now = datetime.utcnow() + timedelta(hours=2)
    slot_a = type("S", (), {"id": 11, "starts_at": now, "label": "Группа A"})()
    slot_b = type("S", (), {"id": 12, "starts_at": now, "label": None})()
    kb = slot_picker_kb(event_id=42, slots_with_free=[(slot_a, 5), (slot_b, 0)])

    btns = _all_buttons(kb)
    payloads = [b["payload"] for b in btns if b.get("type") == "callback"]
    assert "slot:42:11" in payloads
    assert "slot:42:12" in payloads
    # Слот с 0 мест получает суффикс «нет мест» в подписи
    texts = [b["text"] for b in btns if b.get("type") == "callback"]
    assert any("нет мест" in t for t in texts)


def test_cancel_confirm_kb_has_yes_no_buttons():
    kb = cancel_confirm_kb(registration_id=99)
    payloads = [b["payload"] for b in _all_buttons(kb) if b.get("type") == "callback"]
    assert "cancel_yes:99" in payloads
    assert "cancel_no:99" in payloads
