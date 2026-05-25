"""REST API управления организаторами (только admin)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.admin.auth import hash_password
from app.api.deps import AdminOrganizer, DbSession, get_client_ip
from app.models import (
    AuditActorType,
    AuditEntityType,
    AuditEvent,
    Event,
    Organizer,
    OrganizerRole,
)
from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.organizer import OrganizerCreate, OrganizerRead, OrganizerUpdate
from app.services.audit import log_event

router = APIRouter(prefix="/organizers", tags=["organizers"])


@router.get(
    "",
    summary="Список организаторов",
    response_model=list[OrganizerRead],
    responses={403: {"description": "Нужна роль admin", "model": ErrorResponse}},
)
def list_organizers(
    organizer: AdminOrganizer,
    session: DbSession,
) -> list[OrganizerRead]:
    orgs = session.scalars(select(Organizer).order_by(Organizer.created_at.desc()))
    return [OrganizerRead.model_validate(o) for o in orgs]


@router.post(
    "",
    summary="Создать организатора",
    response_model=OrganizerRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Нужна роль admin", "model": ErrorResponse},
        409: {"description": "Email уже занят", "model": ErrorResponse},
    },
)
def create_organizer(
    payload: OrganizerCreate,
    request: Request,
    organizer: AdminOrganizer,
    session: DbSession,
) -> OrganizerRead:
    if payload.role not in (OrganizerRole.ADMIN, OrganizerRole.ORGANIZER):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Недопустимая роль")
    existing = session.scalar(select(Organizer).where(Organizer.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email уже занят")

    target = Organizer(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name or None,
        department=payload.department or None,
        role=payload.role,
    )
    session.add(target)
    session.flush()
    client_ip = get_client_ip(request)
    log_event(
        session,
        event_type=AuditEvent.ORGANIZER_CREATED,
        actor_type=AuditActorType.ADMIN,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.ORGANIZER,
        entity_id=target.id,
        payload={"email": target.email, "role": target.role},
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    session.commit()
    session.refresh(target)
    return OrganizerRead.model_validate(target)


@router.patch(
    "/{organizer_id}",
    summary="Обновить организатора",
    response_model=OrganizerRead,
    responses={
        403: {"description": "Нужна роль admin", "model": ErrorResponse},
        404: {"description": "Организатор не найден", "model": ErrorResponse},
        409: {"description": "Email уже занят", "model": ErrorResponse},
    },
)
def update_organizer(
    organizer_id: int,
    payload: OrganizerUpdate,
    request: Request,
    organizer: AdminOrganizer,
    session: DbSession,
) -> OrganizerRead:
    target = session.get(Organizer, organizer_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организатор не найден")

    updates = payload.model_dump(exclude_unset=True)
    if "role" in updates and updates["role"] not in (OrganizerRole.ADMIN, OrganizerRole.ORGANIZER):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Недопустимая роль")
    if organizer_id == organizer.id and updates.get("role") == OrganizerRole.ORGANIZER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя понизить свою роль",
        )

    new_email = updates.get("email")
    if new_email is not None and new_email != target.email:
        dup = session.scalar(
            select(Organizer).where(Organizer.email == new_email, Organizer.id != organizer_id)
        )
        if dup is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email уже занят")
        target.email = new_email

    if "name" in updates:
        target.name = updates["name"]
    if "department" in updates:
        target.department = updates["department"]
    if "role" in updates:
        target.role = updates["role"]
    if "password" in updates and updates["password"] is not None:
        target.password_hash = hash_password(updates["password"])

    session.flush()
    client_ip = get_client_ip(request)
    log_event(
        session,
        event_type=AuditEvent.ORGANIZER_UPDATED,
        actor_type=AuditActorType.ADMIN,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.ORGANIZER,
        entity_id=target.id,
        payload={"email": target.email, "role": target.role},
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    session.commit()
    session.refresh(target)
    return OrganizerRead.model_validate(target)


@router.delete(
    "/{organizer_id}",
    summary="Удалить организатора",
    response_model=MessageResponse,
    responses={
        403: {"description": "Нужна роль admin или попытка удалить себя", "model": ErrorResponse},
        404: {"description": "Организатор не найден", "model": ErrorResponse},
        409: {"description": "У организатора есть мероприятия", "model": ErrorResponse},
    },
)
def delete_organizer(
    organizer_id: int,
    request: Request,
    organizer: AdminOrganizer,
    session: DbSession,
) -> MessageResponse:
    if organizer_id == organizer.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нельзя удалить себя")

    target = session.get(Organizer, organizer_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организатор не найден")

    has_events = session.scalar(select(Event.id).where(Event.organizer_id == organizer_id).limit(1))
    if has_events is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="У организатора есть мероприятия — сначала переназначьте или удалите их",
        )

    client_ip = get_client_ip(request)
    log_event(
        session,
        event_type=AuditEvent.ORGANIZER_DELETED,
        actor_type=AuditActorType.ADMIN,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.ORGANIZER,
        entity_id=organizer_id,
        payload={"email": target.email},
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    session.delete(target)
    session.commit()
    return MessageResponse(ok=True, message="Организатор удалён")
