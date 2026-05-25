"""Negative: POST /api/v1/auth/login — невалидные payload-ы."""
from __future__ import annotations

import pytest

from config.settings import Settings
from config.urls import path_login
from core.api_client import ApiClient


@pytest.mark.parametrize(
    ("email_key", "password"),
    [
        pytest.param("admin", "definitely-wrong-pwd", id="wrong-password"),
        pytest.param("unknown", "anything12345", id="unknown-email"),
    ],
)
def test_invalid_credentials_return_401(
    api_client: ApiClient,
    settings: Settings,
    email_key: str,
    password: str,
) -> None:
    email = settings.admin_email if email_key == "admin" else "nobody@nope.ru"
    payload = {"email": email, "password": password}

    resp = api_client.post_json(path_login(), json=payload)

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"
    assert "Неверный" in resp.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"email": "admin@mirea.ru", "password": ""}, id="empty-pwd"),
        pytest.param({"email": "not-an-email", "password": "x"}, id="bad-email"),
        pytest.param({}, id="empty-body"),
        pytest.param({"email": "admin@mirea.ru"}, id="missing-pwd"),
    ],
)
def test_invalid_payload_returns_422(api_client: ApiClient, payload: dict) -> None:
    resp = api_client.post_json(path_login(), json=payload)

    assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"
