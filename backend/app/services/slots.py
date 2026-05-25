"""Сервис управления слотами мероприятия.

«Слот» — это временное окно у мероприятия с собственной вместимостью.
Пример: «День открытых дверей» с тремя экскурсиями 11:00 / 13:00 / 15:00
по 20 человек в каждой. Тогда `event.capacity` — это «60 всего», но
запись идёт на конкретный слот через `Registration.slot_id`.

Если у мероприятия слотов нет (`event.slots == []`) — запись идёт на
event напрямую (`slot_id IS NULL`), и работает «старый» путь по
`event.capacity` (см. `services/registration.py`).
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EventSlot, RegStatus


def list_slots(session: Session, event_id: int) -> list[EventSlot]:
    """Слоты мероприятия, отсортированные по времени начала."""
    return list(
        session.scalars(
            select(EventSlot)
            .where(EventSlot.event_id == event_id)
            .order_by(EventSlot.starts_at)
        )
    )


def upcoming_slots_with_capacity(
    session: Session, event_id: int
) -> list[tuple[EventSlot, int]]:
    """Будущие слоты + сколько мест осталось у каждого.

    Возвращает пары `(slot, free_count)`. Используется при отрисовке
    клавиатуры выбора слота — слот в прошлом не показываем, рядом со
    слотом без мест ставим пометку.
    """
    now = datetime.now(UTC).replace(tzinfo=None).replace(tzinfo=None)
    slots = list(
        session.scalars(
            select(EventSlot)
            .where(EventSlot.event_id == event_id, EventSlot.starts_at > now)
            .order_by(EventSlot.starts_at)
        )
    )
    # confirmed_count считаем по in-memory `slot.registrations` —
    # SQLAlchemy уже загрузил их через relationship. Для UI с ~10 слотами
    # это дешевле, чем отдельный COUNT(*) на каждый.
    return [
        (
            slot,
            max(
                0,
                slot.capacity
                - sum(1 for r in slot.registrations if r.status == RegStatus.CONFIRMED),
            ),
        )
        for slot in slots
    ]


def create_slot(
    session: Session,
    event_id: int,
    starts_at: datetime,
    capacity: int,
    ends_at: datetime | None = None,
    label: str | None = None,
) -> EventSlot:
    """Создать новый слот у мероприятия."""
    slot = EventSlot(
        event_id=event_id,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=capacity,
        label=label,
    )
    session.add(slot)
    session.flush()
    return slot


def delete_slot(session: Session, slot_id: int, event_id: int | None = None) -> bool:
    """Удалить слот. Записи на нём останутся, но `slot_id` обнулится.

    `event_id` — необязательная защита от IDOR: если передан, удаление
    произойдёт ТОЛЬКО если слот принадлежит этому мероприятию. Это нужно,
    потому что в админ-маршрутах URL содержит и event_id, и slot_id —
    без сверки одного с другим Bob мог бы удалить слот Alice, угадав id.
    """
    slot = session.get(EventSlot, slot_id)
    if slot is None:
        return False
    if event_id is not None and slot.event_id != event_id:
        # Слот существует, но привязан к другому мероприятию — это попытка IDOR.
        return False
    session.delete(slot)
    session.flush()
    return True
