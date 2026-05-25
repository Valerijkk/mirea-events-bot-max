"""REST API слотов мероприятия."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentOrganizer, DbSession, OwnedEvent, get_client_ip
from app.models import AuditActorType, AuditEntityType, AuditEvent, EventSlot, OrganizerRole
from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.slot import SlotCreate, SlotRead
from app.services.audit import log_event
from app.services.slots import create_slot, delete_slot, list_slots

router = APIRouter(prefix="/events/{event_id}/slots", tags=["slots"])


def _to_read(slot: EventSlot) -> SlotRead:
    return SlotRead(
        id=slot.id,
        event_id=slot.event_id,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        capacity=slot.capacity,
        label=slot.label,
        free_slots=slot.free_slots(),
        created_at=slot.created_at,
    )


@router.get(
    "",
    summary="Список слотов мероприятия",
    response_model=list[SlotRead],
    responses={
        403: {"description": "Нет прав на это мероприятие", "model": ErrorResponse},
        404: {"description": "Мероприятие не найдено", "model": ErrorResponse},
    },
)
def list_event_slots(
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> list[SlotRead]:
    slots = list_slots(session, event.id)
    return [_to_read(s) for s in slots]


@router.post(
    "",
    summary="Создать слот",
    response_model=SlotRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Нет прав на это мероприятие", "model": ErrorResponse},
        404: {"description": "Мероприятие не найдено", "model": ErrorResponse},
    },
)
def create_event_slot(
    payload: SlotCreate,
    request: Request,
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> SlotRead:
    slot = create_slot(
        session,
        event_id=event.id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        capacity=payload.capacity,
        label=payload.label,
    )
    client_ip = get_client_ip(request)
    actor_type = (
        AuditActorType.ADMIN if organizer.role == OrganizerRole.ADMIN else AuditActorType.ORGANIZER
    )
    log_event(
        session,
        event_type=AuditEvent.SLOT_CREATED,
        actor_type=actor_type,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.SLOT,
        entity_id=slot.id,
        payload={"event_id": event.id},
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    session.commit()
    session.refresh(slot)
    return _to_read(slot)


@router.delete(
    "/{slot_id}",
    summary="Удалить слот",
    response_model=MessageResponse,
    responses={
        403: {"description": "Нет прав на это мероприятие", "model": ErrorResponse},
        404: {"description": "Слот или мероприятие не найдено", "model": ErrorResponse},
    },
)
def delete_event_slot(
    slot_id: int,
    request: Request,
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> MessageResponse:
    if not delete_slot(session, slot_id=slot_id, event_id=event.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Слот не найден")
    client_ip = get_client_ip(request)
    actor_type = (
        AuditActorType.ADMIN if organizer.role == OrganizerRole.ADMIN else AuditActorType.ORGANIZER
    )
    log_event(
        session,
        event_type=AuditEvent.SLOT_DELETED,
        actor_type=actor_type,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.SLOT,
        entity_id=slot_id,
        payload={"event_id": event.id},
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    session.commit()
    return MessageResponse(ok=True, message="Слот удалён")
