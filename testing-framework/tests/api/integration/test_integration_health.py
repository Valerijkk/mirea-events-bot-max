"""Pos + neg: GET /api/v1/integration/health."""
from __future__ import annotations

from config.urls import path_integration_health
from core.api_client import ApiClient


def test_integration_health_pos(api_as_integration: ApiClient) -> None:
    resp = api_as_integration.get(path_integration_health())

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body.get("status") == "ok"


def test_integration_health_without_key_401(api_client: ApiClient) -> None:
    resp = api_client.get(path_integration_health())

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


def test_integration_health_bad_key_401(api_client: ApiClient) -> None:
    bad = api_client.with_api_key("fake.never-existed")

    resp = bad.get(path_integration_health())

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"

    bad.close()
