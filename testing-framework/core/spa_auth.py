"""Инъекция JWT в React SPA (zustand persist → localStorage)."""
from __future__ import annotations

import json
from typing import Any

import jwt
from playwright.sync_api import BrowserContext

from core.api_client import ApiClient

AUTH_STORAGE_KEY = "mirea-auth"


def _jwt_sub(token: str) -> int:
    payload = jwt.decode(token, options={"verify_signature": False})
    return int(payload["sub"])


def resolve_organizer(client: ApiClient, email: str, *, role: str) -> dict[str, Any]:
    """Минимальный профиль организатора для zustand — как в frontend loginRequest."""
    if role == "admin":
        resp = client.get("/api/v1/organizers")
        if resp.status_code == 200:
            for org in resp.json():
                if org.get("email") == email:
                    return org

    return {
        "id": _jwt_sub(client.token or ""),
        "email": email,
        "name": email,
        "role": role,
        "department": None,
        "created_at": None,
    }


def persisted_state_json(token: str, organizer: dict[str, Any]) -> str:
    return json.dumps({"state": {"token": token, "organizer": organizer}, "version": 0})


def inject_spa_auth(context: BrowserContext, token: str, organizer: dict[str, Any]) -> None:
    """add_init_script — state попадает в localStorage до первого goto.

    ВАЖНО: скрипт должен быть IIFE, а не просто определением функции.
    Playwright выполняет строку как JS, поэтому `() => {...}` создаёт функцию
    но не вызывает её. Нужно `(() => {...})()`.
    """
    payload = persisted_state_json(token, organizer)
    key_json = json.dumps(AUTH_STORAGE_KEY)
    value_json = json.dumps(payload)
    context.add_init_script(
        f"(() => {{ localStorage.setItem({key_json}, {value_json}); }})()"
    )
