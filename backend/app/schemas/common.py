"""Общие схемы — ответы об ошибках и подтверждения."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Стандартный ответ об ошибке (4xx/5xx)."""

    detail: str = Field(..., description="Человекочитаемое описание ошибки.", examples=["Мероприятие не найдено"])


class MessageResponse(BaseModel):
    """Ответ операций без полезной нагрузки — только статус успеха."""

    ok: bool = Field(True, description="Признак успешного выполнения операции.")
    message: str | None = Field(None, description="Опциональное человекочитаемое сообщение.")
