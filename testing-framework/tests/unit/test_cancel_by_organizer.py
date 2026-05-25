"""Отмена записи организатором: статус CANCELLED_BY_ORGANIZER, late-policy
не действует (организатор отменяет всегда), waitlist промотируется.
"""
from __future__ import annotations

from app.models import LateCancelPolicy, Registration, RegStatus
from app.services.registration import (
    cancel_by_organizer,
    mark_attended_by_id,
    sign_up,
    upsert_user,
)


def _users(session, ids: list[int]) -> None:
    for uid in ids:
        upsert_user(session, max_user_id=uid, chat_id=uid, name=f"U{uid}")
    session.flush()


def test_cancel_by_organizer_changes_status(session, event_factory):
    event = event_factory(capacity=5)
    _users(session, [1])
    result = sign_up(session, event_id=event.id, user_id=1)
    reg_id = result.registration.id

    out = cancel_by_organizer(session, registration_id=reg_id)

    assert out.cancelled is True
    reg = session.get(Registration, reg_id)
    assert reg.status == RegStatus.CANCELLED_BY_ORGANIZER
    assert reg.cancelled_at is not None


def test_cancel_by_organizer_promotes_waitlist(session, event_factory):
    event = event_factory(capacity=1)
    _users(session, [1, 2])
    r1 = sign_up(session, event_id=event.id, user_id=1)
    r2 = sign_up(session, event_id=event.id, user_id=2)
    assert r2.is_waitlist is True

    out = cancel_by_organizer(session, registration_id=r1.registration.id)

    assert out.promoted_registration is not None
    assert out.promoted_registration.user_id == 2
    promoted = session.get(Registration, r2.registration.id)
    assert promoted.status == RegStatus.CONFIRMED


def test_cancel_by_organizer_works_even_after_event_start(session, event_factory):
    """Организаторская отмена не подчиняется late_cancel_policy."""
    from datetime import datetime, timedelta
    event = event_factory(capacity=5)
    event.late_cancel_policy = LateCancelPolicy.DISALLOW
    _users(session, [1])
    result = sign_up(session, event_id=event.id, user_id=1)
    event.starts_at = datetime.utcnow() - timedelta(hours=1)  # уже идёт
    session.commit()

    out = cancel_by_organizer(session, registration_id=result.registration.id)

    assert out.cancelled is True
    reg = session.get(Registration, result.registration.id)
    assert reg.status == RegStatus.CANCELLED_BY_ORGANIZER


def test_cancel_by_organizer_unknown_id_returns_false(session):
    out = cancel_by_organizer(session, registration_id=99999)
    assert out.cancelled is False


def test_cancel_by_organizer_already_cancelled_is_noop(session, event_factory):
    event = event_factory(capacity=5)
    _users(session, [1])
    result = sign_up(session, event_id=event.id, user_id=1)
    reg = session.get(Registration, result.registration.id)
    reg.status = RegStatus.CANCELLED  # уже отменена пользователем
    session.commit()

    out = cancel_by_organizer(session, registration_id=reg.id)

    assert out.cancelled is False
    assert reg.status == RegStatus.CANCELLED


# ---------------------------------------------------------------------------
# mark_attended_by_id — ручная отметка «пришёл» из админки
# ---------------------------------------------------------------------------

def test_mark_attended_by_id_works(session, event_factory):
    event = event_factory(capacity=5)
    _users(session, [1])
    result = sign_up(session, event_id=event.id, user_id=1)

    reg = mark_attended_by_id(session, registration_id=result.registration.id)

    assert reg is not None
    assert reg.status == RegStatus.ATTENDED
    assert reg.attended_at is not None


def test_mark_attended_by_id_rejects_non_confirmed(session, event_factory):
    """Нельзя отметить «пришёл» у waitlist'а или у отменённой записи."""
    event = event_factory(capacity=1)
    _users(session, [1, 2])
    sign_up(session, event_id=event.id, user_id=1)
    r2 = sign_up(session, event_id=event.id, user_id=2)  # waitlist

    out = mark_attended_by_id(session, registration_id=r2.registration.id)
    assert out is None
