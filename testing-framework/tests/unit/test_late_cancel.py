"""Тесты политики поздней отмены: DISALLOW / ALLOW_MARKED.

Ключевое: ALLOW_MARKED помечает запись LATE_CANCELLED, но место в пул НЕ
возвращает — иначе waitlist бы массово ехал на уже идущее мероприятие.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models import LateCancelPolicy, RegStatus
from app.services.registration import (
    cancel_registration,
    sign_up,
    upsert_user,
)


def _setup_event_with_one_registration(
    session, event_factory, late_policy: str, starts_at_offset_hours: float
):
    """starts_at_offset_hours: -1 = час назад (идёт), +1 = через час."""
    event = event_factory(capacity=5)
    event.late_cancel_policy = late_policy
    event.starts_at = datetime.utcnow() + timedelta(hours=starts_at_offset_hours)
    session.commit()

    upsert_user(session, max_user_id=42, chat_id=42, name="Test")
    if starts_at_offset_hours > 0:
        result = sign_up(session, event_id=event.id, user_id=42)
        reg_id = result.registration.id
    else:
        # sign_up не пустит на уже идущее → временно ставим в будущее, потом откатываем.
        event.starts_at = datetime.utcnow() + timedelta(hours=1)
        session.commit()
        result = sign_up(session, event_id=event.id, user_id=42)
        reg_id = result.registration.id
        event.starts_at = datetime.utcnow() + timedelta(hours=starts_at_offset_hours)
        session.commit()
    return event, reg_id


# ---------------------------------------------------------------------------
# Late cancel — DISALLOW
# ---------------------------------------------------------------------------

def test_disallow_policy_forbids_late_cancel(session, event_factory):
    _, reg_id = _setup_event_with_one_registration(
        session, event_factory,
        late_policy=LateCancelPolicy.DISALLOW,
        starts_at_offset_hours=-1,
    )

    result = cancel_registration(session, registration_id=reg_id, user_id=42)

    assert result.cancelled is False
    assert result.forbidden_late is True


# ---------------------------------------------------------------------------
# Late cancel — ALLOW_MARKED
# ---------------------------------------------------------------------------

def test_allow_marked_policy_marks_as_late_cancelled(session, event_factory):
    _, reg_id = _setup_event_with_one_registration(
        session, event_factory,
        late_policy=LateCancelPolicy.ALLOW_MARKED,
        starts_at_offset_hours=-1,
    )

    result = cancel_registration(session, registration_id=reg_id, user_id=42)

    assert result.cancelled is True
    assert result.late is True
    from app.models import Registration
    refreshed = session.get(Registration, reg_id)
    assert refreshed.status == RegStatus.LATE_CANCELLED


def test_allow_marked_does_not_promote_waitlist(session, event_factory):
    event = event_factory(capacity=1)
    event.late_cancel_policy = LateCancelPolicy.ALLOW_MARKED
    upsert_user(session, max_user_id=42, chat_id=42, name="A")
    upsert_user(session, max_user_id=43, chat_id=43, name="B")
    session.commit()

    r1 = sign_up(session, event_id=event.id, user_id=42)
    r2 = sign_up(session, event_id=event.id, user_id=43)  # waitlist
    session.commit()
    event.starts_at = datetime.utcnow() - timedelta(minutes=10)  # уже идёт
    session.commit()

    result = cancel_registration(session, registration_id=r1.registration.id, user_id=42)

    # r2 НЕ промотируется: место освобождать поздно, человек уже не успеет приехать.
    assert result.late is True
    assert result.promoted_registration is None
    from app.models import Registration
    r2_refreshed = session.get(Registration, r2.registration.id)
    assert r2_refreshed.status == RegStatus.WAITLIST


# ---------------------------------------------------------------------------
# Раньше старта — политика не работает
# ---------------------------------------------------------------------------

def test_cancel_before_start_ignores_late_policy(session, event_factory):
    _, reg_id = _setup_event_with_one_registration(
        session, event_factory,
        late_policy=LateCancelPolicy.DISALLOW,
        starts_at_offset_hours=1,
    )

    result = cancel_registration(session, registration_id=reg_id, user_id=42)

    assert result.cancelled is True
    assert result.late is False
    assert result.forbidden_late is False
