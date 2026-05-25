"""Positive + IDOR: REST /api/v1/events/{id}/slots."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from config.urls import path_event_slot, path_event_slots
from core.api_client import ApiClient


def _slot_payload(*, hours_from_now: int = 2, capacity: int = 10) -> dict[str, object]:
    starts_at = (datetime.now() + timedelta(hours=hours_from_now)).replace(microsecond=0)
    return {
        "starts_at": starts_at.isoformat(),
        "capacity": capacity,
        "label": "Группа A",
    }


@pytest.mark.api
@pytest.mark.pos
def test_get_slots_returns_list(
    api_as_organizer: ApiClient,
    clean_event: dict,
) -> None:
    """GET /api/v1/events/{id}/slots возвращает список слотов."""
    resp = api_as_organizer.get(path_event_slots(clean_event["id"]))

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert isinstance(body, list)


@pytest.mark.api
@pytest.mark.pos
def test_create_slot_returns_created(
    api_as_organizer: ApiClient,
    clean_event: dict,
) -> None:
    """POST /api/v1/events/{id}/slots создаёт слот."""
    payload = _slot_payload()

    resp = api_as_organizer.post_json(path_event_slots(clean_event["id"]), json=payload)

    assert resp.status_code == 201, f"Ожидали 201, получили {resp.status_code}: {resp.text}"
    slot = resp.json()

    assert slot["id"] > 0
    assert slot["event_id"] == clean_event["id"]
    assert slot["capacity"] == payload["capacity"]
    assert slot["label"] == payload["label"]
    assert slot["free_slots"] == payload["capacity"]


@pytest.mark.api
@pytest.mark.neg
def test_delete_slot_idor_returns_403(
    api_as_organizer: ApiClient,
    api_as_second_organizer: ApiClient,
    clean_event: dict,
) -> None:
    """DELETE слота чужого мероприятия → 403."""
    created = api_as_organizer.post_json(
        path_event_slots(clean_event["id"]),
        json=_slot_payload(),
    )
    assert created.status_code == 201, (
        f"Ожидали 201, получили {created.status_code}: {created.text}"
    )
    slot_id = created.json()["id"]

    resp = api_as_second_organizer.delete(path_event_slot(clean_event["id"], slot_id))

    assert resp.status_code == 403, f"Ожидали 403, получили {resp.status_code}: {resp.text}"
