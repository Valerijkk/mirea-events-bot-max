"""Прямой доступ к БД SUT для API-тестов (seed регистраций, mute-флаги).

Black-box REST не умеет sign_up/cancel — только GET списка. Для edge-cases
создаём записи через ORM, проверяем поведение через httpx.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.models import Registration, RegStatus
from app.services.registration import sign_up, upsert_user
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def sut_database_url() -> str:
    project_root = Path(__file__).resolve().parents[2]
    default = f"sqlite:///{project_root / 'data' / 'mirea-events.db'}"
    return os.environ.get("DATABASE_URL", default)


@contextmanager
def sut_session() -> Iterator[Session]:
    engine = create_engine(sut_database_url(), future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


def seed_user(
    session: Session,
    user_id: int,
    *,
    name: str | None = None,
    notifications_enabled: bool = True,
) -> None:
    user = upsert_user(
        session,
        max_user_id=user_id,
        chat_id=user_id,
        name=name or f"U{user_id}",
    )
    user.notifications_enabled = notifications_enabled
    session.flush()


def seed_signup(session: Session, event_id: int, user_id: int) -> Registration:
    result = sign_up(session, event_id=event_id, user_id=user_id)
    session.flush()
    return result.registration


def registration_by_user(session: Session, event_id: int, user_id: int) -> Registration | None:
    return session.scalar(
        select(Registration).where(
            Registration.event_id == event_id,
            Registration.user_id == user_id,
        )
    )


def set_registration_notifications(session: Session, reg_id: int, enabled: bool) -> None:
    reg = session.get(Registration, reg_id)
    if reg is None:
        raise ValueError(f"registration {reg_id} not found")
    reg.notifications_enabled = enabled
    session.flush()


def set_registration_status(session: Session, reg_id: int, status: str) -> None:
    reg = session.get(Registration, reg_id)
    if reg is None:
        raise ValueError(f"registration {reg_id} not found")
    reg.status = status
    session.flush()


def confirmed_count(session: Session, event_id: int) -> int:
    return session.query(Registration).filter(
        Registration.event_id == event_id,
        Registration.status == RegStatus.CONFIRMED,
    ).count()
