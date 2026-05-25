"""Общая инфраструктура для unit-тестов: in-memory SQLite, фабрики моделей."""
from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

# backend/ нужен в sys.path, чтобы `from app...` работал после
# переноса тестов в testing-framework/tests/unit/.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Подсовываем минимально необходимые переменные окружения ДО импорта app.config,
# чтобы Pydantic Settings не упал при загрузке. Реальный BOT_TOKEN не нужен —
# мы не дёргаем maxapi в тестах сервисов.
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("BOT_USERNAME", "test_bot")
os.environ.setdefault("JWT_SECRET", "test-secret-for-jwt-must-be-long-enough")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models  # noqa: F401 — регистрируем модели в Base.metadata
from app.db import Base
from app.models import Event, EventStatus, EventType, Organizer


@pytest.fixture
def session() -> Iterator[Session]:
    """Свежая SQLite-БД в памяти на каждый тест."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    sess = SessionLocal()
    try:
        yield sess
    finally:
        sess.close()
        engine.dispose()


@pytest.fixture
def organizer(session: Session) -> Organizer:
    """Заранее созданный организатор — для FK-связей."""
    org = Organizer(
        email="test@mirea.ru",
        password_hash="not-a-real-hash",
        name="Тестовый организатор",
        role="admin",
    )
    session.add(org)
    session.commit()
    return org


@pytest.fixture
def event_factory(session: Session, organizer: Organizer):
    """Фабрика published-мероприятий с заданным capacity."""

    def _make(
        capacity: int = 10,
        *,
        status: str = EventStatus.PUBLISHED,
        starts_at_offset_hours: float | None = None,
    ) -> Event:
        starts = datetime.utcnow() + (
            timedelta(hours=starts_at_offset_hours)
            if starts_at_offset_hours is not None
            else timedelta(days=7)
        )
        ev = Event(
            title="Тестовое мероприятие",
            description="—",
            event_type=EventType.OTHER,
            starts_at=starts,
            location="ауд. 101",
            capacity=capacity,
            organizer_id=organizer.id,
            status=status,
        )
        session.add(ev)
        session.commit()
        return ev

    return _make


@pytest.fixture
def make_users(session: Session):
    """Фабрика пользователей: `make_users([101, 102])` → юзеры с chat_id=max_user_id."""
    from app.services.registration import upsert_user

    def _make(user_ids: list[int], *, notifications_enabled: bool = True) -> None:
        for uid in user_ids:
            user = upsert_user(session, max_user_id=uid, chat_id=uid, name=f"U{uid}")
            user.notifications_enabled = notifications_enabled
        session.flush()

    return _make
