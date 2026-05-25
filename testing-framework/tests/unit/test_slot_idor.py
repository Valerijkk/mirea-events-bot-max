"""Тест на IDOR при удалении слота (SEC-V2 HIGH-1).

Bob не должен мочь удалить слот Alice, даже если знает его id. Защита
реализована параметром `event_id` в `delete_slot`: если слот принадлежит
другому мероприятию — функция возвращает False и не удаляет.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models import EventSlot, EventStatus, EventType, Organizer
from app.services.slots import create_slot, delete_slot


def _make_event_for(session, organizer, capacity=10):
    from app.models import Event
    ev = Event(
        title="Test",
        event_type=EventType.OTHER,
        starts_at=datetime.utcnow() + timedelta(days=7),
        location="x",
        capacity=capacity,
        organizer_id=organizer.id,
        status=EventStatus.PUBLISHED,
    )
    session.add(ev)
    session.commit()
    return ev


def test_delete_slot_with_wrong_event_id_does_not_delete(session):
    alice = Organizer(email="a@m.ru", password_hash="x", name="A", role="organizer")
    bob = Organizer(email="b@m.ru", password_hash="x", name="B", role="organizer")
    session.add_all([alice, bob])
    session.commit()
    alice_event = _make_event_for(session, alice)
    bob_event = _make_event_for(session, bob)

    alice_slot = create_slot(
        session,
        event_id=alice_event.id,
        starts_at=datetime.utcnow() + timedelta(hours=1),
        capacity=5,
    )
    session.commit()

    # Bob знает id чужого слота, прикладывает его к своему event_id.
    result = delete_slot(session, slot_id=alice_slot.id, event_id=bob_event.id)

    assert result is False
    still_there = session.get(EventSlot, alice_slot.id)
    assert still_there is not None
    assert still_there.event_id == alice_event.id


def test_delete_slot_with_matching_event_id_deletes(session):
    """Sanity-check: с правильным event_id удаление работает."""
    alice = Organizer(email="a2@m.ru", password_hash="x", name="A", role="organizer")
    session.add(alice)
    session.commit()
    event = _make_event_for(session, alice)
    slot = create_slot(
        session,
        event_id=event.id,
        starts_at=datetime.utcnow() + timedelta(hours=1),
        capacity=5,
    )
    session.commit()

    result = delete_slot(session, slot_id=slot.id, event_id=event.id)

    assert result is True
    assert session.get(EventSlot, slot.id) is None


def test_delete_slot_without_event_id_param_works_as_before(session):
    """Совместимость: без event_id функция работает по-старому."""
    alice = Organizer(email="a3@m.ru", password_hash="x", name="A", role="organizer")
    session.add(alice)
    session.commit()
    event = _make_event_for(session, alice)
    slot = create_slot(
        session,
        event_id=event.id,
        starts_at=datetime.utcnow() + timedelta(hours=1),
        capacity=5,
    )
    session.commit()

    result = delete_slot(session, slot_id=slot.id)

    assert result is True
    assert session.get(EventSlot, slot.id) is None
