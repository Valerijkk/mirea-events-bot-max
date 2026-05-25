"""PII-leak проверки: никакие публичные/неавторизованные эндпоинты не
должны возвращать phone/email пользователя в открытом виде.
"""
from __future__ import annotations

import pytest

from core.api_client import ApiClient
from steps.api.event_steps import list_events
from utils.allure_helpers import step
from utils.assertions import assert_no_secret_leak

pytestmark = [pytest.mark.api, pytest.mark.neg]


# Известные phone-форматы из init_project (если что-то такое появится в ответе —
# это PII-утечка): русский +7..., с/без скобок.
_PHONE_PATTERNS = ["+7900", "+7 (900", "+7(900", "8900"]


def test_public_catalog_has_no_phone_numbers(
    api_as_admin: ApiClient,
    imported_mirea_events: list[dict],
) -> None:
    """В каталоге событий не должно быть никаких телефонов абитуриентов."""
    with step("GET /api/v1/events?limit=100"):
        events = list_events(api_as_admin, limit=100)

    body = str(events).lower()
    leaks = [p for p in _PHONE_PATTERNS if p in body]

    assert not leaks, f"в каталоге событий утекли телефонные номера: {leaks}"


def test_healthz_returns_no_secrets(api_client: ApiClient) -> None:
    """В healthz нет ключей/токенов — это публичный endpoint."""
    resp = api_client.get("/api/v1/healthz")

    assert_no_secret_leak(resp, ["JWT_SECRET", "BOT_TOKEN", "password", "secret"])
