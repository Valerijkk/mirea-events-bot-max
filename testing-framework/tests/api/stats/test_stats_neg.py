"""Negative: /api/v1/stats и /api/v1/events/{id}/stats."""
from __future__ import annotations

from config.urls import path_event_stats, path_stats
from core.api_client import ApiClient


def test_global_stats_without_token_401(api_client: ApiClient) -> None:
    resp = api_client.get(path_stats())

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


def test_event_stats_nonexistent_404(api_as_admin: ApiClient) -> None:
    resp = api_as_admin.get(path_event_stats(999_999_999))

    assert resp.status_code == 404, f"Ожидали 404, получили {resp.status_code}: {resp.text}"


def test_event_stats_other_organizer_403(
    api_as_second_organizer,
    clean_event: dict,
) -> None:
    # clean_event принадлежит первому организатору.

    resp = api_as_second_organizer.get(path_event_stats(clean_event["id"]))

    # IDOR-защита
    assert resp.status_code == 403, f"Ожидали 403, получили {resp.status_code}: {resp.text}"
