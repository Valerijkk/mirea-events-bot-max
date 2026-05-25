"""Positive: POST /api/v1/scan (используем seed-RG-коды)."""
from __future__ import annotations

from config.urls import path_scan
from core.api_client import ApiClient
from utils.test_helpers import find_confirmed_registration_code


def test_scan_valid_code_ok_then_already_attended(api_as_admin: ApiClient) -> None:
    _event_id, code = find_confirmed_registration_code(api_as_admin)

    first = api_as_admin.post_json(path_scan(), json={"qr_token": code})

    assert first.status_code == 200, f"Ожидали 200, получили {first.status_code}: {first.text}"
    assert first.json()["status"] in ("ok", "already_attended")

    second = api_as_admin.post_json(path_scan(), json={"qr_token": code})

    # already_attended (после первого скана повторный возвращает «уже был»)
    assert second.status_code == 200, f"Ожидали 200, получили {second.status_code}: {second.text}"
    assert second.json()["status"] == "already_attended"
