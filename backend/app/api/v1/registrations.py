"""Ручки для работы со списком записей мероприятия."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import CurrentOrganizer, DbSession, OwnedEvent, get_client_ip
from app.bot.notifications import send_photo, send_text
from app.bot.texts import CANCELLED_BY_ORGANIZER_NOTICE, WAITLIST_PROMOTED
from app.core.formatting import format_event_dt
from app.models import (
    AuditActorType,
    AuditEntityType,
    AuditEvent,
    OrganizerRole,
    Registration,
    User,
)
from app.scheduler import schedule_reminders_for_registration
from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.registration import RegistrationRead, UserRead
from app.services.audit import log_event
from app.services.qr import generate_qr
from app.services.registration import cancel_by_organizer, get_event_registrations

router = APIRouter(prefix="/events/{event_id}/registrations", tags=["registrations"])


@router.get(
    "",
    summary="Записи на мероприятие",
    description=(
        "Список всех записей мероприятия с возможностью фильтра по статусу. "
        "Сортировка — по времени регистрации, старые сверху (так удобнее работать с очередью)."
    ),
    response_model=list[RegistrationRead],
    responses={404: {"description": "Мероприятие не найдено", "model": ErrorResponse}},
)
def list_registrations(
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
    status_filter: Annotated[
        Literal["confirmed", "waitlist", "cancelled", "attended", "no_show"] | None,
        Query(alias="status", description="Фильтр по статусу записи."),
    ] = None,
) -> list[RegistrationRead]:
    regs = get_event_registrations(session, event.id, status_filter=status_filter)
    return [
        RegistrationRead(
            id=r.id,
            event_id=r.event_id,
            user_id=r.user_id,
            status=r.status,
            code=r.code,
            waitlist_position=r.waitlist_position,
            registered_at=r.registered_at,
            cancelled_at=r.cancelled_at,
            attended_at=r.attended_at,
            user=UserRead.model_validate(r.user) if r.user else None,
        )
        for r in regs
    ]


@router.post(
    "/{reg_id}/cancel",
    summary="Отменить запись (организатором)",
    description=(
        "Отмена участника организатором. Статус → cancelled_by_organizer, "
        "место возвращается в пул, следующий из waitlist продвигается."
    ),
    response_model=MessageResponse,
    responses={
        403: {"description": "Нет прав на это мероприятие", "model": ErrorResponse},
        404: {"description": "Запись или мероприятие не найдено", "model": ErrorResponse},
        409: {"description": "Запись нельзя отменить в текущем статусе", "model": ErrorResponse},
    },
)
async def cancel_registration_by_organizer(
    reg_id: int,
    request: Request,
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> MessageResponse:
    reg = session.get(Registration, reg_id)
    if reg is None or reg.event_id != event.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")

    target_user_id = reg.user_id
    result = cancel_by_organizer(session, reg_id)
    if not result.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Запись нельзя отменить в текущем статусе",
        )

    client_ip = get_client_ip(request)
    actor_type = (
        AuditActorType.ADMIN
        if organizer.role == OrganizerRole.ADMIN
        else AuditActorType.ORGANIZER
    )
    log_event(
        session,
        event_type=AuditEvent.REGISTRATION_CANCELLED,
        actor_type=actor_type,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.REGISTRATION,
        entity_id=reg_id,
        payload={"event_id": event.id, "by": "organizer"},
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    session.commit()

    event_dt_str = format_event_dt(event.starts_at)
    user = session.get(User, target_user_id)
    if user is not None and user.notifications_enabled:
        try:
            await send_text(
                chat_id=user.chat_id,
                text=CANCELLED_BY_ORGANIZER_NOTICE.format(
                    title=event.title,
                    date_str=event_dt_str,
                ),
            )
        except Exception:
            pass
    if result.promoted_registration is not None:
        promoted = result.promoted_registration
        promoted_reg_id = promoted.id
        promoted_starts_at = event.starts_at
        try:
            promoted_user = session.get(User, promoted.user_id)
            if promoted_user is not None and promoted_user.notifications_enabled:
                qr_path = generate_qr(promoted.qr_token)
                text = WAITLIST_PROMOTED.format(
                    title=event.title,
                    date_str=event_dt_str,
                ) + f"\n\n🔢 Код записи: {promoted.code}"
                await send_text(chat_id=promoted_user.chat_id, text=text)
                await send_photo(chat_id=promoted_user.chat_id, photo_path=qr_path)
        except Exception:
            pass
        # Планируем напоминания для promoted-участника (24ч и 1ч до начала)
        schedule_reminders_for_registration(promoted_reg_id, promoted_starts_at)

    return MessageResponse(ok=True, message="Запись отменена")
