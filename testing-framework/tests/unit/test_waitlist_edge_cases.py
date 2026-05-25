"""Edge-cases waitlist и capacity."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import LateCancelPolicy, RegStatus, Registration
from app.services.registration import (
    cancel_registration,
    promote_from_waitlist,
    sign_up,
    upsert_user,
)


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.pos
def test_cancel_confirmed_promotes_first_waitlist_member(session, event_factory):
    """TC-UNIT-WL-EDGE-001: отмена confirmed → promotion первого в waitlist."""
    event = event_factory(capacity=1)
    upsert_user(session, max_user_id=701, chat_id=701, name="A")
    upsert_user(session, max_user_id=702, chat_id=702, name="B")
    confirmed = sign_up(session, event_id=event.id, user_id=701).registration
    waitlisted = sign_up(session, event_id=event.id, user_id=702).registration

    result = cancel_registration(session, registration_id=confirmed.id, user_id=701)

    session.refresh(waitlisted)
    assert result.promoted_registration is not None
    assert result.promoted_registration.user_id == 702
    assert waitlisted.status == RegStatus.CONFIRMED
    assert waitlisted.waitlist_position is None


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.neg
def test_late_cancel_does_not_promote_waitlist(session, event_factory):
    """TC-UNIT-WL-EDGE-002: LATE_CANCELLED → waitlist не двигается."""
    event = event_factory(capacity=1)
    event.late_cancel_policy = LateCancelPolicy.ALLOW_MARKED
    upsert_user(session, max_user_id=711, chat_id=711, name="A")
    upsert_user(session, max_user_id=712, chat_id=712, name="B")
    r1 = sign_up(session, event_id=event.id, user_id=711)
    r2 = sign_up(session, event_id=event.id, user_id=712)
    event.starts_at = datetime.utcnow() - timedelta(minutes=5)
    session.commit()

    result = cancel_registration(session, registration_id=r1.registration.id, user_id=711)

    session.refresh(r2.registration)
    assert result.late is True
    assert result.promoted_registration is None
    assert r2.registration.status == RegStatus.WAITLIST


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.pos
def test_promote_from_empty_waitlist_returns_none(session, event_factory):
    """TC-UNIT-WL-EDGE-003: пустой waitlist → None, без исключения."""
    event = event_factory(capacity=5)

    promoted = promote_from_waitlist(session, event_id=event.id)

    assert promoted is None


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.neg
def test_capacity_zero_puts_signup_into_waitlist(session, event_factory):
    """TC-UNIT-WL-EDGE-004: capacity=0 → сразу waitlist."""
    event = event_factory(capacity=0)
    upsert_user(session, max_user_id=721, chat_id=721, name="ZeroCap")

    result = sign_up(session, event_id=event.id, user_id=721)

    assert result.is_waitlist is True
    assert result.registration.status == RegStatus.WAITLIST
    assert result.waitlist_position == 1


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.neg
def test_oversubscribed_signups_respect_capacity(session, event_factory):
    """TC-UNIT-WL-EDGE-005: 4 sign_up при capacity=2 → ровно 2 confirmed + 2 waitlist."""
    event = event_factory(capacity=2)
    user_ids = [731, 732, 733, 734]
    for uid in user_ids:
        upsert_user(session, max_user_id=uid, chat_id=uid, name=f"U{uid}")

    for uid in user_ids:
        sign_up(session, event_id=event.id, user_id=uid)

    confirmed = session.query(Registration).filter(
        Registration.event_id == event.id,
        Registration.status == RegStatus.CONFIRMED,
    ).count()
    waitlist = session.query(Registration).filter(
        Registration.event_id == event.id,
        Registration.status == RegStatus.WAITLIST,
    ).count()

    assert confirmed == 2
    assert waitlist == 2
