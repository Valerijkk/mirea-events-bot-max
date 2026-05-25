"""Positive: /api/v1/stats и /api/v1/events/{id}/stats."""
from __future__ import annotations

import pytest

from config.urls import path_event_stats, path_events, path_stats
from core.api_client import ApiClient


@pytest.mark.smoke
def test_global_stats_returns_counters(api_as_admin: ApiClient) -> None:
    resp = api_as_admin.get(path_stats())

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    for key in ("total_users", "published_events", "active_registrations", "attended_total"):
        assert key in body, f"в /stats нет поля {key}: {body}"
        assert body[key] >= 0


def test_event_stats_funnel(api_as_admin: ApiClient) -> None:
    events = api_as_admin.get(path_events(), params={"limit": 1}).json()
    if not events:
        pytest.skip("Нет событий — нет статистики.")
    event_id = events[0]["id"]

    resp = api_as_admin.get(path_event_stats(event_id))

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    for key in ("confirmed", "waitlist", "cancelled", "attended", "capacity"):
        assert key in body

    assert 0.0 <= body.get("fill_rate", 0.0) <= 1.0
