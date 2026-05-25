"""Audit-log: запись и выборка событий безопасности и операций."""
from __future__ import annotations

import logging
from datetime import datetime
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog

logger = logging.getLogger(__name__)


def log_event(
    db: Session,
    *,
    event_type: str,
    actor_type: str,
    organizer_id: int | None = None,
    user_id: int | None = None,
    actor_display: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    payload: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Пишет запись в audit_log. Никогда не выбрасывает."""
    try:
        entry = AuditLog(
            event_type=event_type,
            actor_type=actor_type,
            organizer_id=organizer_id,
            user_id=user_id,
            actor_display=actor_display,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(entry)
        db.flush()
    except Exception:
        logger.exception("audit log write failed for event_type=%s", event_type)


def query_audit_logs(
    session: Session,
    *,
    page: int = 1,
    per_page: int = 50,
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[AuditLog], int]:
    """Пагинированная выборка audit_log с фильтрами."""
    per_page = min(max(per_page, 1), 200)
    page = max(page, 1)

    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)

    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
        count_stmt = count_stmt.where(AuditLog.event_type == event_type)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
        count_stmt = count_stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
        count_stmt = count_stmt.where(AuditLog.entity_id == entity_id)
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)
        count_stmt = count_stmt.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)
        count_stmt = count_stmt.where(AuditLog.created_at <= date_to)

    total = session.scalar(count_stmt) or 0
    offset = (page - 1) * per_page
    items = list(
        session.scalars(
            stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(per_page)
        )
    )
    return items, total


def audit_pages(total: int, per_page: int) -> int:
    """Число страниц для пагинации."""
    if total <= 0:
        return 0
    return ceil(total / per_page)
