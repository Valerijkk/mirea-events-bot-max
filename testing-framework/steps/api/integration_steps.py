"""API-шаги для /api/v1/integration/*."""
from __future__ import annotations

from typing import Any

from config.urls import path_integration_health, path_integration_sync
from core.api_client import ApiClient
from core.exceptions import ApiError
from utils.allure_helpers import attach_json, step


def sync_events(
    api: ApiClient,
    events: list[dict[str, Any]],
    auto_publish: bool | None = None,
) -> dict[str, Any]:
    with step(f"POST {path_integration_sync()} → bulk-импорт {len(events)} событий"):
        payload: dict[str, Any] = {"events": events}
        if auto_publish is not None:
            payload["auto_publish"] = auto_publish
        attach_json(payload, name="batch")
        resp = api.post_json(path_integration_sync(), json=payload)
        if resp.status_code not in (200, 201):
            raise ApiError(resp, f"sync → {resp.status_code}")
        data = resp.json()
        attach_json(data, name="response")
        return data


def integration_health(api: ApiClient) -> dict[str, Any]:
    with step(f"GET {path_integration_health()} → проверка ключа интеграции"):
        resp = api.get(path_integration_health())
        if resp.status_code != 200:
            raise ApiError(resp, f"integration health → {resp.status_code}")
        return resp.json()
