"""Негативные тесты подделки JWT.

Покрывает 4 классические атаки: пустой токен, подмена payload, подмена
подписи, expired-токен. Все должны давать 401 — никаких 500-ок или
утечек в теле ответа.
"""
from __future__ import annotations

import base64
import json
import time

import pytest

from config.urls import path_events
from core.api_client import ApiClient
from utils.allure_helpers import step
from utils.assertions import assert_no_secret_leak, assert_status

pytestmark = [pytest.mark.api, pytest.mark.neg, pytest.mark.regression]


def _make_token(payload: dict[str, object], signature: str = "BAD") -> str:
    """Собрать псевдо-JWT `header.payload.signature` без честной подписи.

    Локальный хелпер: используется только в этом файле (атаки на структуру JWT).
    """
    header_b64 = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.{signature}"


def test_empty_token_rejected(api_client: ApiClient) -> None:
    with step("GET /api/v1/events с пустым Bearer (без значения)"):
        resp = api_client.get(path_events(), headers={"Authorization": "Bearer"})

    assert resp.status_code in (401, 403), f"ожидался 401/403, пришёл {resp.status_code}"
    assert_no_secret_leak(resp, ["traceback", "secret", "jwt_secret"])


def test_garbage_token_rejected(api_client: ApiClient) -> None:
    with step("GET /api/v1/events с мусором вместо токена"):
        resp = api_client.get(
            path_events(),
            headers={"Authorization": "Bearer xxx.yyy.zzz"},
        )

    assert resp.status_code in (401, 403)
    assert_no_secret_leak(resp, ["traceback", "internal"])


def test_tampered_payload_rejected(api_client: ApiClient) -> None:
    """Меняем `sub`/`role` в payload — подпись становится невалидной."""
    fake_token = _make_token({
        "sub": "999",
        "role": "admin",
        "exp": int(time.time()) + 3600,
    })

    with step("GET /api/v1/events с поддельным admin-токеном"):
        resp = api_client.get(
            path_events(),
            headers={"Authorization": f"Bearer {fake_token}"},
        )

    assert resp.status_code in (401, 403), (
        f"подделанный JWT с admin должен отбиваться 401, а не {resp.status_code}"
    )


def test_expired_token_rejected(api_client: ApiClient) -> None:
    fake_token = _make_token({
        "sub": "1",
        "role": "admin",
        "exp": int(time.time()) - 3600,
    })

    with step("GET /api/v1/events с просроченным токеном"):
        resp = api_client.get(
            path_events(),
            headers={"Authorization": f"Bearer {fake_token}"},
        )

    assert resp.status_code in (401, 403)


def test_missing_authorization_header(api_client: ApiClient) -> None:
    with step("GET /api/v1/events без Authorization вообще"):
        resp = api_client.get(path_events())

    assert_status(resp, 401)


def test_wrong_scheme_rejected(api_client: ApiClient) -> None:
    """Basic-auth вместо Bearer — должен отбиваться."""
    with step("GET /api/v1/events с Basic-схемой"):
        resp = api_client.get(
            path_events(),
            headers={"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="},
        )

    assert resp.status_code in (401, 403)
