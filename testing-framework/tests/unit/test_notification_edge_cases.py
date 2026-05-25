"""Edge-cases уведомлений: broadcast, reminders, mute-флаги."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app import scheduler as sched_mod
from app.models import Event, Reminder, User
from app.services.broadcast import (
    BroadcastSegment,
    create_broadcast,
    get_recipients,
    send_broadcast,
)
from app.services.registration import sign_up, upsert_user


class _SendTextSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    async def __call__(self, chat_id: int, text: str, attachments=None) -> bool:
        self.calls.append((chat_id, text))
        return True


@pytest.fixture
def send_text_spy(monkeypatch):
    spy = _SendTextSpy()
    monkeypatch.setattr("app.services.broadcast.send_text", spy)
    monkeypatch.setattr("app.scheduler.send_text", spy)
    return spy


def _make_users(session, count: int, *, notifications_enabled: bool = True) -> list[User]:
    users = []
    for i in range(count):
        uid = 100 + i + 1
        user = upsert_user(session, max_user_id=uid, chat_id=uid, name=f"User {uid}")
        user.notifications_enabled = notifications_enabled
        users.append(user)
    session.flush()
    return users


def _patch_scheduler_session(session, monkeypatch):
    factory = sessionmaker(
        bind=session.get_bind(), autoflush=False, expire_on_commit=False, future=True,
    )
    monkeypatch.setattr("app.db.SessionLocal", factory)

    @contextmanager
    def _scope():
        s = factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr("app.scheduler.session_scope", _scope)


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.neg
def test_broadcast_empty_event_delivers_zero(session, event_factory, send_text_spy):
    """TC-UNIT-NOTIF-EDGE-001: нет участников → 0 отправок, без ошибок."""
    event = event_factory(capacity=5)
    bc = create_broadcast(
        session,
        event_id=event.id,
        organizer_id=1,
        segment=BroadcastSegment.CONFIRMED,
        message_text="Тест пустой рассылки",
    )
    session.commit()

    asyncio.run(send_broadcast(session, bc.id))

    session.refresh(bc)
    assert bc.delivered_count == 0
    assert bc.failed_count == 0
    assert send_text_spy.calls == []


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.neg
def test_broadcast_all_registrations_muted_delivers_zero(
    session, event_factory, send_text_spy,
):
    """TC-UNIT-NOTIF-EDGE-002: все notifications_enabled=False на записи → 0."""
    event = event_factory(capacity=5)
    upsert_user(session, max_user_id=501, chat_id=501, name="Muted")
    reg = sign_up(session, event_id=event.id, user_id=501).registration
    reg.notifications_enabled = False
    session.flush()

    bc = create_broadcast(
        session,
        event_id=event.id,
        organizer_id=1,
        segment=BroadcastSegment.CONFIRMED,
        message_text="Не должно дойти",
    )
    session.commit()

    asyncio.run(send_broadcast(session, bc.id))

    session.refresh(bc)
    assert bc.delivered_count == 0
    assert send_text_spy.calls == []


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.neg
def test_reminder_for_deleted_event_is_marked_sent_without_error(
    session, event_factory, send_text_spy, monkeypatch,
):
    """TC-UNIT-NOTIF-EDGE-003: event удалён, reg осталась → sent=True, без send."""
    from sqlalchemy import text

    event = event_factory(capacity=5)
    _make_users(session, count=1)
    reg = sign_up(session, event_id=event.id, user_id=101).registration
    reminder = Reminder(
        registration_id=reg.id,
        remind_at=datetime.utcnow() - timedelta(minutes=1),
        kind="day_before",
        sent=False,
    )
    session.add(reminder)
    session.flush()
    reminder_id = reminder.id

    session.execute(text("PRAGMA foreign_keys=OFF"))
    session.delete(session.get(Event, event.id))
    session.commit()
    session.execute(text("PRAGMA foreign_keys=ON"))

    _patch_scheduler_session(session, monkeypatch)
    asyncio.run(sched_mod.process_due_reminders())

    assert send_text_spy.calls == []
    session.expire_all()
    refreshed = session.get(Reminder, reminder_id)
    assert refreshed is not None
    assert refreshed.sent is True


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.neg
def test_global_mute_overrides_registration_notifications_enabled(
    session, event_factory,
):
    """TC-UNIT-NOTIF-EDGE-004: User.notifications_enabled=False блокирует рассылку."""
    event = event_factory(capacity=5)
    user = upsert_user(session, max_user_id=601, chat_id=601, name="GlobalOff")
    user.notifications_enabled = False
    reg = sign_up(session, event_id=event.id, user_id=601).registration
    reg.notifications_enabled = True
    session.flush()

    recipients = get_recipients(session, event.id, BroadcastSegment.CONFIRMED)

    assert recipients == []


@pytest.mark.edge
@pytest.mark.unit
@pytest.mark.neg
def test_scheduler_skips_when_global_mute_despite_reg_enabled(
    session, event_factory, send_text_spy, monkeypatch,
):
    """TC-UNIT-NOTIF-EDGE-005: глобальный mute → reminder не уходит."""
    event = event_factory(capacity=5)
    user = upsert_user(session, max_user_id=602, chat_id=602, name="GlobalOff")
    user.notifications_enabled = False
    reg = sign_up(session, event_id=event.id, user_id=602).registration
    reg.notifications_enabled = True
    session.add(Reminder(
        registration_id=reg.id,
        remind_at=datetime.utcnow() - timedelta(minutes=1),
        kind="hour_before",
        sent=False,
    ))
    session.commit()

    _patch_scheduler_session(session, monkeypatch)
    asyncio.run(sched_mod.process_due_reminders())

    assert send_text_spy.calls == []
