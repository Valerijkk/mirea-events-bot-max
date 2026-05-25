"""API-шаги CRUD мероприятий. Каждый шаг — отдельный allure.step для читаемого отчёта."""
from __future__ import annotations

from typing import Any

from config.urls import path_event, path_event_status, path_events
from core.api_client import ApiClient
from core.exceptions import ApiError
from utils.allure_helpers import attach_json, step


def create_event(api: ApiClient, payload: dict[str, Any]) -> dict[str, Any]:
    with step(f"POST {path_events()} → создать мероприятие «{payload.get('title', '?')}»"):
        attach_json(payload, name="payload")
        resp = api.post_json(path_events(), json=payload)
        if resp.status_code != 201:
            raise ApiError(resp, f"create event → {resp.status_code}")
        data = resp.json()
        attach_json(data, name="response")
        return data


def get_event(api: ApiClient, event_id: int) -> dict[str, Any]:
    with step(f"GET {path_event(event_id)} → прочитать мероприятие"):
        resp = api.get(path_event(event_id))
        if resp.status_code != 200:
            raise ApiError(resp, f"get event {event_id} → {resp.status_code}")
        data = resp.json()
        attach_json(data, name="event")
        return data


def patch_event(api: ApiClient, event_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    with step(f"PATCH {path_event(event_id)} → частичное обновление"):
        attach_json(payload, name="payload")
        resp = api.patch_json(path_event(event_id), json=payload)
        if resp.status_code != 200:
            raise ApiError(resp, f"patch event {event_id} → {resp.status_code}")
        data = resp.json()
        attach_json(data, name="response")
        return data


def change_status(api: ApiClient, event_id: int, status: str) -> dict[str, Any]:
    with step(f"POST {path_event_status(event_id)} → перевести статус в «{status}»"):
        resp = api.post_json(path_event_status(event_id), json={"status": status})
        if resp.status_code != 200:
            raise ApiError(resp, f"status {event_id}→{status}: {resp.status_code}")
        data = resp.json()
        attach_json(data, name="response")
        return data


def delete_event(api: ApiClient, event_id: int) -> None:
    with step(f"DELETE {path_event(event_id)} → удалить мероприятие"):
        resp = api.delete(path_event(event_id))
        if resp.status_code not in (200, 204, 404):
            # 404 при teardown — нормально (тест мог сам удалить).
            raise ApiError(resp, f"delete event {event_id} → {resp.status_code}")


def list_events(api: ApiClient, **params: Any) -> list[dict[str, Any]]:
    with step(f"GET {path_events()} → список мероприятий"):
        resp = api.get(path_events(), params=params)
        if resp.status_code != 200:
            raise ApiError(resp, f"list events → {resp.status_code}")
        data = resp.json()
        attach_json({"count": len(data) if isinstance(data, list) else "?"}, name="meta")
        return data
