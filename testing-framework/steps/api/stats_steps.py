"""API-шаги статистики."""
from __future__ import annotations

from typing import Any

from config.urls import path_event_stats, path_stats
from core.api_client import ApiClient
from core.exceptions import ApiError


def global_stats(api: ApiClient) -> dict[str, Any]:
    resp = api.get(path_stats())
    if resp.status_code != 200:
        raise ApiError(resp, f"stats → {resp.status_code}")
    return resp.json()


def event_stats(api: ApiClient, event_id: int) -> dict[str, Any]:
    resp = api.get(path_event_stats(event_id))
    if resp.status_code != 200:
        raise ApiError(resp, f"event stats {event_id} → {resp.status_code}")
    return resp.json()
