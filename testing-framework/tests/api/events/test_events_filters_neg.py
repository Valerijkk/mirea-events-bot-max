"""Negative: фильтры /api/v1/events."""
from __future__ import annotations

import pytest

from config.urls import path_events
from core.api_client import ApiClient


def test_list_without_token_returns_401(api_client: ApiClient) -> None:
    resp = api_client.get(path_events())

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


@pytest.mark.parametrize(
    "limit",
    [0, -1, 501, 10_000],
    ids=["zero", "negative", "above-500", "huge"],
)
def test_limit_out_of_range_returns_422(api_as_organizer: ApiClient, limit: int) -> None:
    resp = api_as_organizer.get(path_events(), params={"limit": limit})

    assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"


def test_invalid_token_returns_401(api_client: ApiClient) -> None:
    resp = api_client.get(
        path_events(),
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"
