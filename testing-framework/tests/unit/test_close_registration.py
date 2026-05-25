"""Тесты «закрыть регистрацию»: sign_up блокируется, существующие записи живы."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import EventStatus
from app.services.registration import sign_up, upsert_user


def test_signup_blocked_when_registration_closed(session, event_factory):
    event = event_factory(capacity=10)
    event.registration_open = False
    session.commit()
    upsert_user(session, max_user_id=42, chat_id=42, name="Test")

    with pytest.raises(ValueError, match="закрыта"):
        sign_up(session, event_id=event.id, user_id=42)


def test_signup_blocked_when_event_already_started(session, event_factory):
    event = event_factory(capacity=10)
    event.starts_at = datetime.utcnow() - timedelta(minutes=5)
    session.commit()
    upsert_user(session, max_user_id=42, chat_id=42, name="Test")

    with pytest.raises(ValueError, match="началось"):
        sign_up(session, event_id=event.id, user_id=42)


def test_can_accept_registrations_returns_true_for_normal_event(session, event_factory):
    event = event_factory(capacity=10)
    assert event.can_accept_registrations() is True


def test_can_accept_registrations_returns_false_when_closed(session, event_factory):
    event = event_factory(capacity=10)
    event.registration_open = False
    assert event.can_accept_registrations() is False


def test_can_accept_registrations_returns_false_for_draft(session, event_factory):
    event = event_factory(capacity=10, status=EventStatus.DRAFT)
    assert event.can_accept_registrations() is False


def test_existing_registration_preserved_after_close(session, event_factory):
    """Закрытие регистрации — не отмена: существующие записи остаются confirmed."""
    event = event_factory(capacity=10)
    upsert_user(session, max_user_id=42, chat_id=42, name="Test")
    result = sign_up(session, event_id=event.id, user_id=42)

    event.registration_open = False
    session.commit()

    from app.models import Registration, RegStatus
    refreshed = session.get(Registration, result.registration.id)
    assert refreshed.status == RegStatus.CONFIRMED
