"""Тесты безопасных HTTP-заголовков, выставляемых SUT глобально.

Проверяет, что middleware `app.core.security_headers` действительно
доезжает до ответа. Это ловит регрессию вида «middleware закомментировали,
тесты всё ещё зелёные».
"""
from __future__ import annotations

import pytest

from core.api_client import ApiClient
from utils.allure_helpers import step

pytestmark = [pytest.mark.api, pytest.mark.neg]


def test_x_frame_options_deny_on_spa(api_client: ApiClient) -> None:
    """React SPA не должна вставляться в iframe (clickjacking-защита)."""
    with step("GET /login"):
        resp = api_client.get("/login")

    assert resp.headers.get("X-Frame-Options", "").upper() in {"DENY", "SAMEORIGIN"}, (
        f"X-Frame-Options отсутствует или слабый: {resp.headers.get('X-Frame-Options')!r}"
    )


def test_content_type_options_nosniff(api_client: ApiClient) -> None:
    """nosniff — браузер не должен угадывать MIME, даже для JSON."""
    with step("GET /api/v1/healthz — публичный endpoint"):
        resp = api_client.get("/api/v1/healthz")

    assert resp.headers.get("X-Content-Type-Options", "").lower() == "nosniff", (
        f"X-Content-Type-Options должен быть 'nosniff', пришёл "
        f"{resp.headers.get('X-Content-Type-Options')!r}"
    )


def test_permissions_policy_restrictive(api_client: ApiClient) -> None:
    """Permissions-Policy блокирует камеру/мик/геолокацию для SUT (PII-защита)."""
    resp = api_client.get("/login")

    policy = resp.headers.get("Permissions-Policy", "")

    assert any(p in policy for p in ("camera", "microphone", "geolocation")), (
        f"Permissions-Policy не блокирует чувствительные API: {policy!r}"
    )


def test_no_server_version_leak(api_client: ApiClient) -> None:
    """Server header не должен раскрывать конкретную версию (defense-in-depth)."""
    resp = api_client.get("/api/v1/healthz")

    server = resp.headers.get("Server", "").lower()

    assert "uvicorn/" not in server, (
        f"Server header раскрывает версию: {server!r}. Скрыть в production-конфиге."
    )
