"""Тесты `app/bot/handlers.py` через FakeMaxClient: consent flow, команды,
callback'ы, cancel flow, late-cancel-policy.
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
    LateCancelPolicy,
    Registration,
    RegStatus,
    User,
)
from tests.unit.fakes.max_client import FakeMaxClient


@pytest.fixture(autouse=True)
def _swap_db_to_inmemory(monkeypatch, tmp_path):
    """Свежая in-memory БД на тест. StaticPool — иначе session_scope получит
    новое соединение → новую in-memory БД и потеряет seed.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False, future=True
    )
    monkeypatch.setattr("app.db.SessionLocal", TestSessionLocal)

    monkeypatch.setattr(
        "app.scheduler.schedule_reminders_for_registration",
        lambda reg_id, when: None,
    )
    monkeypatch.setattr(
        "app.bot.handlers.schedule_reminders_for_registration",
        lambda reg_id, when: None,
    )

    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "qr_dir", str(tmp_path))


def _seed_user(user_id: int = 100, *, with_consent: bool = True) -> None:
    from app.db import SessionLocal
    with SessionLocal() as s:
        s.add(User(max_user_id=user_id, chat_id=user_id, name=f"U{user_id}"))
        if with_consent:
            s.add(Consent(user_id=user_id, doc_version=CONSENT_VERSION))
        s.commit()


def _seed_event(**overrides) -> int:
    from app.db import SessionLocal
    with SessionLocal() as s:
        ev = Event(
            title=overrides.get("title", "Тестовое мероприятие"),
            description=overrides.get("description", "desc"),
            event_type=EventType.OPEN_DAY,
            starts_at=overrides.get("starts_at", datetime.now(UTC) + timedelta(days=7)),
            location="ауд. 101",
            capacity=overrides.get("capacity", 5),
            status=overrides.get("status", EventStatus.PUBLISHED),
            late_cancel_policy=overrides.get(
                "late_cancel_policy", LateCancelPolicy.DISALLOW
            ),
            format=EventFormat.ONSITE,
        )
        s.add(ev)
        s.commit()
        return ev.id


def _run(coro):
    return asyncio.run(coro)


class TestConsentFlow:
    def test_bot_started_shows_consent_for_new_user(self):
        fake = FakeMaxClient()
        update = {"user": {"user_id": 100, "name": "Новичок"}, "chat_id": 100}

        _run(h.on_bot_started(update, fake))

        assert len(fake.messages) == 1
        msg = fake.messages[0]
        assert "согласие" in msg["text"].lower() or "согласен" in msg["text"].lower()
        assert msg["attachments"], "ожидается inline-клавиатура с кнопкой согласия"

    def test_bot_started_skips_consent_if_already_granted(self):
        _seed_user(100, with_consent=True)
        fake = FakeMaxClient()
        update = {"user": {"user_id": 100, "name": "Старичок"}, "chat_id": 100}

        _run(h.on_bot_started(update, fake))

        texts = " ".join(fake.texts_sent()).lower()
        assert "согласен" not in texts

    def test_consent_callback_grants_and_opens_events(self):
        _seed_user(100, with_consent=False)
        _seed_event(title="Афиша после согласия")
        fake = FakeMaxClient()

        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": "consent"}},
            fake,
        ))

        from app.db import SessionLocal
        with SessionLocal() as s:
            consent = s.query(Consent).filter_by(user_id=100).first()
            assert consent is not None
            assert consent.doc_version == CONSENT_VERSION

    def test_consent_callback_applies_pending_deeplink(self):
        """Если юзер пришёл по deeplink — после согласия попадает на карточку."""
        _seed_user(100, with_consent=False)
        eid = _seed_event(title="Через deeplink")
        from app.db import SessionLocal
        with SessionLocal() as s:
            user = s.get(User, 100)
            ev = s.get(Event, eid)
            user.pending_deeplink_payload = ev.deeplink_payload
            s.commit()

        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": "consent"}},
            fake,
        ))

        assert any("Через deeplink" in t for t in fake.texts_sent())
        with SessionLocal() as s:
            user = s.get(User, 100)
            assert user.pending_deeplink_payload is None


class TestCommands:
    def test_about_shows_disclaimer(self):
        _seed_user(100, with_consent=True)
        fake = FakeMaxClient()

        _run(h.on_message(
            {"user": {"user_id": 100}, "message": {"body": {"text": "/about"}}},
            fake,
        ))

        text = " ".join(fake.texts_sent())
        assert "хакатон" in text.lower()
        assert "не является официальной" in text.lower()

    def test_help_command_shows_help(self):
        _seed_user(100, with_consent=True)
        fake = FakeMaxClient()
        _run(h.on_message(
            {"user": {"user_id": 100}, "message": {"body": {"text": "/help"}}},
            fake,
        ))
        assert any("афиша" in t.lower() or "помог" in t.lower() for t in fake.texts_sent())

    def test_notify_off_toggles_user_flag(self):
        _seed_user(100, with_consent=True)
        fake = FakeMaxClient()
        _run(h.on_message(
            {"user": {"user_id": 100}, "message": {"body": {"text": "/notify_off"}}},
            fake,
        ))
        from app.db import SessionLocal
        with SessionLocal() as s:
            assert s.get(User, 100).notifications_enabled is False

    def test_notify_on_re_enables_flag(self):
        _seed_user(100, with_consent=True)
        fake = FakeMaxClient()
        _run(h.on_message(
            {"user": {"user_id": 100}, "message": {"body": {"text": "/notify_off"}}},
            fake,
        ))
        _run(h.on_message(
            {"user": {"user_id": 100}, "message": {"body": {"text": "/notify_on"}}},
            fake,
        ))
        from app.db import SessionLocal
        with SessionLocal() as s:
            assert s.get(User, 100).notifications_enabled is True


