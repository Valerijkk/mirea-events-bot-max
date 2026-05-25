"""Схемы регистраций и пользователей. ТЗ §3 (минимизация PII): через REST НЕ отдаём phone/username — только имя + системные timestamp'ы. Экспорт контактов — отдельный эндпоинт с аудит-логом."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RegStatusLiteral = Literal[
    "confirmed", "waitlist", "cancelled", "late_cancelled",
    "cancelled_by_organizer", "attended", "no_show",
]


class UserRead(BaseModel):
    """Профиль пользователя в ответах API. Сознательно без phone/username — ТЗ §3, минимизация PII."""

    model_config = ConfigDict(from_attributes=True)

    max_user_id: int = Field(..., description="Идентификатор пользователя в MAX.")
    name: str | None = Field(None, description="Имя, как его сообщил MAX. Используется только для списка участников.")
    notifications_enabled: bool = Field(..., description="Глобальный флаг — отписан ли юзер от бота вообще.")
    first_seen: datetime
    last_active: datetime


class RegistrationRead(BaseModel):
    """Запись пользователя на мероприятие."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    user_id: int
    status: RegStatusLiteral = Field(..., description="Состояние записи.")
    code: str = Field(..., description="Человекочитаемый код записи (RG-XXXXXX) для поиска на входе.")
    waitlist_position: int | None = Field(None, description="Позиция в очереди (1-индексированная). Только для статуса waitlist.")
    registered_at: datetime
    cancelled_at: datetime | None
    attended_at: datetime | None
    user: UserRead | None = Field(None, description="Профиль пользователя — только имя и системные метки, без контактных данных.")
