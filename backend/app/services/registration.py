"""Бизнес-логика записи на мероприятие.

Все операции принимают `Session` извне — это делает функции легко
тестируемыми и позволяет объединять их в одну транзакцию с другими
шагами (например, создать рассылку и отметить участников посетившими).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Event,
    EventSlot,
    EventStatus,
    LateCancelPolicy,
    Registration,
    RegStatus,
    User,
)


@dataclass
class SignupResult:
    """Что произошло при попытке записаться."""

    registration: Registration
    is_waitlist: bool
    waitlist_position: int | None = None
    already_registered: bool = False


@dataclass
class CancelResult:
    """Что произошло при отмене записи."""

    cancelled: bool
    # Если место освободилось и его получил кто-то из waitlist — он здесь.
    promoted_registration: Registration | None = None
    # True, если отмена была «поздней» (после старта) и сохранена с маркером
    # LATE_CANCELLED — для UX-сообщения «отменено, но как поздняя отмена».
    late: bool = False
    # «forbidden» — отмена запрещена политикой мероприятия (после старта,
    # late_cancel_policy=DISALLOW). Бот покажет «отменить уже нельзя».
    forbidden_late: bool = False


def upsert_user(
    session: Session,
    max_user_id: int,
    chat_id: int,
    name: str | None = None,
    username: str | None = None,
    phone: str | None = None,
) -> User:
    """Создать или мягко обновить пользователя при контакте с ботом.

    «Мягко» — это значит:
    * имя/username не перезаписываем, если у нас уже есть значение
      (доверяем тому, что пришло раньше);
    * телефон, наоборот, всегда обновляем (пользователь мог сменить номер);
    * `last_active` бамаем при каждом обращении.
    """
    user = session.get(User, max_user_id)
    if user is None:
        user = User(
            max_user_id=max_user_id,
            chat_id=chat_id,
            name=name,
            username=username,
            phone=phone,
        )
        session.add(user)
    else:
        if name and not user.name:
            user.name = name
        if username and not user.username:
            user.username = username
        if phone:
            user.phone = phone
        user.last_active = datetime.now(UTC)
    session.flush()
    return user


def get_event_by_payload(session: Session, payload: str) -> Event | None:
    """Найти мероприятие по deeplink-payload (UUID из QR/ссылки)."""
    return session.scalar(select(Event).where(Event.deeplink_payload == payload))


def get_active_events(session: Session, limit: int = 20) -> list[Event]:
    """Опубликованные мероприятия, начало которых ещё не наступило, по возрастанию даты."""
    now = datetime.now(UTC).replace(tzinfo=None)
    stmt = (
        select(Event)
        .where(Event.status == EventStatus.PUBLISHED, Event.starts_at > now)
        .order_by(Event.starts_at)
        .limit(limit)
    )
    return list(session.scalars(stmt))


def sign_up(
    session: Session,
    event_id: int,
    user_id: int,
    slot_id: int | None = None,
) -> SignupResult:
    """Записать пользователя на мероприятие (или на конкретный слот).

    Capacity и waitlist считаются в той же ёмкости (слот, если есть, иначе event).
    Защита от гонок (CR-04): `SELECT ... FOR UPDATE` на строку события —
    на Postgres даёт row-lock, на SQLite no-op.
    """
    event = session.scalar(
        select(Event).where(Event.id == event_id).with_for_update()
    )
    if event is None or event.status != EventStatus.PUBLISHED:
        raise ValueError("Мероприятие не найдено или не опубликовано")
    if not event.registration_open:
        raise ValueError("Регистрация на мероприятие закрыта")
    if event.starts_at <= datetime.now(UTC).replace(tzinfo=None):
        raise ValueError("Мероприятие уже началось — запись закрыта")

    slot: EventSlot | None = None
    if event.has_slots():
        if slot_id is None:
            raise ValueError("Это мероприятие со слотами — выберите конкретное время")
        slot = session.get(EventSlot, slot_id)
        if slot is None or slot.event_id != event_id:
            raise ValueError("Указанный слот не принадлежит этому мероприятию")
    elif slot_id is not None:
        # Мероприятие без слотов, а нам прислали slot_id — игнорируем для UX.
        slot_id = None

    existing = session.scalar(
        select(Registration).where(
            and_(Registration.event_id == event_id, Registration.user_id == user_id)
        )
    )

    if existing and existing.status in (RegStatus.CONFIRMED, RegStatus.WAITLIST):
        return SignupResult(
            registration=existing,
            is_waitlist=existing.status == RegStatus.WAITLIST,
            waitlist_position=existing.waitlist_position,
            already_registered=True,
        )

    if existing and existing.status in (
        RegStatus.CANCELLED,
        RegStatus.LATE_CANCELLED,
        RegStatus.CANCELLED_BY_ORGANIZER,
    ):
        # Переиспользуем строку. Что обнуляем при «новой» записи:
        # * qr_token — старая картинка / прошлый скан не должны проходить;
        # * cancelled_at / attended_at — это была другая «жизнь» записи;
        # * entries_count / last_entry_at — иначе на event'е с max_entries=3
        #   юзер, прошедший 2 раза до cancel, после re-signup получил бы
        #   только 1 проход вместо 3 (см. E2E-V3 PARTIAL).
        # Что НЕ обнуляем: `code` (юзер привык к RG-XXXXXX, рассказал
        # друзьям, написал на запястье — пусть останется).
        reg = existing
        reg.cancelled_at = None
        reg.attended_at = None
        reg.entries_count = 0
        reg.last_entry_at = None
        reg.qr_token = uuid.uuid4().hex
        reg.slot_id = slot_id
    else:
        reg = Registration(
            event_id=event_id,
            user_id=user_id,
            slot_id=slot_id,
            status=RegStatus.CONFIRMED,
        )
        session.add(reg)

    if slot is not None:
        confirmed_count = session.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.slot_id == slot.id,
                Registration.status == RegStatus.CONFIRMED,
                Registration.id != reg.id,
            )
        ) or 0
        capacity = slot.capacity
    else:
        confirmed_count = session.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.event_id == event_id,
                Registration.slot_id.is_(None),
                Registration.status == RegStatus.CONFIRMED,
                Registration.id != reg.id,
            )
        ) or 0
        capacity = event.capacity

    if confirmed_count < capacity:
        reg.status = RegStatus.CONFIRMED
        reg.waitlist_position = None
        is_waitlist = False
        position: int | None = None
    else:
        # Waitlist считается внутри той же ёмкости (event или slot).
        waitlist_filter = (
            (Registration.slot_id == slot.id)
            if slot is not None
            else (
                (Registration.event_id == event_id)
                & (Registration.slot_id.is_(None))
            )
        )
        last_position = session.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                waitlist_filter,
                Registration.status == RegStatus.WAITLIST,
            )
        ) or 0
        reg.status = RegStatus.WAITLIST
        reg.waitlist_position = last_position + 1
        is_waitlist = True
        position = reg.waitlist_position

    session.flush()
    return SignupResult(registration=reg, is_waitlist=is_waitlist, waitlist_position=position)


def cancel_registration(session: Session, registration_id: int, user_id: int) -> CancelResult:
    """Отменить запись (по решению пользователя).

    `user_id` — защита от отмены чужой записи по подобранному id.

    Late-cancel policy (ТЗ §«Пользовательский процесс»):
    * `DISALLOW` — после `event.starts_at` отмена запрещена. Вернётся
      `CancelResult(cancelled=False, forbidden_late=True)`.
    * `ALLOW_MARKED` — отмена возможна; status → `LATE_CANCELLED`, место
      НЕ возвращается в пул (мероприятие уже идёт, продвигать некого).

    Для отмены до старта мероприятия — обычная логика: status → `CANCELLED`,
    место освобождается, продвигаем waitlist.
    """
    reg = session.get(Registration, registration_id)
    if reg is None or reg.user_id != user_id:
        return CancelResult(cancelled=False)
    if reg.status not in (RegStatus.CONFIRMED, RegStatus.WAITLIST):
        return CancelResult(cancelled=False)

    event = session.get(Event, reg.event_id)
    is_late = event is not None and event.starts_at <= datetime.now(UTC).replace(tzinfo=None)

    if is_late:
        assert event is not None  # narrow type: is_late => event is not None
        if event.late_cancel_policy == LateCancelPolicy.DISALLOW:
            return CancelResult(cancelled=False, forbidden_late=True)
        # Поздняя отмена: помечаем, место в пул не возвращаем.
        reg.status = RegStatus.LATE_CANCELLED
        reg.cancelled_at = datetime.now(UTC)
        session.flush()
        return CancelResult(cancelled=True, late=True)

    was_confirmed = reg.status == RegStatus.CONFIRMED
    reg.status = RegStatus.CANCELLED
    reg.cancelled_at = datetime.now(UTC)

    promoted: Registration | None = None
    if was_confirmed:
        promoted = promote_from_waitlist(session, reg.event_id, slot_id=reg.slot_id)
    else:
        # Отменился из waitlist → сдвигаем номера тех, кто был позади него.
        _shift_waitlist_positions(
            session, reg.event_id, slot_id=reg.slot_id,
            after_position=reg.waitlist_position or 0,
        )

    session.flush()
    return CancelResult(cancelled=True, promoted_registration=promoted)


def cancel_by_organizer(
    session: Session, registration_id: int
) -> CancelResult:
    """Отмена записи решением организатора (ТЗ §«Меню организатора»).

    Отличие от `cancel_registration`:
    * нет проверки `user_id` — это действие админа, а не самого участника;
    * статус → `CANCELLED_BY_ORGANIZER` (не `CANCELLED`), чтобы потом было
      видно «кто инициатор» в статистике;
    * место в пул возвращается всегда (даже если мероприятие уже идёт) —
      late-cancel-policy применяется только к пользовательской отмене.

    Owner-check (право этого организатора трогать эту запись) делается на
    уровне HTTP-маршрута через `assert_event_owned` — сервис проверять не
    обязан, иначе у нас два места правды.
    """
    reg = session.get(Registration, registration_id)
    if reg is None:
        return CancelResult(cancelled=False)
    if reg.status not in (RegStatus.CONFIRMED, RegStatus.WAITLIST):
        return CancelResult(cancelled=False)

    was_confirmed = reg.status == RegStatus.CONFIRMED
    reg.status = RegStatus.CANCELLED_BY_ORGANIZER
    reg.cancelled_at = datetime.now(UTC)

    promoted: Registration | None = None
    if was_confirmed:
        promoted = promote_from_waitlist(session, reg.event_id, slot_id=reg.slot_id)
    else:
        _shift_waitlist_positions(
            session, reg.event_id, slot_id=reg.slot_id,
            after_position=reg.waitlist_position or 0,
        )
    session.flush()
    return CancelResult(cancelled=True, promoted_registration=promoted)


def mark_attended_by_id(
    session: Session, registration_id: int
) -> Registration | None:
    """Отметить «пришёл» вручную из админки (без QR-сканера).

    ТЗ §«Меню организатора»: «либо отметить участника как пришедшего» —
    подразумевает оба варианта. QR-flow живёт в `mark_attended` (по токену),
    этот — для случая «QR забыли дома, но я знаю кого пускаю».

    Owner-check — на уровне HTTP-маршрута.
    """
    reg = session.get(Registration, registration_id)
    if reg is None or reg.status != RegStatus.CONFIRMED:
        return None
    reg.status = RegStatus.ATTENDED
    reg.attended_at = datetime.now(UTC)
    session.flush()
    return reg


def promote_from_waitlist(
    session: Session, event_id: int, slot_id: int | None = None
) -> Registration | None:
    """Перевести первого из waitlist в `confirmed` в рамках слота или event."""
    stmt = select(Registration).where(
        Registration.event_id == event_id,
        Registration.status == RegStatus.WAITLIST,
    )
    # Промотируем строго в той же «ёмкости» — слот A не пускает в очередь
    # на event-level и наоборот.
    if slot_id is None:
        stmt = stmt.where(Registration.slot_id.is_(None))
    else:
        stmt = stmt.where(Registration.slot_id == slot_id)
    candidate = session.scalar(stmt.order_by(Registration.waitlist_position).limit(1))
    if candidate is None:
        return None

    candidate.status = RegStatus.CONFIRMED
    old_position = candidate.waitlist_position or 0
    candidate.waitlist_position = None
    _shift_waitlist_positions(session, event_id, slot_id, after_position=old_position)
    session.flush()
    return candidate


def _shift_waitlist_positions(
    session: Session, event_id: int, slot_id: int | None, after_position: int
) -> None:
    """Сдвинуть waitlist_position на −1 для всех позади указанной позиции
    в той же «ёмкости» (event или slot).
    """
    stmt = select(Registration).where(
        Registration.event_id == event_id,
        Registration.status == RegStatus.WAITLIST,
        Registration.waitlist_position > after_position,
    )
    if slot_id is None:
        stmt = stmt.where(Registration.slot_id.is_(None))
    else:
        stmt = stmt.where(Registration.slot_id == slot_id)
    for r in session.scalars(stmt):
        if r.waitlist_position is not None:
            r.waitlist_position -= 1


def mark_attended(session: Session, qr_token: str) -> Registration | None:
    """Пометить запись «пришёл» — по QR-токену или человекочитаемому коду.

    Принимает на вход одну из двух форм:
    * `qr_token` — 32 hex-символа из QR-картинки (длинный непредсказуемый);
    * `code` — `RG-XXXXXX` из текстового сообщения боту (его удобнее ввести
      руками на входе, если QR не открывается).

    Возвращает `None`, если:
    * ничего не найдено по обоим полям;
    * запись не в статусе `CONFIRMED` (т.е. либо уже погашена, либо отменена).

    Это исключает двойное сканирование одного и того же гостя и сканирование
    отменённых пропусков.
    """
    needle = (qr_token or "").strip()
    if not needle:
        return None

    # Code приводим к uppercase — храним именно так, пользователь может ввести «rg-8h7xll».
    reg = session.scalar(select(Registration).where(Registration.qr_token == needle))
    if reg is None:
        reg = session.scalar(
            select(Registration).where(Registration.code == needle.upper())
        )

    if reg is None or reg.status != RegStatus.CONFIRMED:
        return None
    reg.status = RegStatus.ATTENDED
    reg.attended_at = datetime.now(UTC)
    session.flush()
    return reg


def get_user_registrations(session: Session, user_id: int) -> list[Registration]:
    """Все записи пользователя (включая отменённые), свежие сверху.

    `selectinload(Registration.event)` — eager-загрузка мероприятий одним
    дополнительным SELECT'ом. Без неё бот в «🎟 Мои записи» делал бы N+1
    запросов (по одному на каждую запись пользователя).
    """
    return list(
        session.scalars(
            select(Registration)
            .options(selectinload(Registration.event))
            .where(Registration.user_id == user_id)
            .order_by(Registration.registered_at.desc())
        )
    )


def get_event_registrations(
    session: Session, event_id: int, status_filter: str | None = None
) -> list[Registration]:
    """Записи на мероприятие, опционально отфильтрованные по статусу.

    `selectinload(Registration.user)` — eager-загрузка пользователей. Без
    неё страница мероприятия в админке при 100+ участниках делала бы N+1
    SELECT'ов (по одному на `r.user.name` в шаблоне).
    """
    stmt = (
        select(Registration)
        .options(selectinload(Registration.user))
        .where(Registration.event_id == event_id)
    )
    if status_filter:
        stmt = stmt.where(Registration.status == status_filter)
    stmt = stmt.order_by(Registration.registered_at)
    return list(session.scalars(stmt))
