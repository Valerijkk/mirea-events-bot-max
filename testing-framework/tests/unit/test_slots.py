"""Тесты слотов: запись на слот, независимый waitlist, валидация slot_id.

Слот — временное окно у мероприятия с собственной capacity и собственной очередью.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import EventSlot, RegStatus
from app.services.registration import (
    cancel_registration,
    sign_up,
    upsert_user,
)
from app.services.slots import create_slot, delete_slot, list_slots


def _make_users(session, count: int) -> None:
    for i in range(count):
        uid = 1000 + i
        upsert_user(session, max_user_id=uid, chat_id=uid, name=f"U{uid}")
    session.flush()


def _add_slot(session, event, capacity=2, hours_from_now=2, label=None) -> EventSlot:
    return create_slot(
        session,
        event_id=event.id,
        starts_at=datetime.utcnow() + timedelta(hours=hours_from_now),
        capacity=capacity,
        label=label,
    )


# ---------------------------------------------------------------------------
# Базовые операции
# ---------------------------------------------------------------------------

def test_create_slot_attaches_to_event(session, event_factory):
    event = event_factory(capacity=10)

    slot = _add_slot(session, event, capacity=5, label="Группа A")
    session.commit()

    assert slot.event_id == event.id
    assert slot.label == "Группа A"
    assert slot.capacity == 5


def test_list_slots_returns_sorted_by_starts_at(session, event_factory):
    event = event_factory(capacity=10)
    _add_slot(session, event, hours_from_now=10)
    _add_slot(session, event, hours_from_now=2)
    _add_slot(session, event, hours_from_now=5)
    session.commit()

    result = list_slots(session, event.id)

    times = [s.starts_at for s in result]
    assert times == sorted(times)


def test_delete_slot_returns_false_for_unknown(session):
    assert delete_slot(session, slot_id=99999) is False


# ---------------------------------------------------------------------------
# sign_up с slot_id
# ---------------------------------------------------------------------------

def test_signup_on_slot_uses_slot_capacity(session, event_factory):
    # event.capacity=10, slot.capacity=2 — побеждает slot
    event = event_factory(capacity=10)
    slot = _add_slot(session, event, capacity=2)
    session.commit()
    _make_users(session, 3)

    r1 = sign_up(session, event_id=event.id, user_id=1000, slot_id=slot.id)
    r2 = sign_up(session, event_id=event.id, user_id=1001, slot_id=slot.id)
    r3 = sign_up(session, event_id=event.id, user_id=1002, slot_id=slot.id)

    assert r1.is_waitlist is False
    assert r2.is_waitlist is False
    assert r3.is_waitlist is True
    assert r3.waitlist_position == 1


def test_signup_different_slots_dont_share_capacity(session, event_factory):
    event = event_factory(capacity=10)
    slot_a = _add_slot(session, event, capacity=1, hours_from_now=2)
    slot_b = _add_slot(session, event, capacity=1, hours_from_now=4)
    session.commit()
    _make_users(session, 2)

    r_a = sign_up(session, event_id=event.id, user_id=1000, slot_id=slot_a.id)
    r_b = sign_up(session, event_id=event.id, user_id=1001, slot_id=slot_b.id)

    assert r_a.is_waitlist is False
    assert r_b.is_waitlist is False


def test_signup_on_event_with_slots_without_slot_id_raises(session, event_factory):
    event = event_factory(capacity=10)
    _add_slot(session, event, capacity=1)
    session.commit()
    _make_users(session, 1)

    with pytest.raises(ValueError, match="выберите конкретное время"):
        sign_up(session, event_id=event.id, user_id=1000, slot_id=None)


def test_signup_with_alien_slot_raises(session, event_factory):
    event_a = event_factory(capacity=10)
    event_b = event_factory(capacity=10)
    alien_slot = _add_slot(session, event_a, capacity=1)
    _add_slot(session, event_b, capacity=1)  # чтобы у event_b были слоты
    session.commit()
    _make_users(session, 1)

    with pytest.raises(ValueError, match="не принадлежит"):
        sign_up(session, event_id=event_b.id, user_id=1000, slot_id=alien_slot.id)


def test_cancel_on_slot_promotes_waitlist_of_same_slot(session, event_factory):
    event = event_factory(capacity=10)
    slot = _add_slot(session, event, capacity=1)
    session.commit()
    _make_users(session, 3)

    r1 = sign_up(session, event_id=event.id, user_id=1000, slot_id=slot.id)
    sign_up(session, event_id=event.id, user_id=1001, slot_id=slot.id)
    sign_up(session, event_id=event.id, user_id=1002, slot_id=slot.id)

    result = cancel_registration(session, registration_id=r1.registration.id, user_id=1000)

    assert result.cancelled is True
    promoted = result.promoted_registration
    assert promoted is not None
    assert promoted.user_id == 1001
    assert promoted.status == RegStatus.CONFIRMED
