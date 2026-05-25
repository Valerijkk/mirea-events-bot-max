"""Схемы для рассылок организатора."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SegmentLiteral = Literal["all", "confirmed", "waitlist", "attended", "no_show"]


class BroadcastRequest(BaseModel):
    """Параметры для запуска рассылки."""

    segment: SegmentLiteral = Field(
        "confirmed",
        description=(
            "Сегмент получателей: confirmed — только подтверждённые; "
            "waitlist — лист ожидания; all — confirmed + waitlist; "
            "attended — посетившие; no_show — не явившиеся."
        ),
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Текст сообщения. Может содержать перенос строк и базовый Markdown.",
        examples=["Внимание! Аудитория переносится в 405."],
    )


class BroadcastRead(BaseModel):
    """Информация об уже созданной рассылке."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    organizer_id: int | None
    segment: SegmentLiteral
    message_text: str
    sent_at: datetime | None = Field(None, description="Время фактической отправки. None — отправка ещё не завершилась.")
    delivered_count: int = Field(..., description="Сколько сообщений успешно ушло.")
    failed_count: int = Field(..., description="Сколько сообщений не доставили (бот не может писать пользователю, заблокирован и т.п.).")
    created_at: datetime


class BroadcastResult(BaseModel):
    """Итог немедленной рассылки."""

    broadcast: BroadcastRead = Field(..., description="Только что созданная рассылка с финальными счётчиками.")
