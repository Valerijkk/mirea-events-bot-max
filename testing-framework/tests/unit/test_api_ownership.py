"""Multi-tenant изоляция REST API (CR-01): организатор A не видит данные B,
admin обходит проверку. Тестируем `get_owned_event` напрямую, без TestClient —
иначе lifespan полез бы в MAX API.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.admin.auth import hash_password
from app.api.deps import get_owned_event
from app.models import Event, EventStatus, EventType, Organizer

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def alice_and_bob(session) -> tuple[Organizer, Organizer]:
    """Два рядовых организатора с одинаковыми правами, но разными id."""
    alice = Organizer(
        email="alice@mirea.ru",
        password_hash=hash_password("p" * 12),
        name="Alice", department="Каф. ИТ", role="organizer",
    )
    bob = Organizer(
        email="bob@mirea.ru",
        password_hash=hash_password("p" * 12),
        name="Bob", department="Каф. ФИ", role="organizer",
    )
    session.add_all([alice, bob])
    session.commit()
    return alice, bob


@pytest.fixture
def super_admin(session) -> Organizer:
    """Организатор с role='admin' — должен обходить owner-проверку."""
    org = Organizer(
        email="boss@mirea.ru",
        password_hash=hash_password("p" * 12),
        name="Boss", department="Ректорат", role="admin",
    )
    session.add(org)
    session.commit()
    return org


def _make_event(session, organizer: Organizer, title: str = "Test") -> Event:
    from datetime import datetime, timedelta
    ev = Event(
        title=title,
        event_type=EventType.OTHER,
        starts_at=datetime.utcnow() + timedelta(days=7),
        location="x",
        capacity=10,
        organizer_id=organizer.id,
        status=EventStatus.PUBLISHED,
    )
    session.add(ev)
    session.commit()
    return ev


# ---------------------------------------------------------------------------
# Owner OK
# ---------------------------------------------------------------------------

def test_owner_can_access_own_event(session, alice_and_bob):
    alice, _ = alice_and_bob
    event = _make_event(session, alice, title="Alice event")

    result = get_owned_event(event_id=event.id, organizer=alice, session=session)

    assert result is event


# ---------------------------------------------------------------------------
# Foreign organizer → 403
# ---------------------------------------------------------------------------

def test_foreign_organizer_gets_403(session, alice_and_bob):
    alice, bob = alice_and_bob
    alice_event = _make_event(session, alice, title="Alice private")

    with pytest.raises(HTTPException) as exc:
        get_owned_event(event_id=alice_event.id, organizer=bob, session=session)
    assert exc.value.status_code == 403, f"Статус: {exc.value.status_code}"
    assert "прав" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# admin-роль обходит проверку
# ---------------------------------------------------------------------------

def test_admin_role_bypasses_owner_check(session, alice_and_bob, super_admin):
    alice, _ = alice_and_bob
    alice_event = _make_event(session, alice, title="Alice private")

    result = get_owned_event(event_id=alice_event.id, organizer=super_admin, session=session)

    assert result is alice_event


# ---------------------------------------------------------------------------
# Несуществующее мероприятие → 404
# ---------------------------------------------------------------------------

def test_missing_event_returns_404(session, alice_and_bob):
    alice, _ = alice_and_bob

    with pytest.raises(HTTPException) as exc:
        get_owned_event(event_id=9999, organizer=alice, session=session)
    assert exc.value.status_code == 404, f"Статус: {exc.value.status_code}"


# ---------------------------------------------------------------------------
# Свои + чужие в одной сессии — проверка не ломается при множественных вызовах
# ---------------------------------------------------------------------------

def test_multiple_lookups_independently_resolved(session, alice_and_bob):
    alice, bob = alice_and_bob
    ev_a = _make_event(session, alice, "A1")
    ev_b = _make_event(session, bob, "B1")

    # Alice видит своё, не видит Bob'ово
    assert get_owned_event(event_id=ev_a.id, organizer=alice, session=session) is ev_a
    with pytest.raises(HTTPException) as exc:
        get_owned_event(event_id=ev_b.id, organizer=alice, session=session)
    assert exc.value.status_code == 403, f"Статус: {exc.value.status_code}"

    # И симметрично
    assert get_owned_event(event_id=ev_b.id, organizer=bob, session=session) is ev_b
    with pytest.raises(HTTPException) as exc:
        get_owned_event(event_id=ev_a.id, organizer=bob, session=session)
    assert exc.value.status_code == 403, f"Статус: {exc.value.status_code}"
