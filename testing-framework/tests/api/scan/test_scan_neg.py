"""Negative: POST /api/v1/scan."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from config.urls import path_event_registrations, path_scan
from core.api_client import ApiClient
from utils.test_helpers import find_confirmed_registration_code


def test_scan_nonexistent_returns_not_found(api_as_admin: ApiClient) -> None:
    resp = api_as_admin.post_json(path_scan(), json={"qr_token": "RG-NOPE123"})

    # не 404, а 200 с status=not_found (oracle-mitigation против
    # перебора чужих кодов: разница ответов «не существует» vs «не твой»
    # позволила бы атакующему сузить пространство кодов).
    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert resp.json()["status"] == "not_found"


@pytest.mark.parametrize(
    "token",
    ["", "abc", "1234567"],
    ids=["empty", "too-short-3", "too-short-7"],
)
def test_scan_short_token_returns_422(api_as_admin: ApiClient, token: str) -> None:
    resp = api_as_admin.post_json(path_scan(), json={"qr_token": token})

    assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"


def test_scan_without_token_returns_401(api_client: ApiClient) -> None:
    resp = api_client.post_json(path_scan(), json={"qr_token": "RG-XXXXXX"})

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


def _sut_database_url() -> str:
    project_root = Path(__file__).resolve().parents[4]
    default = f"sqlite:///{project_root / 'data' / 'mirea-events.db'}"
    return os.environ.get("DATABASE_URL", default)


def _mute_registration_by_code(code: str) -> None:
    from app.models import Registration

    engine = create_engine(_sut_database_url(), future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        reg_id = session.scalar(
            select(Registration.id).where(Registration.code == code.upper())
        )
        if reg_id is None:
            pytest.skip(f"Регистрация {code} не найдена в БД SUT.")
        session.execute(
            update(Registration)
            .where(Registration.id == reg_id)
            .values(notifications_enabled=False)
        )
        session.commit()
    engine.dispose()


def test_scan_does_not_notify_user_with_per_event_notifications_muted(
    api_as_organizer: ApiClient,
) -> None:
    """TC-API-SCAN-005: muted reg — scan ok, attended зафиксирован (бот не проверяем)."""
    event_id, code = find_confirmed_registration_code(api_as_organizer)

    _mute_registration_by_code(code)

    resp = api_as_organizer.post_json(path_scan(), json={"qr_token": code})

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == "ok"

    regs = api_as_organizer.get(
        path_event_registrations(event_id),
        params={"status": "attended"},
    ).json()
    assert any(str(r.get("code")) == code for r in regs)
