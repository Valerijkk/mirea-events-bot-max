"""PUT /api/v1/events/{id} — проверка контракта REST API.

mirea-events-bot использует PATCH для частичных правок. PUT не объявлен
в роутере, поэтому ожидаем 405 Method Not Allowed. Это документирует
контракт API и гарантирует, что случайный PUT не будет принят как PATCH.

Требование заказчика — иметь тесты на PUT-метод. Здесь — negative-тест:
проверяем что endpoint корректно отказывает.
"""
from __future__ import annotations

import pytest

from config.urls import path_event, path_events
from core.api_client import ApiClient


@pytest.mark.regression
@pytest.mark.neg
def test_put_on_event_returns_method_not_allowed(
    api_as_organizer: ApiClient,
    clean_event: dict,
) -> None:
    """PUT не объявлен — должен вернуть 405."""
    resp = api_as_organizer.put_json(
        path_event(clean_event["id"]),
        json={"title": "PUT попытка"},
    )

    assert resp.status_code == 405, f"Ожидали 405, получили {resp.status_code}: {resp.text}"


@pytest.mark.regression
@pytest.mark.neg
def test_put_on_events_collection_returns_method_not_allowed(
    api_as_organizer: ApiClient,
) -> None:
    """PUT /events (без id) тоже должен быть 405."""
    resp = api_as_organizer.put_json(path_events(), json={})

    assert resp.status_code == 405, f"Ожидали 405, получили {resp.status_code}: {resp.text}"


@pytest.mark.regression
def test_patch_is_supported_for_partial_update(
    api_as_organizer: ApiClient,
    clean_event: dict,
) -> None:
    """Контр-проверка: PATCH — это идиоматический способ обновления в этом API."""
    resp = api_as_organizer.patch_json(
        path_event(clean_event["id"]),
        json={"capacity": 200},
    )

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert resp.json()["capacity"] == 200


@pytest.mark.regression
@pytest.mark.neg
def test_put_on_auth_login_returns_method_not_allowed(
    api_client: ApiClient,
) -> None:
    """POST /auth/login существует, PUT — нет."""
    resp = api_client.put_json(
        "/api/v1/auth/login",
        json={"email": "x", "password": "y"},
    )

    assert resp.status_code == 405, f"Ожидали 405, получили {resp.status_code}: {resp.text}"


@pytest.mark.regression
@pytest.mark.neg
def test_put_on_healthz_returns_method_not_allowed(
    api_client: ApiClient,
) -> None:
    """GET /healthz существует, PUT — нет."""
    resp = api_client.put_json("/api/v1/healthz")

    assert resp.status_code == 405, f"Ожидали 405, получили {resp.status_code}: {resp.text}"
