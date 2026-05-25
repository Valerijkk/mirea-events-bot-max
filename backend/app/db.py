"""SQLAlchemy engine, фабрика сессий и базовый класс ORM-моделей.

В приложении две схемы работы с БД:

* `session_scope()` — контекст-менеджер для воркеров и сервисов: открывает
  сессию, коммитит при выходе, откатывает при исключении.
* `get_session()` — FastAPI-зависимость: даёт «голую» сессию без auto-commit
  (это делает сам обработчик после успешной операции).
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


def _ensure_sqlite_dir(database_url: str) -> None:
    """Для SQLite создаём папку с файлом БД заранее — иначе движок упадёт."""
    if not database_url.startswith("sqlite"):
        return
    # sqlite:///./relative  → path_part = "./relative"
    # sqlite:////abs/path   → path_part = "/abs/path"
    # lstrip("./ ") сломало бы абсолютные пути (стрипало ведущий /), поэтому
    # используем простой срез по длине префикса.
    path_part = database_url[len("sqlite:///"):]
    Path(path_part).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

# check_same_thread=False — SQLite по умолчанию не пускает межпотоковые
# обращения, но FastAPI крутит обработчики в worker-потоках. Для Postgres
# флаг не нужен и игнорируется.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Корневой класс для всех ORM-моделей."""


@contextmanager
def session_scope() -> Iterator[Session]:
    """Контекстная сессия с auto-commit/auto-rollback.

    Используется в фоновых воркерах (планировщик, рассылки, хендлеры бота),
    где обработчик не хочет явно дёргать commit на каждой ветке.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: одна сессия на запрос, явный commit в обработчике."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
