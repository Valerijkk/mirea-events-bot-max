"""Сводная статистика — единый источник истины для дашборда и REST `/api/v1/stats`."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Event, EventStatus, Registration, RegStatus, User
from app.schemas.stats import GlobalStats


def collect_global_stats(session: Session) -> GlobalStats:
    """Глобальные счётчики для главного экрана дашборда. Один и тот же объект — для HTML-админки и REST."""
    total_users = session.scalar(select(func.count()).select_from(User)) or 0
    total_events = session.scalar(select(func.count()).select_from(Event)) or 0
    published_events = session.scalar(
        select(func.count()).select_from(Event).where(Event.status == EventStatus.PUBLISHED)
    ) or 0
    total_regs = session.scalar(select(func.count()).select_from(Registration)) or 0
    active_regs = session.scalar(
        select(func.count())
        .select_from(Registration)
        .where(Registration.status.in_([RegStatus.CONFIRMED, RegStatus.WAITLIST]))
    ) or 0
    attended_total = session.scalar(
        select(func.count()).select_from(Registration).where(Registration.status == RegStatus.ATTENDED)
    ) or 0
    return GlobalStats(
        total_users=total_users,
        total_events=total_events,
        published_events=published_events,
        total_registrations=total_regs,
        active_registrations=active_regs,
        attended_total=attended_total,
    )


def registrations_by_day(session: Session, days: int = 7) -> list[dict[str, int | str]]:
    """Список `{date: 'дд.мм', count: N}` за последние `days` дней.

    Пустые дни тоже включены — иначе Chart.js рисует прерывистый график.
    Используем func.date() — работает и на SQLite, и на Postgres.
    """
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)

    rows = session.execute(
        select(func.date(Registration.registered_at), func.count())
        .where(Registration.registered_at >= datetime.combine(start, datetime.min.time()))
        .group_by(func.date(Registration.registered_at))
    ).all()
    # SQLite даёт строку 'YYYY-MM-DD', Postgres — datetime.date; приводим к str.
    by_date: dict[str, int] = {str(d): int(c) for d, c in rows}

    result: list[dict[str, int | str]] = []
    for i in range(days):
        day = start + timedelta(days=i)
        result.append({"date": day.strftime("%d.%m"), "count": by_date.get(str(day), 0)})
    return result
