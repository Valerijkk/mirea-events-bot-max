"""Тесты broadcast-уведомлений и планировщика напоминаний.

`send_text` мокаем через monkeypatch — никаких сетевых вызовов в MAX.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from app.models import (
    EventStatus,
    Reminder,
    User,
)
from app.services.broadcast import (
    BroadcastSegment,
    get_recipients,
    notify_event_cancelled,
)
from app.services.registration import sign_up, upsert_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _SendTextSpy:
    """Подмена `send_text`: возвращает True, копит (chat_id, text) в `calls`."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    async def __call__(self, chat_id: int, text: str, attachments=None) -> bool:
        self.calls.append((chat_id, text))
        return True


@pytest.fixture
def send_text_spy(monkeypatch):
    """Подменяет send_text сразу в `broadcast` и `scheduler` — никакой сети."""
    spy = _SendTextSpy()
    monkeypatch.setattr("app.services.broadcast.send_text", spy)
    monkeypatch.setattr("app.scheduler.send_text", spy)
    return spy


def _make_users(session, count: int, *, notifications_enabled: bool = True) -> list[User]:
    """Создать `count` пользователей с предсказуемыми id (101, 102, ...)."""
    users = []
    for i in range(count):
        uid = 100 + i + 1
        user = upsert_user(session, max_user_id=uid, chat_id=uid, name=f"User {uid}")
        user.notifications_enabled = notifications_enabled
        users.append(user)
    session.flush()
    return users


# ---------------------------------------------------------------------------
# notify_event_cancelled
# ---------------------------------------------------------------------------

def test_notify_event_cancelled_returns_zero_for_missing_event(session, send_text_spy):
    delivered, failed = asyncio.run(notify_event_cancelled(session, event_id=999))

    assert (delivered, failed) == (0, 0)
    assert send_text_spy.calls == [], "не должно быть исходящих сообщений"


def test_notify_event_cancelled_sends_to_confirmed_and_waitlist(
    session, event_factory, send_text_spy
):
    # capacity=1 → один confirmed, два в waitlist; все трое должны получить
    event = event_factory(capacity=1)
    _make_users(session, count=3)
    sign_up(session, event_id=event.id, user_id=101)
    sign_up(session, event_id=event.id, user_id=102)
    sign_up(session, event_id=event.id, user_id=103)
    session.flush()

    delivered, failed = asyncio.run(notify_event_cancelled(session, event_id=event.id))

    assert delivered == 3
    assert failed == 0
    chat_ids = {chat_id for chat_id, _ in send_text_spy.calls}
    assert chat_ids == {101, 102, 103}
    sample_text = send_text_spy.calls[0][1]
    assert event.title in sample_text


def test_notify_event_cancelled_respects_notifications_disabled(
    session, event_factory, send_text_spy
):
    event = event_factory(capacity=5)
    _make_users(session, count=1)  # 101 — notifications=True
    user_silent = upsert_user(session, max_user_id=102, chat_id=102, name="Silent")
    user_silent.notifications_enabled = False
    session.flush()

    sign_up(session, event_id=event.id, user_id=101)
    sign_up(session, event_id=event.id, user_id=102)
    session.flush()

    delivered, failed = asyncio.run(notify_event_cancelled(session, event_id=event.id))

    assert delivered == 1, "только пользователь с notifications_enabled должен получить"
    assert failed == 0
    assert send_text_spy.calls == [(101, send_text_spy.calls[0][1])]


# ---------------------------------------------------------------------------
# get_recipients — уважение notifications_enabled
# ---------------------------------------------------------------------------

def test_get_recipients_excludes_users_with_notifications_disabled(
    session, event_factory
):
    event = event_factory(capacity=5)
    upsert_user(session, max_user_id=201, chat_id=201, name="A")
    u2 = upsert_user(session, max_user_id=202, chat_id=202, name="B")
    u2.notifications_enabled = False
    session.flush()
    sign_up(session, event_id=event.id, user_id=201)
    sign_up(session, event_id=event.id, user_id=202)

    recipients = get_recipients(session, event.id, BroadcastSegment.CONFIRMED)

    assert [r.max_user_id for r in recipients] == [201]


