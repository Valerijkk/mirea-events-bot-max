"""CRUD-ручки для мероприятий."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from app.api.deps import CurrentOrganizer, DbSession, OwnedEvent, get_client_ip
from app.models import (
    AuditActorType,
    AuditEntityType,
    AuditEvent,
    Event,
    EventStatus,
    OrganizerRole,
    Registration,
    RegStatus,
)
from app.scheduler import schedule_reminders_for_registration
from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.event import EventCreate, EventRead, EventStatusUpdate, EventUpdate
from app.services.audit import log_event
from app.services.broadcast import notify_event_cancelled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


def _to_read(event: Event) -> EventRead:
    """ORM-объект → схема ответа с агрегатами (count'ы)."""
    confirmed = event.confirmed_count()
    waitlist = sum(1 for r in event.registrations if r.status == RegStatus.WAITLIST)
    return EventRead(
        id=event.id,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        location=event.location,
        cover_url=event.cover_url,
        capacity=event.capacity,
        status=event.status,
        organizer_id=event.organizer_id,
        deeplink_payload=event.deeplink_payload,
        free_slots=event.free_slots(),
        confirmed_count=confirmed,
        waitlist_count=waitlist,
        duration_minutes=event.duration_minutes,
        format=event.format,
        requirements=event.requirements,
        cancellation_terms=event.cancellation_terms,
        meeting_url=event.meeting_url,
        late_cancel_policy=event.late_cancel_policy,
        registration_open=event.registration_open,
        max_entries=event.max_entries,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


@router.get(
    "",
    summary="Список мероприятий",
    description=(
        "Возвращает мероприятия с фильтрами. "
        "По умолчанию — все, отсортированные по дате начала (свежие сверху). "
        "Опции `status` и `only_upcoming` помогают сузить выборку."
    ),
    response_model=list[EventRead],
)
def list_events(
    organizer: CurrentOrganizer,
    session: DbSession,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Фильтр по статусу: draft / published / cancelled / finished."),
    ] = None,
    type_filter: Annotated[
        str | None,
        Query(alias="type", description="Фильтр по типу: open_day/masterclass/olympiad/tour/consultation/other."),
    ] = None,
    format_filter: Annotated[
        str | None,
        Query(alias="format", description="Фильтр по формату: online / onsite."),
    ] = None,
    only_upcoming: Annotated[
        bool,
        Query(description="Если True — отдать только мероприятия, начало которых ещё не наступило."),
    ] = False,
    limit: Annotated[int, Query(ge=1, le=500, description="Максимум записей в ответе.")] = 100,
) -> list[EventRead]:
    stmt = select(Event)
    if organizer.role != OrganizerRole.ADMIN:
        stmt = stmt.where(Event.organizer_id == organizer.id)
    if status_filter:
        stmt = stmt.where(Event.status == status_filter)
    if type_filter:
        stmt = stmt.where(Event.event_type == type_filter)
    if format_filter:
        stmt = stmt.where(Event.format == format_filter)
    if only_upcoming:
        stmt = stmt.where(Event.starts_at > datetime.now(UTC).replace(tzinfo=None))
    stmt = stmt.order_by(Event.starts_at.desc()).limit(limit)
    return [_to_read(e) for e in session.scalars(stmt)]


@router.post(
    "",
    summary="Создать мероприятие",
    description="Создаёт мероприятие в статусе `draft`. Перевести в `published` можно отдельной ручкой.",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    payload: EventCreate,
    request: Request,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> EventRead:
    event = Event(
        title=payload.title,
        description=payload.description,
        event_type=payload.event_type,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        location=payload.location,
        cover_url=payload.cover_url,
        capacity=payload.capacity,
        duration_minutes=payload.duration_minutes,
        format=payload.format,
        requirements=payload.requirements,
        cancellation_terms=payload.cancellation_terms,
        meeting_url=payload.meeting_url,
        late_cancel_policy=payload.late_cancel_policy,
        max_entries=payload.max_entries,
        organizer_id=organizer.id,
        status=EventStatus.DRAFT,
    )
    session.add(event)
    session.flush()
    client_ip = get_client_ip(request)
    actor_type = (
        AuditActorType.ADMIN
        if organizer.role == OrganizerRole.ADMIN
        else AuditActorType.ORGANIZER
    )
    log_event(
        session,
        event_type=AuditEvent.EVENT_CREATED,
        actor_type=actor_type,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.EVENT,
        entity_id=event.id,
        payload={"title": event.title},
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    session.commit()
    session.refresh(event)
    return _to_read(event)


@router.get(
    "/{event_id}",
    summary="Получить мероприятие",
    response_model=EventRead,
    responses={
        403: {"description": "Нет прав на это мероприятие", "model": ErrorResponse},
        404: {"description": "Мероприятие не найдено", "model": ErrorResponse},
    },
)
def get_event(event: OwnedEvent, organizer: CurrentOrganizer) -> EventRead:
    return _to_read(event)


@router.patch(
    "/{event_id}",
    summary="Изменить мероприятие",
    description="Частичное обновление. Передавайте только те поля, которые хотите изменить.",
    response_model=EventRead,
    responses={
        403: {"description": "Нет прав на это мероприятие", "model": ErrorResponse},
        404: {"description": "Мероприятие не найдено", "model": ErrorResponse},
    },
)
def update_event(
    payload: EventUpdate,
    request: Request,
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> EventRead:
    updates = payload.model_dump(exclude_unset=True)

    # capacity не опускаем ниже confirmed — иначе overbook и инварианты sign_up/free_slots сломаются.
    new_capacity = updates.get("capacity")
    if new_capacity is not None:
        confirmed = event.confirmed_count()
        if new_capacity < confirmed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Нельзя уменьшить capacity до {new_capacity}: "
                    f"уже подтверждено {confirmed} участников"
                ),
            )

    # Сдвиг даты → переплан напоминаний для подтверждённых записей (старые снимутся внутри scheduler'а).
    starts_at_changed = (
        "starts_at" in updates and updates["starts_at"] != event.starts_at
    )

    for key, value in updates.items():
        setattr(event, key, value)
    session.flush()
    client_ip = get_client_ip(request)
    actor_type = (
        AuditActorType.ADMIN
        if organizer.role == OrganizerRole.ADMIN
        else AuditActorType.ORGANIZER
    )
    log_event(
        session,
        event_type=AuditEvent.EVENT_UPDATED,
        actor_type=actor_type,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.EVENT,
        entity_id=event.id,
        payload={"title": event.title},
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    session.commit()
    session.refresh(event)

    if starts_at_changed:
        confirmed_ids = list(
            session.scalars(
                select(Registration.id).where(
                    Registration.event_id == event.id,
                    Registration.status == RegStatus.CONFIRMED,
                )
            )
        )
        for reg_id in confirmed_ids:
            schedule_reminders_for_registration(reg_id, event.starts_at)

    return _to_read(event)


@router.post(
    "/{event_id}/status",
    summary="Сменить статус мероприятия",
    description=(
        "Опубликовать (`published`), отменить (`cancelled`), завершить (`finished`) "
        "или вернуть в черновик (`draft`). При переходе в `cancelled` всем активным "
        "участникам (confirmed + waitlist) автоматически уходит уведомление в боте."
    ),
    response_model=EventRead,
    responses={
        403: {"description": "Нет прав на это мероприятие", "model": ErrorResponse},
        404: {"description": "Мероприятие не найдено", "model": ErrorResponse},
    },
)
async def set_event_status(
    payload: EventStatusUpdate,
    request: Request,
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> EventRead:
    # old_status нужен, чтобы при идемпотентном cancelled→cancelled не слать уведомление повторно.
    old_status = event.status
    event.status = payload.status
    session.flush()
    client_ip = get_client_ip(request)
    actor_type = (
        AuditActorType.ADMIN
        if organizer.role == OrganizerRole.ADMIN
        else AuditActorType.ORGANIZER
    )
    if payload.status == EventStatus.CANCELLED:
        audit_event_type = AuditEvent.EVENT_CANCELLED
    elif payload.status == EventStatus.FINISHED:
        audit_event_type = AuditEvent.EVENT_FINISHED
    elif payload.status == EventStatus.PUBLISHED:
        audit_event_type = AuditEvent.EVENT_PUBLISHED
    else:
        audit_event_type = None
    if audit_event_type is not None:
        log_event(
            session,
            event_type=audit_event_type,
            actor_type=actor_type,
            organizer_id=organizer.id,
            actor_display=organizer.name or organizer.email,
            entity_type=AuditEntityType.EVENT,
            entity_id=event.id,
            payload={"title": event.title, "old_status": old_status, "new_status": payload.status},
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
        )
    session.commit()
    if (
        payload.status == EventStatus.CANCELLED
        and old_status != EventStatus.CANCELLED
    ):
        try:
            await notify_event_cancelled(session, event.id)
        except Exception:
            logger.exception("notify_event_cancelled failed for event_id=%s", event.id)
    session.refresh(event)
    return _to_read(event)


@router.delete(
    "/{event_id}",
    summary="Удалить мероприятие",
    description=(
        "Жёсткое удаление — снесёт мероприятие и все связанные с ним записи. "
        "Прежде чем удалить, всем активным участникам уходит уведомление об отмене — "
        "иначе они приедут к закрытым дверям. Для безопасной отмены без удаления "
        "используйте `POST /events/{id}/status` со статусом `cancelled`."
    ),
    response_model=MessageResponse,
    responses={
        403: {"description": "Нет прав на это мероприятие", "model": ErrorResponse},
        404: {"description": "Мероприятие не найдено", "model": ErrorResponse},
    },
)
async def delete_event(
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> MessageResponse:
    # Уведомляем ДО delete: после CASCADE event.registrations пуст. Сетевые ошибки глотаем — операция оператора, не транзакция.
    event_id = event.id
    try:
        await notify_event_cancelled(session, event_id)
    except Exception:
        logger.exception("notify_event_cancelled failed for event_id=%s", event_id)
    actor_type = (
        AuditActorType.ADMIN
        if organizer.role == OrganizerRole.ADMIN
        else AuditActorType.ORGANIZER
    )
    log_event(
        session,
        event_type=AuditEvent.EVENT_DELETED,
        actor_type=actor_type,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.EVENT,
        entity_id=event_id,
        payload={"title": event.title},
    )
    session.delete(event)
    session.commit()
    return MessageResponse(ok=True, message="Мероприятие удалено")