class TestCallbackGuards:
    def test_callback_without_consent_shows_required(self):
        _seed_user(100, with_consent=False)
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": "events"}},
            fake,
        ))
        text = " ".join(fake.texts_sent()).lower()
        assert "согласие" in text


class TestSignupFlow:
    def test_signup_callback_shows_summary(self):
        _seed_user(100, with_consent=True)
        eid = _seed_event(title="Без слотов", capacity=5)
        fake = FakeMaxClient()

        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"signup:{eid}"}},
            fake,
        ))

        assert any("проверьте" in t.lower() or "подтверд" in t.lower()
                   for t in fake.texts_sent())

    def test_confirm_creates_registration(self):
        _seed_user(100, with_consent=True)
        eid = _seed_event(capacity=5)
        fake = FakeMaxClient()

        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"confirm:{eid}"}},
            fake,
        ))

        from app.db import SessionLocal
        with SessionLocal() as s:
            reg = s.query(Registration).filter_by(event_id=eid, user_id=100).first()
            assert reg is not None
            assert reg.status == RegStatus.CONFIRMED
            assert reg.code.startswith("RG-")

    def test_double_tap_confirm_handled_gracefully(self):
        """Двойной клик по «Подтверждаю» — без исключений и дубля записи."""
        _seed_user(100, with_consent=True)
        eid = _seed_event(capacity=5)
        fake = FakeMaxClient()

        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"confirm:{eid}"}},
            fake,
        ))
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"confirm:{eid}"}},
            fake,
        ))
        from app.db import SessionLocal
        with SessionLocal() as s:
            count = s.query(Registration).filter_by(event_id=eid, user_id=100).count()
            assert count == 1


class TestCancelFlow:
    def _setup_with_reg(self, late_policy: str, starts_at: datetime) -> tuple[int, int]:
        """user+event+reg → (event_id, registration_id).

        sign_up не пускает на уже прошедшие — создаём в будущем, потом
        сдвигаем event.starts_at в нужный момент для теста late-cancel.
        """
        _seed_user(100, with_consent=True)
        eid = _seed_event(capacity=5, late_cancel_policy=late_policy)
        from app.db import SessionLocal
        from app.services.registration import sign_up
        with SessionLocal() as s:
            sign_up(s, event_id=eid, user_id=100)
            s.commit()
            ev = s.get(Event, eid)
            ev.starts_at = starts_at
            s.commit()
            reg = s.query(Registration).filter_by(event_id=eid, user_id=100).first()
            reg_id = reg.id
        return eid, reg_id

    def test_user_cancel_normal_path(self):
        """До старта мероприятия — обычная отмена без флага «поздняя»."""
        _, reg_id = self._setup_with_reg(
            LateCancelPolicy.DISALLOW,
            datetime.now(UTC) + timedelta(hours=2),
        )
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"cancel_yes:{reg_id}"}},
            fake,
        ))
        text = " ".join(fake.texts_sent()).lower()
        assert "отменен" in text and "поздн" not in text

    def test_user_late_cancel_disallow_returns_forbidden(self):
        _, reg_id = self._setup_with_reg(
            LateCancelPolicy.DISALLOW,
            datetime.now(UTC) - timedelta(hours=1),
        )
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"cancel_yes:{reg_id}"}},
            fake,
        ))
        text = " ".join(fake.texts_sent()).lower()
        assert "уже нельзя" in text or "началось" in text

    def test_user_late_cancel_allow_marked_proceeds(self):
        eid, reg_id = self._setup_with_reg(
            LateCancelPolicy.ALLOW_MARKED,
            datetime.now(UTC) - timedelta(minutes=30),
        )
        fake = FakeMaxClient()
        _run(h.on_callback(
            {"user": {"user_id": 100}, "callback": {"payload": f"cancel_yes:{reg_id}"}},
            fake,
        ))
        text = " ".join(fake.texts_sent()).lower()
        assert "поздн" in text
        from app.db import SessionLocal
        with SessionLocal() as s:
            assert s.get(Registration, reg_id).status == RegStatus.LATE_CANCELLED


def test_notif_off_for_registration_disables_flag():
    _seed_user(100, with_consent=True)
    eid = _seed_event(capacity=5)
    from app.db import SessionLocal
    from app.services.registration import sign_up
    with SessionLocal() as s:
        sign_up(s, event_id=eid, user_id=100)
        s.commit()
        reg_id = s.query(Registration).first().id

    fake = FakeMaxClient()
    _run(h.on_callback(
        {"user": {"user_id": 100}, "callback": {"payload": f"notif_off:{reg_id}"}},
        fake,
    ))

    with SessionLocal() as s:
        assert s.get(Registration, reg_id).notifications_enabled is False
