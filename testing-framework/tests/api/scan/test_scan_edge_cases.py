"""Edge-cases сканера QR через REST /api/v1/scan."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from config.urls import path_scan
from core.api_client import ApiClient
from steps.api.event_steps import change_status, patch_event
from utils.sut_db_helpers import (
    seed_signup,
    seed_user,
    set_registration_status,
    sut_session,
)


@pytest.mark.edge
@pytest.mark.api
@pytest.mark.pos
def test_scan_before_event_start_succeeds(
    api_as_organizer: ApiClient,
    published_event: dict,
) -> None:
    """TC-API-SCAN-EDGE-001: мероприятие ещё не началось → scan ok."""
    event_id = published_event["id"]
    future = (datetime.utcnow() + timedelta(days=14)).replace(microsecond=0).isoformat()
    patch_event(api_as_organizer, event_id, {"starts_at": future})

    with sut_session() as db:
        seed_user(db, 890_001)
        reg = seed_signup(db, event_id, 890_001)
        token = reg.qr_token

    resp = api_as_organizer.post_json(path_scan(), json={"qr_token": token})

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert resp.json()["ok"] is True
    assert resp.json()["status"] == "ok"


@pytest.mark.edge
@pytest.mark.api
@pytest.mark.pos
def test_scan_finished_event_still_accepts_attendance(
    api_as_organizer: ApiClient,
    published_event: dict,
) -> None:
    """TC-API-SCAN-EDGE-002: FINISHED → scan проходит (лимит только по reg.status)."""
    event_id = published_event["id"]

    with sut_session() as db:
        seed_user(db, 890_002)
        reg = seed_signup(db, event_id, 890_002)
        token = reg.qr_token

    change_status(api_as_organizer, event_id, "finished")

    resp = api_as_organizer.post_json(path_scan(), json={"qr_token": token})

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert resp.json()["ok"] is True
    assert resp.json()["status"] == "ok"


@pytest.mark.edge
@pytest.mark.api
@pytest.mark.neg
def test_scan_cancelled_registration_returns_cancelled_status(
    api_as_organizer: ApiClient,
    published_event: dict,
) -> None:
    """TC-API-SCAN-EDGE-003: отменённая запись → status=cancelled."""
    event_id = published_event["id"]

    with sut_session() as db:
        seed_user(db, 890_003)
        reg = seed_signup(db, event_id, 890_003)
        set_registration_status(db, reg.id, "cancelled")
        token = reg.qr_token

    resp = api_as_organizer.post_json(path_scan(), json={"qr_token": token})

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert resp.json()["ok"] is False
    assert resp.json()["status"] == "cancelled"
