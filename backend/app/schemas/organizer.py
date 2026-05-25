"""Схемы организаторов (admin only)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

OrganizerRoleLiteral = Literal["admin", "organizer"]


class OrganizerRead(BaseModel):
    """Организатор без password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None
    email: str
    role: OrganizerRoleLiteral
    department: str | None
    created_at: datetime


class OrganizerCreate(BaseModel):
    """Создание организатора."""

    name: str | None = None
    email: EmailStr
    password: str = Field(min_length=8)
    role: OrganizerRoleLiteral = "organizer"
    department: str | None = None


class OrganizerUpdate(BaseModel):
    """Частичное обновление организатора."""

    name: str | None = None
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    role: OrganizerRoleLiteral | None = None
    department: str | None = None
