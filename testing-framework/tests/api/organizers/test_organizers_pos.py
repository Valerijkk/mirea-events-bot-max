"""Positive + security: REST /api/v1/organizers (admin only)."""
from __future__ import annotations

import uuid

import pytest

from config.settings import Settings
from config.urls import path_organizer, path_organizers
from core.api_client import ApiClient


@pytest.mark.api
@pytest.mark.pos
def test_list_organizers_admin_only(
    api_as_organizer: ApiClient,
    api_as_admin: ApiClient,
) -> None:
    """GET /api/v1/organizers доступен только admin."""
    org_resp = api_as_organizer.get(path_organizers())
    assert org_resp.status_code == 403, (
        f"Ожидали 403, получили {org_resp.status_code}: {org_resp.text}"
    )

    admin_resp = api_as_admin.get(path_organizers())
    assert admin_resp.status_code == 200, (
        f"Ожидали 200, получили {admin_resp.status_code}: {admin_resp.text}"
    )

    body = admin_resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1


@pytest.mark.api
@pytest.mark.pos
def test_create_organizer_returns_201(api_as_admin: ApiClient) -> None:
    """POST /api/v1/organizers создаёт нового организатора."""
    payload = {
        "email": f"qa-org-{uuid.uuid4().hex[:8]}@mirea.ru",
        "password": "testpass1234",
        "name": "QA Тестовый Организатор",
        "department": "Кафедра тестирования",
        "role": "organizer",
    }

    resp = api_as_admin.post_json(path_organizers(), json=payload)

    assert resp.status_code == 201, f"Ожидали 201, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body["id"] > 0
    assert body["email"] == payload["email"]
    assert body["role"] == "organizer"
    assert body["name"] == payload["name"]

    cleanup = api_as_admin.delete(path_organizer(body["id"]))
    assert cleanup.status_code == 200, (
        f"Ожидали 200, получили {cleanup.status_code}: {cleanup.text}"
    )


@pytest.mark.api
@pytest.mark.neg
@pytest.mark.security
def test_delete_self_returns_409_or_403(
    api_as_admin: ApiClient,
    settings: Settings,
) -> None:
    """DELETE /api/v1/organizers/{self_id} → 409 или 403."""
    listed = api_as_admin.get(path_organizers())
    assert listed.status_code == 200, f"Ожидали 200, получили {listed.status_code}: {listed.text}"

    admin_row = next(
        (row for row in listed.json() if row["email"] == settings.admin_email),
        None,
    )
    assert admin_row is not None, "admin не найден в GET /api/v1/organizers"

    resp = api_as_admin.delete(path_organizer(admin_row["id"]))

    assert resp.status_code in (403, 409), (
        f"Ожидали 403 или 409, получили {resp.status_code}: {resp.text}"
    )