# ---------------------------------------------------------------------------
# scheduler.process_due_reminders — пропуск отменённых мероприятий
# ---------------------------------------------------------------------------

def test_process_due_reminders_skips_cancelled_event(
    session, event_factory, send_text_spy, monkeypatch
):
    """Если мероприятие отменено, напоминание молча гасится — иначе юзер
    приедет к закрытым дверям. Reminder при этом помечается sent=True,
    чтобы scheduler не пытался его обработать заново.
    """
    from app import scheduler as sched_mod

    event = event_factory(capacity=5)
    _make_users(session, count=1)
    reg = sign_up(session, event_id=event.id, user_id=101).registration
    reminder = Reminder(
        registration_id=reg.id,
        remind_at=datetime.utcnow() - timedelta(minutes=1),  # созрело
        kind="day_before",
        sent=False,
    )
    session.add(reminder)
    event.status = EventStatus.CANCELLED
    session.commit()

    # process_due_reminders берёт сессию через `session_scope()`. Подменяем
    # SessionLocal на фабрику к тому же engine, что и фикстура — иначе
    # будут две in-memory БД и тест ничего не увидит.
    test_engine = session.get_bind()
    from sqlalchemy.orm import sessionmaker
    TestSessionFactory = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False, future=True
    )
    monkeypatch.setattr("app.db.SessionLocal", TestSessionFactory)
    monkeypatch.setattr("app.scheduler.session_scope", _patched_session_scope(TestSessionFactory))

    asyncio.run(sched_mod.process_due_reminders())

    assert send_text_spy.calls == [], "по отменённому мероприятию нельзя слать напоминание"
    session.expire_all()
    refreshed = session.get(Reminder, reminder.id)
    assert refreshed.sent is True
    assert refreshed.sent_at is not None


def test_process_due_reminders_skips_user_with_notifications_disabled(
    session, event_factory, send_text_spy, monkeypatch
):
    from app import scheduler as sched_mod

    event = event_factory(capacity=5)
    user = upsert_user(session, max_user_id=301, chat_id=301, name="Mute")
    user.notifications_enabled = False
    reg = sign_up(session, event_id=event.id, user_id=301).registration
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


# ---------------------------------------------------------------------------
# scheduler.process_due_reminders — HAPPY PATH (отправка)
# ---------------------------------------------------------------------------

def test_process_due_reminders_sends_day_before_to_confirmed_user(
    session, event_factory, send_text_spy, monkeypatch
):
    from app import scheduler as sched_mod

    event = event_factory(capacity=5)
    _make_users(session, count=1)
    reg = sign_up(session, event_id=event.id, user_id=101).registration
    session.add(Reminder(
        registration_id=reg.id,
        remind_at=datetime.utcnow() - timedelta(minutes=2),
        kind="day_before",
        sent=False,
    ))
    session.commit()

    _patch_scheduler_session(session, monkeypatch)

    asyncio.run(sched_mod.process_due_reminders())

    assert len(send_text_spy.calls) == 1
    chat_id, text = send_text_spy.calls[0]
    assert chat_id == 101
    assert event.title in text


def test_process_due_reminders_sends_hour_before_with_correct_template(
    session, event_factory, send_text_spy, monkeypatch
):
    """hour_before берёт `REMINDER_HOUR_BEFORE` — отличается от day_before."""
    from app import scheduler as sched_mod
    from app.bot.texts import REMINDER_HOUR_BEFORE

    event = event_factory(capacity=5)
    _make_users(session, count=1)
    reg = sign_up(session, event_id=event.id, user_id=101).registration
    session.add(Reminder(
        registration_id=reg.id,
        remind_at=datetime.utcnow() - timedelta(minutes=1),
        kind="hour_before",
        sent=False,
    ))
    session.commit()

    _patch_scheduler_session(session, monkeypatch)

    asyncio.run(sched_mod.process_due_reminders())

    expected = REMINDER_HOUR_BEFORE.format(title=event.title, location=event.location or "—")
    assert send_text_spy.calls == [(101, expected)]


