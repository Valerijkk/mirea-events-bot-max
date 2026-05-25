"""Positive: POST /api/v1/auth/login."""
from __future__ import annotations

import pytest

from config.settings import Settings
from config.urls import path_login
from core.api_client import ApiClient


@pytest.mark.smoke
def test_login_admin_returns_bearer_token(api_client: ApiClient, settings: Settings) -> None:
    payload = {
        "email": settings.admin_email,
        "password": settings.admin_password_value,
    }

    resp = api_client.post_json(path_login(), json=payload)

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["token_type"] == "bearer"
    # TTL задаётся настройкой SUT `jwt_expire_minutes` — точное значение нам
    # тут не важно, важно что оно положительное и в разумном диапазоне.
    assert isinstance(body["expires_in"], int)
    assert 60 <= body["expires_in"] <= 7 * 24 * 3600
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 20


def test_login_organizer_returns_token(api_client: ApiClient, settings: Settings) -> None:
    payload = {
        "email": settings.organizer_email,
        "password": settings.organizer_password_value,
    }

    resp = api_client.post_json(path_login(), json=payload)

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["access_token"]
    assert body["token_type"] == "bearer"
