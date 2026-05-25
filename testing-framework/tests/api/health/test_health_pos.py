"""Positive: /api/v1/healthz, /readyz."""
from __future__ import annotations

import pytest

from config.urls import path_healthz, path_readyz
from core.api_client import ApiClient


@pytest.mark.smoke
def test_healthz_returns_alive(api_client: ApiClient) -> None:
    resp = api_client.get(path_healthz())

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body.get("ok") is True
    assert body.get("message") == "alive"


@pytest.mark.smoke
def test_readyz_returns_ready(api_client: ApiClient) -> None:
    resp = api_client.get(path_readyz())

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body.get("ok") is True
    assert body.get("message") == "ready"
