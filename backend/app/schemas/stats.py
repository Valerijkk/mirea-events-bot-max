"""Схемы для статистики (виджеты дашборда)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EventStats(BaseModel):
    """Сводка по одному мероприятию."""

    event_id: int
    confirmed: int = Field(..., description="Сколько участников подтвердили запись.")
    waitlist: int = Field(..., description="Сколько участников ждут в очереди.")
    cancelled: int = Field(..., description="Сколько отменивших запись.")
    attended: int = Field(..., description="Сколько по факту пришли (отсканировали QR).")
    capacity: int = Field(..., description="Лимит мест.")
    fill_rate: float = Field(..., description="Процент заполнения (confirmed / capacity), 0..1.", ge=0, le=1)
    attendance_rate: float | None = Field(
        None,
        ge=0,
        le=1,
        description="Процент явки (attended / confirmed). None — пока мероприятие не прошло.",
    )


class GlobalStats(BaseModel):
    """Сводка по всему сервису (для главного экрана дашборда)."""

    total_users: int = Field(..., description="Всего пользователей, хотя бы раз открывших бота.")
    total_events: int = Field(..., description="Всего мероприятий в системе.")
    published_events: int = Field(..., description="Сейчас опубликовано.")
    total_registrations: int = Field(..., description="Всего записей за всё время.")
    active_registrations: int = Field(..., description="Сейчас активных (confirmed + waitlist).")
    attended_total: int = Field(..., description="Сколько посещений зафиксировано.")
