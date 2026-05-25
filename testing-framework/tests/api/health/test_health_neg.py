"""Negative: метод POST на /healthz должен дать 405."""
from __future__ import annotations

from config.urls import path_healthz
from core.api_client import ApiClient


def test_post_to_healthz_returns_405(api_client: ApiClient) -> None:
    resp = api_client.request("POST", path_healthz())

    assert resp.status_code == 405, f"Ожидали 405, получили {resp.status_code}: {resp.text}"
