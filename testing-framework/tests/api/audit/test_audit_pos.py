"""Positive + security: GET /api/v1/audit-logs."""
from __future__ import annotations

import pytest

from config.urls import path_audit_logs
from core.api_client import ApiClient


@pytest.mark.api
@pytest.mark.security
def test_audit_log_endpoint_requires_admin(
    api_as_organizer: ApiClient,
    api_as_admin: ApiClient,
) -> None:
    """TC-API-AUDIT-001: GET /api/v1/audit-logs возвращает 403 для organizer, 200 для admin."""
    org_resp = api_as_organizer.get(path_audit_logs())
    assert org_resp.status_code == 403, f"Ожидали 403, получили {org_resp.status_code}: {org_resp.text}"

    admin_resp = api_as_admin.get(path_audit_logs())
    assert admin_resp.status_code == 200, f"Ожидали 200, получили {admin_resp.status_code}: {admin_resp.text}"


@pytest.mark.api
@pytest.mark.smoke
def test_audit_log_response_schema(api_as_admin: ApiClient) -> None:
    """TC-API-AUDIT-002: GET /api/v1/audit-logs возвращает корректную схему AuditLogPage."""
    resp = api_as_admin.get(path_audit_logs())

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    for field in ("items", "total", "page", "per_page", "pages"):
        assert field in body

    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)
    assert isinstance(body["page"], int)
    assert isinstance(body["per_page"], int)
    assert isinstance(body["pages"], int)