def test_process_due_reminders_does_not_touch_future_reminders(
    session, event_factory, send_text_spy, monkeypatch
):
    from app import scheduler as sched_mod

    event = event_factory(capacity=5)
    _make_users(session, count=1)
    reg = sign_up(session, event_id=event.id, user_id=101).registration
    future_reminder = Reminder(
        registration_id=reg.id,
        remind_at=datetime.utcnow() + timedelta(hours=2),  # ещё не созрело
        kind="hour_before",
        sent=False,
    )
    session.add(future_reminder)
    session.commit()

    _patch_scheduler_session(session, monkeypatch)

    asyncio.run(sched_mod.process_due_reminders())

    assert send_text_spy.calls == []
    session.expire_all()
    refreshed = session.get(Reminder, future_reminder.id)
    assert refreshed.sent is False, "будущее напоминание не должно гаситься"


@pytest.mark.neg
def test_stale_reminder_is_skipped_without_sending(
    session, event_factory, send_text_spy, monkeypatch
):
    """TC-UNIT-REM-003: просроченное напоминание (>5 мин) после рестарта помечается sent=True, сообщение не отправляется."""
    from app import scheduler as sched_mod

    event = event_factory(capacity=5)
    _make_users(session, count=1)
    reg = sign_up(session, event_id=event.id, user_id=101).registration
    reminder = Reminder(
        registration_id=reg.id,
        remind_at=datetime.utcnow() - timedelta(minutes=10),
        kind="day_before",
        sent=False,
    )
    session.add(reminder)
    session.commit()

    _patch_scheduler_session(session, monkeypatch)

    asyncio.run(sched_mod.process_due_reminders())

    assert send_text_spy.calls == []
    session.expire_all()
    refreshed = session.get(Reminder, reminder.id)
    assert refreshed.sent is True
    assert refreshed.sent_at is not None


def test_process_due_reminders_marks_sent_even_when_delivery_fails(
    session, event_factory, monkeypatch
):
    """Если send_text вернул False — ретраить не надо (потенциальный спам)."""
    from app import scheduler as sched_mod

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
    session.commit()

    # send_text=False имитирует «бот заблокирован пользователем»
    async def failing_send(chat_id, text, attachments=None):
        return False

    monkeypatch.setattr("app.scheduler.send_text", failing_send)
    _patch_scheduler_session(session, monkeypatch)

    asyncio.run(sched_mod.process_due_reminders())

    session.expire_all()
    refreshed = session.get(Reminder, reminder.id)
    assert refreshed.sent is True
    assert refreshed.sent_at is not None


# ---------------------------------------------------------------------------
# Хелперы (внизу — чтобы фикстуры читались сверху вниз)
# ---------------------------------------------------------------------------

def _patched_session_scope(session_factory):
    """Контекст-менеджер, заменяющий `session_scope` в scheduler.py."""
    from contextlib import contextmanager

    @contextmanager
    def _scope():
        s = session_factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    return _scope


def _patch_scheduler_session(session, monkeypatch):
    """DRY: подмена SessionLocal и session_scope для тестов scheduler'а."""
    from sqlalchemy.orm import sessionmaker
    factory = sessionmaker(
        bind=session.get_bind(), autoflush=False, expire_on_commit=False, future=True
    )
    monkeypatch.setattr("app.db.SessionLocal", factory)
    monkeypatch.setattr("app.scheduler.session_scope", _patched_session_scope(factory))
