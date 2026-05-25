"""Positive: фильтры списка /api/v1/events."""
from __future__ import annotations

import pytest

from config.urls import path_events
from core.api_client import ApiClient


@pytest.mark.smoke
def test_list_events_returns_array(api_as_organizer: ApiClient) -> None:
    resp = api_as_organizer.get(path_events())

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert isinstance(body, list)


def test_filter_status_published_returns_only_published(api_as_admin: ApiClient) -> None:
    resp = api_as_admin.get(path_events(), params={"status": "published"})

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert all(item["status"] == "published" for item in body)


def test_only_upcoming_returns_future_events(api_as_admin: ApiClient) -> None:
    resp = api_as_admin.get(path_events(), params={"only_upcoming": "true"})

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"


def test_limit_one_returns_one_item(api_as_admin: ApiClient) -> None:
    resp = api_as_admin.get(path_events(), params={"limit": 1})

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert len(resp.json()) <= 1
