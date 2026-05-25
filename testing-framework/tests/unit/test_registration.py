"""Юнит-тесты бизнес-логики записи: sign_up, cancel, mark_attended, waitlist."""
from __future__ import annotations

import pytest

from app.models import RegStatus, User
from app.services.registration import (
    cancel_registration,
    mark_attended,
    sign_up,
    upsert_user,
)

# ---------------------------------------------------------------------------
# Хелпер: создать пользователя через upsert_user, чтобы он точно был в БД
# ---------------------------------------------------------------------------

def _make_user(session, max_user_id: int, name: str = "User") -> User:
    return upsert_user(session, max_user_id=max_user_id, chat_id=max_user_id, name=name)


# ---------------------------------------------------------------------------
# sign_up — успешные сценарии
# ---------------------------------------------------------------------------

def test_signup_confirms_when_seats_available(session, event_factory):
    event = event_factory(capacity=2)
    _make_user(session, 100)

    result = sign_up(session, event_id=event.id, user_id=100)

    assert result.is_waitlist is False
    assert result.already_registered is False
    assert result.registration.status == RegStatus.CONFIRMED
    assert result.registration.waitlist_position is None


def test_signup_puts_into_waitlist_when_full(session, event_factory):
    event = event_factory(capacity=1)
    _make_user(session, 100)
    _make_user(session, 200)

    sign_up(session, event_id=event.id, user_id=100)
    result = sign_up(session, event_id=event.id, user_id=200)

    assert result.is_waitlist is True
    assert result.waitlist_position == 1
    assert result.registration.status == RegStatus.WAITLIST


def test_waitlist_positions_are_sequential(session, event_factory):
    event = event_factory(capacity=1)
    for uid in (100, 200, 300, 400):
        _make_user(session, uid)

    sign_up(session, event_id=event.id, user_id=100)  # confirmed
    r2 = sign_up(session, event_id=event.id, user_id=200)
    r3 = sign_up(session, event_id=event.id, user_id=300)
    r4 = sign_up(session, event_id=event.id, user_id=400)

    assert r2.waitlist_position == 1
    assert r3.waitlist_position == 2
    assert r4.waitlist_position == 3


def test_repeat_signup_returns_already_registered(session, event_factory):
    event = event_factory(capacity=5)
    _make_user(session, 100)

    sign_up(session, event_id=event.id, user_id=100)
    result = sign_up(session, event_id=event.id, user_id=100)

    assert result.already_registered is True
    # Ровно одна запись в БД — никакого дубля.
    from app.models import Registration
    count = session.query(Registration).filter_by(event_id=event.id, user_id=100).count()
    assert count == 1


def test_signup_after_cancel_reuses_row_with_new_token(session, event_factory):
    event = event_factory(capacity=5)
    _make_user(session, 100)

    first = sign_up(session, event_id=event.id, user_id=100)
    old_id = first.registration.id
    old_token = first.registration.qr_token

    cancel_registration(session, registration_id=old_id, user_id=100)
    second = sign_up(session, event_id=event.id, user_id=100)

    assert second.registration.id == old_id, "должна переиспользоваться та же строка"
    assert second.registration.qr_token != old_token, "qr_token должен быть пересоздан"
    assert second.registration.status == RegStatus.CONFIRMED


def test_signup_raises_when_event_not_published(session, event_factory):
    event = event_factory(capacity=5, status="draft")
    _make_user(session, 100)

    with pytest.raises(ValueError):
        sign_up(session, event_id=event.id, user_id=100)


# ---------------------------------------------------------------------------
# cancel_registration — освобождение места и promotion
# ---------------------------------------------------------------------------

def test_cancel_confirmed_promotes_first_from_waitlist(session, event_factory):
    event = event_factory(capacity=1)
    _make_user(session, 100)
    _make_user(session, 200)

    confirmed = sign_up(session, event_id=event.id, user_id=100).registration
    waitlist_first = sign_up(session, event_id=event.id, user_id=200).registration
    assert waitlist_first.status == RegStatus.WAITLIST

    result = cancel_registration(session, registration_id=confirmed.id, user_id=100)

    assert result.cancelled is True
    assert result.promoted_registration is not None
    assert result.promoted_registration.user_id == 200
    assert result.promoted_registration.status == RegStatus.CONFIRMED
    assert result.promoted_registration.waitlist_position is None


def test_cancel_from_waitlist_shifts_other_positions(session, event_factory):
    event = event_factory(capacity=1)
    for uid in (100, 200, 300, 400):
        _make_user(session, uid)

    sign_up(session, event_id=event.id, user_id=100)
    r2 = sign_up(session, event_id=event.id, user_id=200).registration  # pos 1
    r3 = sign_up(session, event_id=event.id, user_id=300).registration  # pos 2
    r4 = sign_up(session, event_id=event.id, user_id=400).registration  # pos 3

    # Отменяет тот, кто на 2-й позиции (300):
    cancel_registration(session, registration_id=r3.id, user_id=300)

    session.refresh(r2)
    session.refresh(r4)

    assert r2.waitlist_position == 1  # не сдвинулся
    assert r4.waitlist_position == 2  # подтянулся на одно место


def test_cancel_rejected_for_wrong_user(session, event_factory):
    event = event_factory(capacity=5)
    _make_user(session, 100)
    _make_user(session, 200)

    reg = sign_up(session, event_id=event.id, user_id=100).registration

    # Чужой пользователь не может отменить запись.
    result = cancel_registration(session, registration_id=reg.id, user_id=200)
    assert result.cancelled is False


def test_double_cancel_is_noop(session, event_factory):
    event = event_factory(capacity=5)
    _make_user(session, 100)
    reg = sign_up(session, event_id=event.id, user_id=100).registration

    first = cancel_registration(session, registration_id=reg.id, user_id=100)
    second = cancel_registration(session, registration_id=reg.id, user_id=100)

    assert first.cancelled is True
    assert second.cancelled is False  # повторная отмена молча игнорируется


# ---------------------------------------------------------------------------
# mark_attended — отметка по QR
# ---------------------------------------------------------------------------

def test_mark_attended_happy_path(session, event_factory):
    event = event_factory(capacity=5)
    _make_user(session, 100)
    reg = sign_up(session, event_id=event.id, user_id=100).registration

    marked = mark_attended(session, reg.qr_token)

    assert marked is not None
    assert marked.status == RegStatus.ATTENDED
    assert marked.attended_at is not None


def test_mark_attended_rejects_unknown_token(session, event_factory):
    event_factory()  # нужно, чтобы метаданные были, но не используем
    assert mark_attended(session, "nonexistent-token") is None


def test_mark_attended_rejects_already_attended(session, event_factory):
    event = event_factory(capacity=5)
    _make_user(session, 100)
    reg = sign_up(session, event_id=event.id, user_id=100).registration

    first = mark_attended(session, reg.qr_token)
    second = mark_attended(session, reg.qr_token)

    assert first is not None
    assert second is None, "повторное сканирование того же QR должно вернуть None"


def test_mark_attended_rejects_waitlist_token(session, event_factory):
    event = event_factory(capacity=1)
    _make_user(session, 100)
    _make_user(session, 200)

    sign_up(session, event_id=event.id, user_id=100)
    waitlist = sign_up(session, event_id=event.id, user_id=200).registration

    # Пользователь в waitlist не должен мочь пройти по QR — у него ещё нет места.
    assert mark_attended(session, waitlist.qr_token) is None
