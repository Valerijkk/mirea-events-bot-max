"""Схемы для авторизации организаторов."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Тело запроса на вход в API."""

    email: EmailStr = Field(..., description="Email организатора.", examples=["organizer@mirea.ru"])
    password: str = Field(..., min_length=1, description="Пароль организатора.")


class TokenResponse(BaseModel):
    """Ответ с выданным JWT-токеном."""

    access_token: str = Field(..., description="JWT-токен. Подставляйте в заголовок `Authorization: Bearer <token>`.")
    token_type: str = Field("bearer", description="Тип токена.")
    expires_in: int = Field(..., description="Время жизни токена в секундах.")
