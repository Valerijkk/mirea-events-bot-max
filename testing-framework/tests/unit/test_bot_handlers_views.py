"""Тесты отрисовки карточек/списков в боте: event card, events list,
my registrations, slot picker.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.bot import handlers as h
from app.bot.texts import CONSENT_VERSION
from app.db import Base
from app.models import (
    Consent,
    Event,
    EventFormat,
    EventStatus,
    EventType,
    User,
)
from app.services.registration import sign_up
from app.services.slots import create_slot
from tests.unit.fakes.max_client import FakeMaxClient


@pytest.fixture(autouse=True)
def _swap_db(monkeypatch, tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr("app.db.SessionLocal", SessionLocal)
    monkeypatch.setattr("app.scheduler.schedule_reminders_for_registration", lambda *a, **k: None)
    monkeypatch.setattr("app.bot.handlers.schedule_reminders_for_registration", lambda *a, **k: None)
    # QR в tmp
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "qr_dir", str(tmp_path))

    yield

    h._AWAITING_NAME.clear()


def _seed_user(uid: int = 100, *, consent: bool = True) -> None:
    from app.db import SessionLocal
    with SessionLocal() as s:
        s.add(User(max_user_id=uid, chat_id=uid, name="Петров Пётр Петрович"))
        if consent:
            s.add(Consent(user_id=uid, doc_version=CONSENT_VERSION))
        s.commit()


def _seed_event(**kw) -> int:
    from app.db import SessionLocal
    with SessionLocal() as s:
        ev = Event(
            title=kw.get("title", "Тест"),
            description=kw.get("description", "desc"),
            event_type=kw.get("event_type", EventType.OPEN_DAY),
            starts_at=kw.get("starts_at", datetime.now(UTC) + timedelta(days=7)),
            location=kw.get("location", "ауд. 101"),
            capacity=kw.get("capacity", 5),
            status=kw.get("status", EventStatus.PUBLISHED),
            format=kw.get("format", EventFormat.ONSITE),
            duration_minutes=kw.get("duration_minutes", 90),
            registration_open=kw.get("registration_open", True),
            requirements=kw.get("requirements"),
            cancellation_terms=kw.get("cancellation_terms"),
            meeting_url=kw.get("meeting_url"),
        )
        s.add(ev)
        s.commit()
        return ev.id


def _run(coro):
    return asyncio.run(coro)


class TestEventsList:
    def test_empty_catalog_shows_no_events(self):
        _seed_user(100)
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": "events"}}, fake,
        ))
        assert any("нет открытых" in t.lower() or "пока" in t.lower() for t in fake.texts())

    def test_catalog_shows_published_events(self):
        _seed_user(100)
        _seed_event(title="Видимое")
        _seed_event(title="Тоже видимое")
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": "events"}}, fake,
        ))
        # В клавиатуре есть кнопки с этими названиями
        all_text = str(fake.messages)
        assert "Видимое" in all_text
        assert "Тоже видимое" in all_text


class TestEventCard:
    def test_card_includes_format_and_duration(self):
        _seed_user(100)
        eid = _seed_event(format=EventFormat.ONLINE, meeting_url="https://meet.x", duration_minutes=120)
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"event:{eid}"}}, fake,
        ))
        text = " ".join(fake.texts())
        # Онлайн-формат и длительность отрисованы
        assert "Онлайн" in text or "💻" in text
        assert "ч" in text  # «1 ч 30 мин» / «2 ч»

    def test_card_with_registration_closed_shows_status(self):
        _seed_user(100)
        eid = _seed_event(registration_open=False)
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"event:{eid}"}}, fake,
        ))
        text = " ".join(fake.texts())
        assert "закрыта" in text.lower()

    def test_details_callback_shows_requirements_and_terms(self):
        _seed_user(100)
        eid = _seed_event(
            requirements="11 класс, паспорт",
            cancellation_terms="Можно отменить за 24 часа",
        )
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"details:{eid}"}}, fake,
        ))
        text = " ".join(fake.texts())
        assert "11 класс" in text
        assert "24 часа" in text

    def test_card_for_unknown_event_shows_not_found(self):
        _seed_user(100)
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": "event:99999"}}, fake,
        ))
        text = " ".join(fake.texts())
        assert "не найден" in text.lower() or "завершил" in text.lower()


class TestSlotPicker:
    def test_signup_on_event_with_slots_shows_picker(self):
        _seed_user(100)
        eid = _seed_event()
        from app.db import SessionLocal
        with SessionLocal() as s:
            create_slot(s, event_id=eid,
                        starts_at=datetime.now(UTC) + timedelta(hours=2),
                        capacity=10, label="11:00 — экскурсия")
            create_slot(s, event_id=eid,
                        starts_at=datetime.now(UTC) + timedelta(hours=4),
                        capacity=10, label="13:00 — экскурсия")
            s.commit()

        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"signup:{eid}"}}, fake,
        ))
        text = " ".join(fake.texts())
        # Заголовок выбора слота: SLOT_PICKER_HEADER говорит «временных окон»
        assert "временн" in text.lower() or "выберите" in text.lower()
        # И сама клавиатура с обоими слотами
        all_msg = str(fake.messages)
        assert "11:00" in all_msg and "13:00" in all_msg

    def test_slot_callback_shows_summary_with_slot_info(self):
        _seed_user(100)
        eid = _seed_event()
        from app.db import SessionLocal
        with SessionLocal() as s:
            slot = create_slot(s, event_id=eid,
                               starts_at=datetime.now(UTC) + timedelta(hours=2),
                               capacity=10, label="11:00")
            s.commit()
            slot_id = slot.id

        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"slot:{eid}:{slot_id}"}}, fake,
        ))
        text = " ".join(fake.texts())
        assert "Слот: 11:00" in text or "11:00" in text


class TestMyRegistrations:
    def test_empty_my_shows_placeholder(self):
        _seed_user(100)
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": "my"}}, fake,
        ))
        text = " ".join(fake.texts())
        assert "пока нет" in text.lower() or "афиша" in text.lower()

    def test_my_shows_confirmed_with_code(self):
        _seed_user(100)
        eid = _seed_event()
        from app.db import SessionLocal
        with SessionLocal() as s:
            sign_up(s, event_id=eid, user_id=100)
            s.commit()

        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": "my"}}, fake,
        ))
        text = " ".join(fake.texts())
        # В тексте — код записи RG-XXXXXX
        assert "RG-" in text

    def test_my_marks_cancelled_event_appropriately(self):
        """Если мероприятие отменено целиком — запись юзера показывается как отменённая."""
        _seed_user(100)
        eid = _seed_event()
        from app.db import SessionLocal
        with SessionLocal() as s:
            sign_up(s, event_id=eid, user_id=100)
            ev = s.get(Event, eid)
            ev.status = EventStatus.CANCELLED
            s.commit()

        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": "my"}}, fake,
        ))
        text = " ".join(fake.texts())
        assert "отменено" in text.lower()


def test_menu_callback_shows_main_menu():
    _seed_user(100)
    fake = FakeMaxClient()
    _run(h.on_callback(
        {"user": {"user_id": 100}, "callback": {"payload": "menu"}}, fake,
    ))
    assert len(fake.messages) >= 1


def test_unknown_text_shows_unknown_message():
    _seed_user(100)
    fake = FakeMaxClient()
    _run(h.on_message(
        {"user": {"user_id": 100}, "message": {"body": {"text": "случайный мусор"}}},
        fake,
    ))
    text = " ".join(fake.texts())
    assert "не понял" in text.lower() or "помог" in text.lower() or "афиша" in text.lower()
