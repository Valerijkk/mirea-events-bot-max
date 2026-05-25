"""Negative: CRUD /api/v1/events."""
from __future__ import annotations

import pytest

from config.urls import path_event, path_events
from core.api_client import ApiClient
from factories.event_factory import minimal_event_payload


def test_create_event_without_token_returns_401(api_client: ApiClient) -> None:
    resp = api_client.post_json(path_events(), json=minimal_event_payload())

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


@pytest.mark.parametrize(
    "field,value",
    [
        pytest.param("title", "ab", id="title-too-short"),
        pytest.param("capacity", 0, id="capacity-zero"),
        pytest.param("capacity", -10, id="capacity-negative"),
        pytest.param("starts_at", "не-iso", id="bad-starts-at"),
    ],
)
def test_create_event_invalid_payload_422(
    api_as_organizer: ApiClient,
    field: str,
    value: object,
) -> None:
    payload = minimal_event_payload()
    payload[field] = value

    resp = api_as_organizer.post_json(path_events(), json=payload)

    assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"


def test_get_nonexistent_event_returns_404(api_as_organizer: ApiClient) -> None:
    resp = api_as_organizer.get(path_event(999_999_999))

    assert resp.status_code == 404, f"Ожидали 404, получили {resp.status_code}: {resp.text}"


def test_get_other_organizer_event_returns_403(
    api_as_organizer: ApiClient,
    api_as_second_organizer: ApiClient,
    clean_event: dict,
) -> None:
    # clean_event принадлежит первому организатору.

    # второй организатор пытается прочитать чужое.
    resp = api_as_second_organizer.get(path_event(clean_event["id"]))

    # IDOR-защита
    assert resp.status_code == 403, f"Ожидали 403, получили {resp.status_code}: {resp.text}"


def test_delete_nonexistent_event_returns_404(api_as_organizer: ApiClient) -> None:
    resp = api_as_organizer.delete(path_event(999_999_999))

    assert resp.status_code == 404, f"Ожидали 404, получили {resp.status_code}: {resp.text}"


@pytest.mark.api
@pytest.mark.neg
@pytest.mark.parametrize("bad_capacity", [0, -1, -100])
def test_create_event_invalid_capacity_returns_422(
    api_as_organizer: ApiClient,
    bad_capacity: int,
) -> None:
    """BVA: capacity ниже минимума (1) → 422."""
    payload = minimal_event_payload()
    payload["capacity"] = bad_capacity
    resp = api_as_organizer.post_json(path_events(), json=payload)
    assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"


@pytest.mark.api
@pytest.mark.pos
def test_create_event_minimum_valid_capacity_returns_201(
    api_as_organizer: ApiClient,
) -> None:
    """BVA: capacity=1 (минимально допустимое) → 201."""
    payload = minimal_event_payload()
    payload["capacity"] = 1
    resp = api_as_organizer.post_json(path_events(), json=payload)
    assert resp.status_code == 201, f"Ожидали 201, получили {resp.status_code}: {resp.text}"
    api_as_organizer.delete(path_event(resp.json()["id"]))
