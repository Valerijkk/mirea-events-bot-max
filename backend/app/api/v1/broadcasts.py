"""Ручки для рассылок по участникам мероприятия."""
from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentOrganizer, DbSession, OwnedEvent
from app.models import Broadcast
from app.schemas.broadcast import BroadcastRead, BroadcastRequest, BroadcastResult
from app.schemas.common import ErrorResponse
from app.services.broadcast import create_broadcast, send_broadcast

router = APIRouter(prefix="/events/{event_id}/broadcasts", tags=["broadcasts"])


def _to_read(bc: Broadcast) -> BroadcastRead:
    return BroadcastRead.model_validate(bc)


@router.post(
    "",
    summary="Создать и сразу отправить рассылку",
    description=(
        "Создаёт запись о рассылке и тут же её отправляет (синхронно, по rate-limit MAX). "
        "Возвращает финальные счётчики `delivered_count` и `failed_count`. "
        "Для крупных рассылок (>500 получателей) рекомендуется отдельный воркер — "
        "это пометка к будущей итерации."
    ),
    response_model=BroadcastResult,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Мероприятие не найдено", "model": ErrorResponse}},
)
async def send_broadcast_now(
    payload: BroadcastRequest,
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> BroadcastResult:
    bc = create_broadcast(
        session,
        event_id=event.id,
        organizer_id=organizer.id,
        segment=payload.segment,
        message_text=payload.message,
    )
    session.commit()
    await send_broadcast(session, bc.id)
    session.refresh(bc)
    return BroadcastResult(broadcast=_to_read(bc))


@router.get(
    "",
    summary="История рассылок мероприятия",
    description="Все рассылки по этому мероприятию, свежие сверху.",
    response_model=list[BroadcastRead],
    responses={404: {"description": "Мероприятие не найдено", "model": ErrorResponse}},
)
async def list_broadcasts(
    event: OwnedEvent,
    organizer: CurrentOrganizer,
    session: DbSession,
) -> list[BroadcastRead]:
    items = list(
        session.scalars(
            select(Broadcast)
            .where(Broadcast.event_id == event.id)
            .order_by(Broadcast.created_at.desc())
        )
    )
    return [_to_read(b) for b in items]
