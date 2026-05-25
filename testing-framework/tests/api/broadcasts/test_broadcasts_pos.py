"""Positive: /api/v1/events/{id}/broadcasts."""
from __future__ import annotations

from config.urls import path_event_broadcasts
from core.api_client import ApiClient
from utils.test_helpers import published_event_id_or_skip


def test_broadcast_history_returns_list(api_as_admin: ApiClient) -> None:
    event_id = published_event_id_or_skip(api_as_admin)

    resp = api_as_admin.get(path_event_broadcasts(event_id))

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert isinstance(resp.json(), list)


def test_create_broadcast_returns_delivered_count(api_as_admin: ApiClient) -> None:
    event_id = published_event_id_or_skip(api_as_admin)
    payload = {"message": "Напоминание для тестов QA.", "segment": "confirmed"}

    resp = api_as_admin.post_json(path_event_broadcasts(event_id), json=payload)

    assert resp.status_code in (200, 201), (
        f"Ожидали 200 или 201, получили {resp.status_code}: {resp.text}"
    )
    body = resp.json()

    # Контракт: рассылка может приходить либо плоско, либо обёрнутой в ключ "broadcast".
    rendered = body.get("broadcast", body)

    assert "delivered_count" in rendered
    assert rendered["delivered_count"] >= 0
