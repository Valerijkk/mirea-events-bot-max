"""Создание таблиц БД из ORM-моделей + лёгкая миграция новых колонок.

Запуск:
    python -m app.db_init

Безопасно вызывать многократно. Алгоритм:

1. `Base.metadata.create_all` — создаст недостающие таблицы.
2. Для каждой существующей таблицы сравним фактические колонки с теми,
   что описаны в моделях, и для отсутствующих выполним `ALTER TABLE ...
   ADD COLUMN ...`. Это «бедная» миграция — без переименований / изменений
   типов, но её достаточно, чтобы при добавлении новых полей старые
   SQLite-БД не приходилось сносить вручную.

На проде вместо этого используйте Alembic — он умеет идемпотентные
скрипты, откаты, ветки и т.д.
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.types import TypeEngine

from app import models  # noqa: F401 — импорт регистрирует модели в Base.metadata
from app.db import Base, engine


def _sql_type(col_type: TypeEngine, dialect_name: str) -> str:
    """Сериализовать SQLAlchemy-тип в строку DDL для текущего диалекта."""
    return col_type.compile(dialect=engine.dialect)


def _add_missing_columns(eng: Engine) -> list[str]:
    """Для каждой существующей таблицы добавить недостающие колонки.

    Возвращает список применённых ALTER'ов (для лога).
    """
    inspector = inspect(eng)
    applied: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in inspector.get_table_names():
            continue  # таблицы вообще нет → create_all создаст целиком
        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            ddl_type = _sql_type(col.type, eng.dialect.name)
            nullable = "" if col.nullable else " NOT NULL"
            # SQLite не любит DEFAULT с CURRENT_TIMESTAMP при ALTER —
            # обходимся литералами/NULL. Для Python-default'ов ставим NULL,
            # ORM проставит при следующем INSERT.
            default_clause = ""
            # `.arg` есть у DefaultClause/ColumnDefault, но не у их базовых
            # классов FetchedValue / DefaultGenerator — отсюда type ignore.
            if col.server_default is not None:
                default_clause = f" DEFAULT {col.server_default.arg}"  # type: ignore[attr-defined]
            elif col.default is not None and not callable(col.default.arg):  # type: ignore[attr-defined]
                default_clause = f" DEFAULT {col.default.arg!r}"  # type: ignore[attr-defined]
            # NOT NULL без default'а ломает ALTER в SQLite — даём default
            # по типу, чтобы старые строки получили валидное значение.
            if not col.nullable and not default_clause:
                py_default = _default_for_type(col.type)
                default_clause = f" DEFAULT {py_default}"
            stmt = (
                f'ALTER TABLE {table_name} ADD COLUMN {col.name} '
                f'{ddl_type}{default_clause}{nullable}'
            )
            with eng.begin() as conn:
                conn.execute(text(stmt))
            applied.append(stmt)
    return applied


def _default_for_type(col_type: TypeEngine) -> str:
    """Безопасное значение по умолчанию для NOT NULL колонки при миграции."""
    name = col_type.__class__.__name__.lower()
    if "int" in name or "numeric" in name or "float" in name:
        return "0"
    if "bool" in name:
        return "0"
    if "date" in name or "time" in name:
        return "CURRENT_TIMESTAMP"
    return "''"


def init_db() -> None:
    """Создать недостающие таблицы + добавить новые колонки в существующие."""
    Base.metadata.create_all(bind=engine)
    applied = _add_missing_columns(engine)
    if applied:
        print(f"[OK] Применено миграций: {len(applied)}")
        for stmt in applied:
            print(f"  + {stmt}")
    else:
        print("[OK] Таблицы и колонки актуальны")


if __name__ == "__main__":
    init_db()
