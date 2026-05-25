"""REST API audit-log — только для role=admin."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import AdminOrganizer, DbSession
from app.schemas.audit import AuditLogItem, AuditLogPage
from app.schemas.common import ErrorResponse
from app.services.audit import audit_pages, query_audit_logs

router = APIRouter(tags=["audit"])


@router.get(
    "/audit-logs",
    summary="Журнал аудита",
    description="Список записей audit_log с фильтрами. Доступно только admin.",
    response_model=AuditLogPage,
    responses={
        403: {"description": "Нужна роль admin", "model": ErrorResponse},
    },
)
def list_audit_logs(
    organizer: AdminOrganizer,
    session: DbSession,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditLogPage:
    items, total = query_audit_logs(
        session,
        page=page,
        per_page=per_page,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
    )
    return AuditLogPage(
        items=[AuditLogItem.model_validate(row) for row in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=audit_pages(total, per_page),
    )
