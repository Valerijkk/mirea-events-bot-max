"""Авторизация организаторов: JWT в `Authorization: Bearer` (REST).

Legacy-хелперы `AdminLoginRequired` / `current_organizer` (cookie) оставлены
для совместимости со старыми тестами — в проде не используются.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Cookie, Depends
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import Organizer


class AdminLoginRequired(Exception):
    """Legacy: cookie-авторизация HTML-админки (только unit-тесты).

    Намеренно не наследуется от HTTPException — старые тесты ловят это
    исключение напрямую. В проде используется Bearer JWT через REST.
    """

settings = get_settings()

# deprecated="auto" — на будущее тихая миграция на новый алгоритм без ломки старых хешей.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_token(organizer_id: int) -> str:
    """Выпустить JWT для организатора. Срок жизни — `jwt_expire_minutes` из .env."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(organizer_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    """Распарсить JWT и вернуть id организатора. None — если токен невалидный/просроченный."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def authenticate(session: Session, email: str, password: str) -> Organizer | None:
    """Проверить пару email/пароль. None — если что-то не сошлось."""
    organizer = session.scalar(select(Organizer).where(Organizer.email == email))
    if organizer is None:
        return None
    if not verify_password(password, organizer.password_hash):
        return None
    return organizer


def current_organizer(
    token: Annotated[str | None, Cookie(alias="admin_token")] = None,
    session: Session = Depends(get_session),
) -> Organizer:
    """Legacy dependency: достать организатора из cookie (только unit-тесты).

    При любой ошибке авторизации бросает `AdminLoginRequired`.
    В проде используется Bearer JWT через `app/api/deps.py`.
    """
    if not token:
        raise AdminLoginRequired
    organizer_id = decode_token(token)
    if organizer_id is None:
        raise AdminLoginRequired
    organizer = session.get(Organizer, organizer_id)
    if organizer is None:
        raise AdminLoginRequired
    return organizer
