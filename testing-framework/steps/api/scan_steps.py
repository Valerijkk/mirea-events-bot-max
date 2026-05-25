"""API-шаги для сканера."""
from __future__ import annotations

from typing import Any

from config.urls import path_scan
from core.api_client import ApiClient


def scan_token(api: ApiClient, qr_token: str) -> dict[str, Any]:
    # Сырое тело — статус ответа интерпретирует вызывающий тест (pos/neg).
    resp = api.post_json(path_scan(), json={"qr_token": qr_token})
    body = resp.json() if resp.content else {}
    body["_status_code"] = resp.status_code
    return body
