"""Сервис рассылок по сегментам участников мероприятия.

Сегменты:

* `all` — все, у кого активная запись (`confirmed` + `waitlist`)
* `confirmed` — только подтверждённые
* `waitlist` — только в листе ожидания
* `attended` — только посетившие
* `no_show` — не явившиеся

Рассылка идёт последовательно с грубым rate-limit. На больших объёмах
(>500 получателей) стоит вынести в фоновый воркер с пулом отправок —
сейчас функция оставлена синхронной, потому что для типовых мероприятий
(50–100 человек) латентность 3–6 секунд приемлема.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bot.notifications import send_text
from app.bot.texts import BROADCAST_PREFIX, EVENT_CANCELLED_NOTICE
from app.models import Broadcast, BroadcastSegment, Event, Registration, RegStatus, User

logger = logging.getLogger(__name__)

# Грубый rate-limit (секунд между сообщениями), чтобы не получить 429 от MAX
# на крупной рассылке. 50 мс между отправками ≈ 20 rps.
_RATE_LIMIT_SECONDS = 0.05


def _segment_to_statuses(segment: str) -> list[str]:
    """Сопоставить имя сегмента → список статусов записей, которым шлём."""
    return {
        BroadcastSegment.ALL: [RegStatus.CONFIRMED, RegStatus.WAITLIST],
        BroadcastSegment.CONFIRMED: [RegStatus.CONFIRMED],
        BroadcastSegment.WAITLIST: [RegStatus.WAITLIST],
        BroadcastSegment.ATTENDED: [RegStatus.ATTENDED],
        BroadcastSegment.NO_SHOW: [RegStatus.NO_SHOW],
    }.get(segment, [])


def get_recipients(session: Session, event_id: int, segment: str) -> list[User]:
    """Список пользователей, попадающих в сегмент.

    Уважаем ОБА флага:
    * `User.notifications_enabled` — глобальный (отписка от бота вообще);
    * `Registration.notifications_enabled` — per-event (ТЗ §«Пользовательский процесс»:
      «настройка внутри записи, а не отписка от бота в целом»).
    """
    statuses = _segment_to_statuses(segment)
    if not statuses:
        return []
    stmt = (
        select(User)
        .join(Registration, Registration.user_id == User.max_user_id)
        .where(
            Registration.event_id == event_id,
            Registration.status.in_(statuses),
            Registration.notifications_enabled.is_(True),
            User.notifications_enabled.is_(True),
        )
        .distinct()
    )
    return list(session.scalars(stmt))


def create_broadcast(
    session: Session,
    event_id: int,
    organizer_id: int | None,
    segment: str,
    message_text: str,
) -> Broadcast:
    """Создать запись о рассылке. Сама отправка — отдельным вызовом `send_broadcast`."""
    broadcast = Broadcast(
        event_id=event_id,
        organizer_id=organizer_id,
        segment=segment,
        message_text=message_text,
    )
    session.add(broadcast)
    session.flush()
    return broadcast


async def send_broadcast(session: Session, broadcast_id: int) -> None:
    """Отправить рассылку с уже созданной записью.

    Заметка: вызывается из async-контекста (FastAPI обработчика). Если в БД
    уже стоит `sent_at`, повторно ничего не делаем — это страхует от
    случайных дублей при ретре формы.
    """
    broadcast = session.get(Broadcast, broadcast_id)
    if broadcast is None or broadcast.sent_at is not None:
        return

    event = session.get(Event, broadcast.event_id)
    if event is None:
        return

    recipients = get_recipients(session, broadcast.event_id, broadcast.segment)
    full_text = BROADCAST_PREFIX.format(event_title=event.title) + broadcast.message_text

    delivered = 0
    failed = 0
    for user in recipients:
        ok = await send_text(chat_id=user.chat_id, text=full_text)
        if ok:
            delivered += 1
        else:
            failed += 1
        await asyncio.sleep(_RATE_LIMIT_SECONDS)

    broadcast.sent_at = datetime.now(UTC)
    broadcast.delivered_count = delivered
    broadcast.failed_count = failed
    session.commit()
    logger.info(
        "Broadcast %s sent: %s delivered, %s failed (event_id=%s, segment=%s)",
        broadcast_id, delivered, failed, broadcast.event_id, broadcast.segment,
    )


async def notify_event_cancelled(session: Session, event_id: int) -> tuple[int, int]:
    """Разослать уведомление об отмене мероприятия всем активным участникам.

    Возвращает `(delivered, failed)` — кол-во доставленных и неуспешных
    сообщений. Безопасна при повторном вызове: статусы записей переводим
    в `CANCELLED` отдельно, здесь только отправка.

    Чем отличается от обычной рассылки:
    * текст — фиксированный шаблон с понятной формулировкой;
    * сегмент — `confirmed + waitlist` (всем, кто чего-то ждал);
    * не создаём запись в таблице `broadcasts` — это автособытие, а не
      редактируемая рассылка организатора.
    """
    event = session.get(Event, event_id)
    if event is None:
        return 0, 0

    statuses = [RegStatus.CONFIRMED, RegStatus.WAITLIST]
    recipients = list(
        session.scalars(
            select(User)
            .join(Registration, Registration.user_id == User.max_user_id)
            .where(
                Registration.event_id == event_id,
                Registration.status.in_(statuses),
                Registration.notifications_enabled.is_(True),
                User.notifications_enabled.is_(True),
            )
            .distinct()
        )
    )
    text = EVENT_CANCELLED_NOTICE.format(
        title=event.title,
        date_str=event.starts_at.strftime("%d.%m.%Y в %H:%M"),
    )
    delivered = 0
    failed = 0
    for user in recipients:
        ok = await send_text(chat_id=user.chat_id, text=text)
        if ok:
            delivered += 1
        else:
            failed += 1
        await asyncio.sleep(_RATE_LIMIT_SECONDS)
    logger.info(
        "Event %s cancellation notice: %s delivered, %s failed",
        event_id, delivered, failed,
    )
    return delivered, failed
