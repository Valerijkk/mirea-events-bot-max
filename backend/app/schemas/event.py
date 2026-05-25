"""Схемы для мероприятий."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EventTypeLiteral = Literal["open_day", "masterclass", "olympiad", "tour", "consultation", "other"]
EventStatusLiteral = Literal["draft", "published", "cancelled", "finished"]
EventFormatLiteral = Literal["online", "onsite"]
LateCancelPolicyLiteral = Literal["disallow", "allow_marked"]


class EventBase(BaseModel):
    """Общие поля мероприятия."""

    title: str = Field(..., min_length=3, max_length=255, description="Название мероприятия.", examples=["День открытых дверей ИИТ"])
    description: str | None = Field(None, description="Подробное описание (поддерживает обычный текст).")
    event_type: EventTypeLiteral = Field("other", description="Тип мероприятия.")
    starts_at: datetime = Field(..., description="Дата и время начала (UTC).", examples=["2026-05-20T10:00:00"])
    ends_at: datetime | None = Field(None, description="Дата и время окончания. Необязательно — по умолчанию +2 часа от начала.")
    location: str | None = Field(None, max_length=255, description="Адрес или аудитория (для очного формата).", examples=["ауд. 301, корп. А, пр. Вернадского, 78"])
    cover_url: str | None = Field(None, max_length=512, description="URL обложки (бот прикрепит как картинку к карточке).")
    capacity: int = Field(..., gt=0, le=10000, description="Максимальное число подтверждённых записей.")
    duration_minutes: int | None = Field(None, ge=1, le=1440, description="Длительность в минутах. Если не задана — посчитаем из ends_at-starts_at.")
    format: EventFormatLiteral = Field("onsite", description="Формат: online (нужна meeting_url) или onsite (нужна location).")
    requirements: str | None = Field(None, description="Требования к участникам (показывается в «Подробнее»).")
    cancellation_terms: str | None = Field(None, description="Условия отмены (показывается в «Подробнее»).")
    meeting_url: str | None = Field(None, max_length=512, description="Ссылка на онлайн-подключение (для format=online).")
    late_cancel_policy: LateCancelPolicyLiteral = Field("disallow", description="Что делать с отменой после начала: запрет или маркер «Поздняя отмена».")
    max_entries: int = Field(1, ge=0, le=100, description="Сколько раз можно использовать пропуск (0 = безлимит, 1 = классический одноразовый, 2+ = N проходов).")


class EventCreate(EventBase):
    """Параметры для создания мероприятия."""


class EventUpdate(BaseModel):
    """Частичное обновление мероприятия. Все поля опциональны."""

    title: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = None
    event_type: EventTypeLiteral | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = Field(None, max_length=255)
    cover_url: str | None = Field(None, max_length=512)
    capacity: int | None = Field(None, gt=0, le=10000)
    duration_minutes: int | None = Field(None, ge=1, le=1440)
    format: EventFormatLiteral | None = None
    requirements: str | None = None
    cancellation_terms: str | None = None
    meeting_url: str | None = Field(None, max_length=512)
    late_cancel_policy: LateCancelPolicyLiteral | None = None
    registration_open: bool | None = None
    max_entries: int | None = Field(None, ge=0, le=100)


class EventStatusUpdate(BaseModel):
    """Смена статуса мероприятия."""

    status: EventStatusLiteral = Field(..., description="Новый статус мероприятия.")


class EventRead(EventBase):
    """Мероприятие в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Внутренний идентификатор мероприятия.")
    status: EventStatusLiteral = Field(..., description="Текущий статус.")
    organizer_id: int | None = Field(None, description="ID организатора, создавшего мероприятие.")
    deeplink_payload: str = Field(..., description="Payload для deeplink в MAX. Полная ссылка собирается в админке.")
    free_slots: int = Field(..., description="Сколько мест свободно прямо сейчас.")
    confirmed_count: int = Field(..., description="Сколько участников подтвердили запись.")
    waitlist_count: int = Field(..., description="Сколько участников в листе ожидания.")
    registration_open: bool = Field(True, description="Открыта ли регистрация (организатор может закрыть вручную).")
    created_at: datetime
    updated_at: datetime
