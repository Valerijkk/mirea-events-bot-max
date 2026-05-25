"""API-шаги авторизации."""
from __future__ import annotations

from config.urls import path_login
from core.api_client import ApiClient
from core.exceptions import ApiError


def get_token(client: ApiClient, email: str, password: str) -> str:
    resp = client.post_json(path_login(), json={"email": email, "password": password})
    if resp.status_code != 200:
        raise ApiError(resp, f"login {email} → {resp.status_code}")
    return resp.json()["access_token"]
