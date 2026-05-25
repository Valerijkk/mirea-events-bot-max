"""Схемы REST API для audit-log."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor_type: str
    organizer_id: int | None = None
    user_id: int | None = None
    actor_display: str | None = None
    event_type: str
    entity_type: str | None = None
    entity_id: int | None = None
    payload: dict | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class AuditLogPage(BaseModel):
    items: list[AuditLogItem]
    total: int
    page: int
    per_page: int = Field(..., description="Размер страницы (макс. 200).")
    pages: int
