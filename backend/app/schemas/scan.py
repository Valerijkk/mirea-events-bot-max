"""Схемы для сканера QR-кодов на входе."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    """Запрос на отметку посещения по QR."""

    qr_token: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Значение, считанное со QR-кода (поле `qr_token` из таблицы регистраций).",
        examples=["8f4a1c9d2e3b4f5a6c7d8e9f0a1b2c3d"],
    )


class ScanResponse(BaseModel):
    """Ответ на сканирование.

    `status` — машиночитаемый код результата для UI-логики:
    * `ok` — посещение только что зафиксировано;
    * `already_attended` — повторное сканирование уже посетившего (UX: amber);
    * `cancelled` — запись отменена (пользователем / организатором / поздно);
    * `not_found` — qr_token или code не существуют.

    Поля `user_name`, `event_title`, `attended_at` заполняются и для
    `already_attended` — организатору важно увидеть «кого именно».
    """

    ok: bool = Field(..., description="True — посещение зафиксировано прямо сейчас.")
    status: str = Field(
        "ok",
        description="Машиночитаемый код: ok / already_attended / cancelled / not_found.",
    )
    user_name: str | None = Field(None, description="Имя посетителя (если запись найдена).")
    event_title: str | None = Field(None, description="Название мероприятия (если запись найдена).")
    attended_at: str | None = Field(None, description="Время первого сканирования — для already_attended.")
    error: str | None = Field(None, description="Человекочитаемая причина для UI.")
