"""Positive: POST /api/v1/events/{id}/status."""
from __future__ import annotations

import pytest

from config.urls import path_event, path_event_status
from core.api_client import ApiClient


@pytest.mark.smoke
def test_draft_to_published(api_as_organizer: ApiClient, clean_event: dict) -> None:
    resp = api_as_organizer.post_json(
        path_event_status(clean_event["id"]),
        json={"status": "published"},
    )

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert resp.json()["status"] == "published"


def test_published_to_cancelled_is_idempotent(
    api_as_organizer: ApiClient, clean_event: dict,
) -> None:
    api_as_organizer.post_json(
        path_event_status(clean_event["id"]),
        json={"status": "published"},
    )

    first = api_as_organizer.post_json(
        path_event_status(clean_event["id"]),
        json={"status": "cancelled"},
    )

    assert first.status_code == 200, f"Ожидали 200, получили {first.status_code}: {first.text}"

    # повторная отмена (идемпотентность)
    second = api_as_organizer.post_json(
        path_event_status(clean_event["id"]),
        json={"status": "cancelled"},
    )

    assert second.status_code == 200, f"Ожидали 200, получили {second.status_code}: {second.text}"

    final = api_as_organizer.get(path_event(clean_event["id"]))

    assert final.json()["status"] == "cancelled"
