"""Утилиты времени для тестов: безопасное «завтра/через час», подсчёты слотов.

Все функции возвращают **naive** datetime (без tz), потому что SUT работает
в naive UTC — `Event.starts_at` хранится как DATETIME без timezone-info.
Если когда-то перейдём на timezone-aware — поменяем только здесь.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def in_minutes(minutes: int, *, base: datetime | None = None) -> datetime:
    """Метка времени через `minutes` минут от base (или now)."""
    return (base or datetime.utcnow()) + timedelta(minutes=minutes)


def in_hours(hours: int, *, base: datetime | None = None) -> datetime:
    return (base or datetime.utcnow()) + timedelta(hours=hours)


def in_days(days: int, *, base: datetime | None = None) -> datetime:
    return (base or datetime.utcnow()) + timedelta(days=days)


def tomorrow_at(hour: int, minute: int = 0, *, base: datetime | None = None) -> datetime:
    """Конкретное время завтрашнего дня — для предсказуемых нагрузочных тестов."""
    base_day = (base or datetime.utcnow()) + timedelta(days=1)
    return base_day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def split_into_slots(
    starts_at: datetime,
    duration_minutes: int,
    *,
    slot_minutes: int,
) -> list[tuple[datetime, datetime]]:
    """Разрезать диапазон мероприятия на слоты по slot_minutes минут.

    Используется в тестах слотовой записи — там, где нужно сгенерировать
    несколько подряд идущих слотов и проверить, что система не позволяет
    записаться в перекрывающиеся.
    """
    assert slot_minutes > 0, "slot_minutes должен быть > 0"
    assert duration_minutes > 0, "duration_minutes должен быть > 0"
    result: list[tuple[datetime, datetime]] = []
    cursor = starts_at
    end_of_event = starts_at + timedelta(minutes=duration_minutes)
    while cursor < end_of_event:
        slot_end = min(cursor + timedelta(minutes=slot_minutes), end_of_event)
        result.append((cursor, slot_end))
        cursor = slot_end
    return result


def iso(dt: datetime) -> str:
    """Безопасная сериализация в ISO для отправки в JSON-body."""
    return dt.replace(microsecond=0).isoformat()
