"""Общие FastAPI-зависимости REST API: Bearer-JWT + проверка прав на событие (multi-tenant, роль `admin` обходит ограничение)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.admin.auth import decode_token
from app.db import get_session
from app.models import Event, Organizer, OrganizerRole

# auto_error=False — мы сами формулируем красивое сообщение об ошибке.
_bearer_scheme = HTTPBearer(auto_error=False, description="JWT, полученный через POST /api/v1/auth/login")


def get_current_organizer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
    session: Annotated[Session, Depends(get_session)] = None,  # type: ignore[assignment]
) -> Organizer:
    """Резолв организатора по Bearer-токену. Все ошибки авторизации — 401 (нет роли «авторизован, но не разрешён»)."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется заголовок Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    organizer_id = decode_token(credentials.credentials)
    if organizer_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен невалиден или истёк",
            headers={"WWW-Authenticate": "Bearer"},
        )
    organizer = session.get(Organizer, organizer_id)
    if organizer is None:
        # Организатор удалён, но токен ещё формально живой.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Организатор не найден",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return organizer


def get_admin_organizer(organizer: Annotated[Organizer, Depends(get_current_organizer)]) -> Organizer:
    """Только role=admin — для audit-log и прочих глобальных операций."""
    if organizer.role != OrganizerRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещён: нужна роль admin",
        )
    return organizer


# Сокращённый алиас для красивых сигнатур в роутерах.
CurrentOrganizer = Annotated[Organizer, Depends(get_current_organizer)]
AdminOrganizer = Annotated[Organizer, Depends(get_admin_organizer)]
DbSession = Annotated[Session, Depends(get_session)]


def assert_event_owned(event: Event | None, organizer: Organizer) -> Event:
    """Проверка владения событием. 404 если None, 403 если чужое; роль `admin` обходит."""
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Мероприятие не найдено"
        )
    if organizer.role != OrganizerRole.ADMIN and event.organizer_id != organizer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав на это мероприятие",
        )
    return event


def get_owned_event(
    event_id: int,
    organizer: Annotated[Organizer, Depends(get_current_organizer)],
    session: Annotated[Session, Depends(get_session)],
) -> Event:
    """FastAPI-зависимость: event_id из URL → Event с проверкой владения."""
    return assert_event_owned(session.get(Event, event_id), organizer)


def get_owned_event_by_id(
    session: Session, event_id: int, organizer: Organizer
) -> Event:
    """Версия без FastAPI-Depends — для сервисов и legacy-вызовов."""
    return assert_event_owned(session.get(Event, event_id), organizer)


OwnedEvent = Annotated[Event, Depends(get_owned_event)]


def get_client_ip(request: Request) -> str:
    """Извлечь IP клиента из запроса."""
    return (request.client.host if request.client else "unknown") or "unknown"
