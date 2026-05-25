"""API-шаги для рассылок."""
from __future__ import annotations

from typing import Any

from config.urls import path_event_broadcasts
from core.api_client import ApiClient
from core.exceptions import ApiError


def create_broadcast(
    api: ApiClient,
    event_id: int,
    message: str,
    segment: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": message}
    if segment is not None:
        payload["segment"] = segment
    resp = api.post_json(path_event_broadcasts(event_id), json=payload)
    if resp.status_code not in (200, 201):
        raise ApiError(resp, f"broadcast {event_id} → {resp.status_code}")
    return resp.json()


def list_broadcasts(api: ApiClient, event_id: int) -> list[dict[str, Any]]:
    resp = api.get(path_event_broadcasts(event_id))
    if resp.status_code != 200:
        raise ApiError(resp, f"list broadcasts {event_id} → {resp.status_code}")
    return resp.json()
