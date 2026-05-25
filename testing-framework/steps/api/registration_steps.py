"""API-шаги работы с регистрациями (read-only — создаются ботом MAX)."""
from __future__ import annotations

from typing import Any

from config.urls import path_event_registrations
from core.api_client import ApiClient
from core.exceptions import ApiError
from utils.allure_helpers import attach_json, step


def list_registrations(api: ApiClient, event_id: int, **params: Any) -> list[dict[str, Any]]:
    with step(f"GET {path_event_registrations(event_id)} → список регистраций"):
        resp = api.get(path_event_registrations(event_id), params=params)
        if resp.status_code != 200:
            raise ApiError(resp, f"list regs {event_id} → {resp.status_code}")
        data = resp.json()
        attach_json({"count": len(data) if isinstance(data, list) else "?"}, name="meta")
        return data


def find_by_code(api: ApiClient, event_id: int, code: str) -> dict[str, Any] | None:
    with step(f"Поиск регистрации по коду {code!r} среди event_id={event_id}"):
        for reg in list_registrations(api, event_id):
            if reg.get("code") == code:
                return reg
        return None
