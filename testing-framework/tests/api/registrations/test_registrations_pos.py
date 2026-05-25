"""Positive: GET /api/v1/events/{id}/registrations (read-only — данные из seed)."""
from __future__ import annotations

import pytest

from config.urls import path_event_registrations
from core.api_client import ApiClient
from utils.test_helpers import published_event_id_or_skip


def test_list_registrations_returns_array(api_as_admin: ApiClient) -> None:
    event_id = published_event_id_or_skip(api_as_admin)

    resp = api_as_admin.get(path_event_registrations(event_id))

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert isinstance(body, list)


def test_filter_status_confirmed(api_as_admin: ApiClient) -> None:
    event_id = published_event_id_or_skip(api_as_admin)

    resp = api_as_admin.get(
        path_event_registrations(event_id),
        params={"status": "confirmed"},
    )

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert all(item["status"] == "confirmed" for item in resp.json())


def test_registration_code_format(api_as_admin: ApiClient) -> None:
    event_id = published_event_id_or_skip(api_as_admin)

    body = api_as_admin.get(path_event_registrations(event_id)).json()

    if not body:
        pytest.skip("У выбранного события нет регистраций — нечего проверять.")

    code = body[0]["code"]

    assert code.startswith("RG-"), f"код регистрации не по формату: {code}"
