"""Negative: POST /api/v1/events/{id}/status."""
from __future__ import annotations

import pytest

from config.urls import path_event_status
from core.api_client import ApiClient


@pytest.mark.parametrize(
    "value",
    ["", "garbage", "DRAFT", "published_"],
    ids=["empty", "garbage", "wrong-case", "trailing-underscore"],
)
def test_invalid_status_value_returns_422(
    api_as_organizer: ApiClient, clean_event: dict, value: str,
) -> None:
    resp = api_as_organizer.post_json(
        path_event_status(clean_event["id"]),
        json={"status": value},
    )

    assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"


def test_change_status_other_organizer_returns_403(
    api_as_second_organizer: ApiClient, clean_event: dict,
) -> None:
    # clean_event принадлежит первому организатору.

    # второй организатор пытается сменить статус чужого события
    resp = api_as_second_organizer.post_json(
        path_event_status(clean_event["id"]),
        json={"status": "published"},
    )

    # IDOR-защита
    assert resp.status_code == 403, f"Ожидали 403, получили {resp.status_code}: {resp.text}"
