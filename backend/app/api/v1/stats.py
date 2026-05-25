"""Сводная статистика для дашбордов."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AdminOrganizer, CurrentOrganizer, DbSession, OwnedEvent
from app.models import Registration, RegStatus
from app.schemas.common import ErrorResponse
from app.schemas.stats import EventStats, GlobalStats
from app.services.stats import collect_global_stats, registrations_by_day

router = APIRouter(tags=["stats"])


@router.get(
    "/stats",
    summary="Сводка по всему сервису",
    description="Глобальные счётчики для главного экрана дашборда. Только admin.",
    response_model=GlobalStats,
    responses={403: {"description": "Нужна роль admin", "model": ErrorResponse}},
)
def global_stats(organizer: AdminOrganizer, session: DbSession) -> GlobalStats:
    return collect_global_stats(session)


@router.get(
    "/stats/registrations-by-day",
    summary="Регистрации по дням",
    description="Список {date, count} за последние N дней. Только admin.",
    response_model=list[dict],
    responses={403: {"description": "Нужна роль admin", "model": ErrorResponse}},
)
def regs_by_day(
    organizer: AdminOrganizer,
    session: DbSession,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> list[dict]:
    return registrations_by_day(session, days)


@router.get(
    "/events/{event_id}/stats",
    summary="Сводка по мероприятию",
    description="Воронка по мероприятию: записались → подтвердились → пришли.",
    response_model=EventStats,
    responses={
        403: {"description": "Нет прав на это мероприятие", "model": ErrorResponse},
        404: {"description": "Мероприятие не найдено", "model": ErrorResponse},
    },
)
def event_stats(
    event: OwnedEvent, organizer: CurrentOrganizer, session: DbSession
) -> EventStats:
    by_status: dict[str, int] = {}
    for status_value, count in session.execute(
        select(Registration.status, func.count())
        .where(Registration.event_id == event.id)
        .group_by(Registration.status)
    ):
        by_status[status_value] = count

    confirmed = by_status.get(RegStatus.CONFIRMED, 0)
    attended = by_status.get(RegStatus.ATTENDED, 0)
    # ATTENDED — это бывший CONFIRMED: знаменатель для явки = confirmed + attended.
    total_with_slot = confirmed + attended

    # attendance_rate только после старта мероприятия — до него знаменатель бессмысленен.
    now = datetime.now(UTC).replace(tzinfo=None).replace(tzinfo=None)
    attendance_rate: float | None = None
    if event.starts_at < now and total_with_slot > 0:
        attendance_rate = attended / total_with_slot

    return EventStats(
        event_id=event.id,
        confirmed=confirmed,
        waitlist=by_status.get(RegStatus.WAITLIST, 0),
        cancelled=by_status.get(RegStatus.CANCELLED, 0),
        attended=attended,
        capacity=event.capacity,
        fill_rate=min(1.0, total_with_slot / event.capacity) if event.capacity else 0.0,
        attendance_rate=attendance_rate,
    )
