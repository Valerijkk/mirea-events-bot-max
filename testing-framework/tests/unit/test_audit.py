"""Unit-тесты audit-log: log_event, query_audit_logs."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import AuditActorType, AuditEvent, AuditLog
from app.services.audit import log_event, query_audit_logs


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    AuditLog.__table__.create(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.mark.unit
@pytest.mark.pos
def test_log_event_creates_db_record(db: Session) -> None:
    """TC-UNIT-AUDIT-001: log_event записывает строку в audit_log."""
    log_event(
        db,
        event_type=AuditEvent.ADMIN_LOGIN,
        actor_type=AuditActorType.ADMIN,
    )

    assert db.query(AuditLog).count() == 1


@pytest.mark.unit
@pytest.mark.neg
def test_log_event_swallows_db_error(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-UNIT-AUDIT-002: log_event не выбрасывает при сбое БД."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise Exception("db error")

    monkeypatch.setattr(db, "flush", _boom)

    log_event(
        db,
        event_type=AuditEvent.ADMIN_LOGIN,
        actor_type=AuditActorType.ADMIN,
    )


@pytest.mark.unit
@pytest.mark.pos
def test_query_audit_logs_filters_by_event_type(db: Session) -> None:
    """TC-UNIT-AUDIT-003: query_audit_logs возвращает только записи с указанным event_type."""
    log_event(db, event_type=AuditEvent.ADMIN_LOGIN, actor_type=AuditActorType.ADMIN)
    log_event(db, event_type=AuditEvent.EVENT_CREATED, actor_type=AuditActorType.ADMIN)

    items, total = query_audit_logs(db, event_type=AuditEvent.ADMIN_LOGIN)

    assert total == 1
    assert len(items) == 1
    assert items[0].event_type == AuditEvent.ADMIN_LOGIN


@pytest.mark.unit
@pytest.mark.pos
def test_query_audit_logs_pagination(db: Session) -> None:
    """TC-UNIT-AUDIT-004: query_audit_logs корректно пагинирует результаты."""
    for i in range(5):
        log_event(
            db,
            event_type=AuditEvent.ADMIN_LOGIN,
            actor_type=AuditActorType.ADMIN,
            actor_display=f"admin-{i}",
        )

    items, total = query_audit_logs(db, page=2, per_page=2)

    assert total == 5
    assert len(items) == 2
