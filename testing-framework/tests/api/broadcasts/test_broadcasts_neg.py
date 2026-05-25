"""Negative: /api/v1/events/{id}/broadcasts."""
from __future__ import annotations

from config.urls import path_event_broadcasts
from core.api_client import ApiClient


def test_broadcast_empty_message_returns_422(
    api_as_organizer: ApiClient, clean_event: dict,
) -> None:
    resp = api_as_organizer.post_json(
        path_event_broadcasts(clean_event["id"]),
        json={"message": ""},
    )

    assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"


def test_broadcast_other_organizer_returns_403(
    api_as_second_organizer: ApiClient, clean_event: dict,
) -> None:
    # clean_event принадлежит первому организатору.

    # рассылка от второго организатора
    resp = api_as_second_organizer.post_json(
        path_event_broadcasts(clean_event["id"]),
        json={"message": "Привет"},
    )

    # IDOR-защита
    assert resp.status_code == 403, f"Ожидали 403, получили {resp.status_code}: {resp.text}"


def test_broadcast_history_without_token_401(api_client: ApiClient) -> None:
    resp = api_client.get(path_event_broadcasts(1))

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"
