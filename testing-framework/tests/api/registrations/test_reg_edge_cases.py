"""Edge-cases регистраций: REST + seed через БД SUT.

REST `/events/{id}/registrations` — read-only; sign_up/cancel живут в боте.
Записи создаём через `utils.sut_db_helpers`, инварианты проверяем через API.
"""
from __future__ import annotations

import pytest

from config.urls import path_event, path_event_registrations, path_scan
from core.api_client import ApiClient
from steps.api.event_steps import change_status, patch_event
from utils.sut_db_helpers import (
    seed_signup,
    seed_user,
    sut_session,
)


@pytest.mark.edge
@pytest.mark.neg
def test_duplicate_signup_keeps_single_registration_row(
    api_as_organizer: ApiClient,
    published_event: dict,
) -> None:
    """TC-API-REG-EDGE-001: повторная запись → та же строка, не дубль."""
    event_id = published_event["id"]
    user_id = 880_001

    with sut_session() as db:
        seed_user(db, user_id)
        first = seed_signup(db, event_id, user_id)
        first_id = first.id
        second = seed_signup(db, event_id, user_id)

    assert second.id == first_id

    body = api_as_organizer.get(path_event_registrations(event_id)).json()
    user_regs = [r for r in body if r.get("user_id") == user_id]

    assert len(user_regs) == 1
    assert user_regs[0]["status"] == "confirmed"


@pytest.mark.edge
@pytest.mark.neg
def test_full_capacity_next_signup_is_waitlist_in_api_list(
    api_as_organizer: ApiClient,
    published_event: dict,
) -> None:
    """TC-API-REG-EDGE-002: capacity=1, без слотов → следующий в waitlist."""
    event_id = published_event["id"]
    patch_event(api_as_organizer, event_id, {"capacity": 1})

    with sut_session() as db:
        seed_user(db, 880_010)
        seed_user(db, 880_011)
        seed_signup(db, event_id, 880_010)
        waitlist_reg = seed_signup(db, event_id, 880_011)

    assert waitlist_reg.status == "waitlist"

    waitlist = api_as_organizer.get(
        path_event_registrations(event_id),
        params={"status": "waitlist"},
    ).json()

    assert any(r["user_id"] == 880_011 for r in waitlist)
    assert all(r["status"] == "waitlist" for r in waitlist)


@pytest.mark.edge
@pytest.mark.neg
def test_list_registrations_nonexistent_event_returns_404(
    api_as_organizer: ApiClient,
) -> None:
    """TC-API-REG-EDGE-003: несуществующее мероприятие → 404."""
    resp = api_as_organizer.get(path_event_registrations(999_999_998))

    assert resp.status_code == 404, f"Ожидали 404, получили {resp.status_code}: {resp.text}"


@pytest.mark.edge
@pytest.mark.security
@pytest.mark.neg
def test_list_registrations_other_organizer_returns_403(
    api_as_second_organizer: ApiClient,
    published_event: dict,
) -> None:
    """TC-API-REG-EDGE-004: IDOR — чужой organizer не видит записи."""
    resp = api_as_second_organizer.get(path_event_registrations(published_event["id"]))

    assert resp.status_code == 403, f"Ожидали 403, получили {resp.status_code}: {resp.text}"


@pytest.mark.edge
@pytest.mark.neg
def test_registration_closed_reflected_in_event_get(
    api_as_organizer: ApiClient,
    published_event: dict,
) -> None:
    """TC-API-REG-EDGE-005: registration_open=False → free_slots=0 в GET."""
    event_id = published_event["id"]
    change_status(api_as_organizer, event_id, "published")

    patch_event(api_as_organizer, event_id, {"registration_open": False})

    body = api_as_organizer.get(path_event(event_id)).json()

    assert body["registration_open"] is False
    assert body["free_slots"] == 0


@pytest.mark.edge
@pytest.mark.neg
def test_scan_already_attended_is_idempotent(
    api_as_organizer: ApiClient,
    published_event: dict,
) -> None:
    """TC-API-REG-EDGE-006: повторный scan → already_attended (200, не 409)."""
    event_id = published_event["id"]

    with sut_session() as db:
        seed_user(db, 880_020)
        reg = seed_signup(db, event_id, 880_020)
        token = reg.qr_token

    first = api_as_organizer.post_json(path_scan(), json={"qr_token": token})
    second = api_as_organizer.post_json(path_scan(), json={"qr_token": token})

    assert first.status_code == 200, f"Ожидали 200, получили {first.status_code}: {first.text}"
    assert first.json()["status"] == "ok"
    assert second.status_code == 200, f"Ожидали 200, получили {second.status_code}: {second.text}"
    assert second.json()["status"] == "already_attended"


@pytest.mark.edge
@pytest.mark.neg
def test_scan_invalid_qr_token_returns_not_found(
    api_as_organizer: ApiClient,
) -> None:
    """TC-API-REG-EDGE-007: невалидный токен → not_found (oracle-mitigation, не 404)."""
    resp = api_as_organizer.post_json(
        path_scan(),
        json={"qr_token": "00000000000000000000000000000000"},
    )

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert resp.json()["status"] == "not_found"
    assert resp.json()["ok"] is False
