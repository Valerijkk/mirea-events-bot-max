"""Схемы временных слотов мероприятия."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SlotRead(BaseModel):
    """Слот мероприятия с агрегатом свободных мест."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    starts_at: datetime
    ends_at: datetime | None
    capacity: int
    label: str | None
    free_slots: int
    created_at: datetime


class SlotCreate(BaseModel):
    """Параметры создания слота."""

    starts_at: datetime
    ends_at: datetime | None = None
    capacity: int = Field(ge=1)
    label: str | None = None
