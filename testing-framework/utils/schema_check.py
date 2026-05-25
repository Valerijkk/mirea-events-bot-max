"""Лёгкая проверка JSON-структуры без внешних зависимостей.

Зачем не jsonschema: один модуль, один импорт, никаких version-pin'ов.
Для нашего пресета (типы + required-ключи) хватает за глаза. Если нужна
полная OpenAPI-валидация — берётся pydantic-моделью SUT напрямую.
"""
from __future__ import annotations

from typing import Any


def check_keys(obj: dict[str, Any], required: list[str]) -> None:
    """Бросит AssertionError если каких-то ключей нет."""
    missing = [k for k in required if k not in obj]
    assert not missing, f"в объекте нет ключей: {missing}. Есть: {sorted(obj.keys())}"


def check_types(obj: dict[str, Any], spec: dict[str, type]) -> None:
    """Каждое поле obj[key] — экземпляр spec[key] (или None, если поле опционально)."""
    errors: list[str] = []
    for key, expected_type in spec.items():
        if key not in obj:
            continue
        value = obj[key]
        if value is None:
            continue
        if not isinstance(value, expected_type):
            errors.append(
                f"{key}: ожидался {expected_type.__name__}, "
                f"пришёл {type(value).__name__} = {value!r}"
            )
    assert not errors, "ошибки типов:\n  " + "\n  ".join(errors)


def check_enum(value: Any, allowed: list[Any], *, label: str = "value") -> None:
    """Проверка что value входит в перечисление."""
    assert value in allowed, f"{label}={value!r} не входит в допустимые: {allowed}"


def check_event_response(event: dict[str, Any]) -> None:
    """Контракт ответа GET /api/v1/events/{id} — все обязательные поля и типы."""
    check_keys(event, [
        "id", "title", "starts_at", "event_type", "status", "format", "capacity",
    ])
    check_types(event, {
        "id": int,
        "title": str,
        "description": str,
        "starts_at": str,
        "ends_at": str,
        "event_type": str,
        "status": str,
        "format": str,
        "capacity": int,
        "duration_minutes": int,
        "location": str,
        "meeting_url": str,
        "max_entries": int,
    })
    check_enum(event["status"], ["draft", "published", "cancelled", "finished"], label="status")
    check_enum(event["format"], ["online", "onsite"], label="format")
    check_enum(
        event["event_type"],
        ["open_day", "masterclass", "olympiad", "tour", "consultation", "other"],
        label="event_type",
    )
