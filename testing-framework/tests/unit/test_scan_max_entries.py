"""Тесты `max_entries` — лимит проходов: 1 (одноразовый), N (тур), 0 (безлимит)."""
from __future__ import annotations

import asyncio

import pytest

from app.models import Registration, RegStatus
from app.services.registration import sign_up, upsert_user
from app.services.scan import scan_lookup


def _scan(session, organizer, needle):
    return asyncio.run(scan_lookup(session, organizer, needle))


@pytest.fixture
def setup(session, organizer, event_factory):
    """Возвращает (event, reg) — мероприятие + одну confirmed-запись."""
    event = event_factory(capacity=10)
    upsert_user(session, max_user_id=100, chat_id=100, name="Тест")
    reg = sign_up(session, event_id=event.id, user_id=100).registration
    session.commit()
    return event, reg


def test_default_max_entries_is_one(setup, session, organizer):
    event, reg = setup
    assert event.max_entries == 1

    r1 = _scan(session, organizer, reg.qr_token)
    assert r1.ok is True
    assert r1.status == "ok"

    r2 = _scan(session, organizer, reg.qr_token)
    assert r2.ok is False
    assert r2.status == "already_attended"
    assert "лимит" in (r2.error or "").lower()


def test_max_entries_3_allows_three_scans(setup, session, organizer):
    event, reg = setup
    event.max_entries = 3
    session.commit()

    # 3 успешных скана подряд
    for i in range(3):
        r = _scan(session, organizer, reg.qr_token)
        assert r.ok is True, f"скан #{i+1} провалился: {r.error}"
        assert r.status == "ok"

    # 4-й — отказ
    r4 = _scan(session, organizer, reg.qr_token)
    assert r4.ok is False
    assert r4.status == "already_attended"

    # entries_count в БД сохранён
    session.expire_all()
    assert session.get(Registration, reg.id).entries_count == 3


def test_max_entries_0_means_unlimited(setup, session, organizer):
    """max_entries=0 — безлимит (сезонный абонемент)."""
    event, reg = setup
    event.max_entries = 0
    session.commit()

    # 10 сканов подряд — все ok
    for i in range(10):
        r = _scan(session, organizer, reg.qr_token)
        assert r.ok is True, f"скан #{i+1} провалился"

    session.expire_all()
    assert session.get(Registration, reg.id).entries_count == 10


def test_subsequent_scans_dont_change_attended_at(setup, session, organizer):
    """attended_at — время ПЕРВОГО скана (для аудита). last_entry_at — последнего."""
    event, reg = setup
    event.max_entries = 3
    session.commit()

    _scan(session, organizer, reg.qr_token)
    session.expire_all()
    first_attended_at = session.get(Registration, reg.id).attended_at
    assert first_attended_at is not None

    _scan(session, organizer, reg.qr_token)
    _scan(session, organizer, reg.qr_token)

    session.expire_all()
    final = session.get(Registration, reg.id)
    assert final.attended_at == first_attended_at, "attended_at не должен меняться"
    assert final.last_entry_at >= first_attended_at, "last_entry_at растёт с каждым сканом"


def test_cancelled_registration_blocked_regardless_of_max_entries(setup, session, organizer):
    """Отмена записи бьёт max_entries: cancelled нельзя пускать ни при каком лимите."""
    event, reg = setup
    event.max_entries = 10
    reg.status = RegStatus.CANCELLED
    session.commit()

    r = _scan(session, organizer, reg.qr_token)
    assert r.ok is False
    assert r.status == "cancelled"


def test_scan_response_includes_entry_counter_text(setup, session, organizer):
    event, reg = setup
    event.max_entries = 5
    session.commit()

    r1 = _scan(session, organizer, reg.qr_token)
    assert r1.ok is True
    assert "1 из 5" in (r1.user_name or "")

    r2 = _scan(session, organizer, reg.qr_token)
    assert "2 из 5" in (r2.user_name or "")


def test_unlimited_scan_shows_progress_label(setup, session, organizer):
    event, reg = setup
    event.max_entries = 0
    session.commit()

    r = _scan(session, organizer, reg.qr_token)
    assert r.ok is True
    assert "без ограничений" in (r.user_name or "").lower()
