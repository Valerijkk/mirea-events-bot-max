"""Бизнес-логика сканера QR-пропусков.

Вынесена сюда, чтобы её можно было импортировать из `app/api/v1/scan.py`
(REST-сканер на Bearer JWT) без циклической зависимости между слоями.

Различает четыре исхода — UI на основании `status` подсвечивает результат
разным цветом (зелёный / амбер / красный):

    ok                — посещение зафиксировано прямо сейчас, пускайте;
    already_attended  — этот пропуск уже использовали раньше, повторный
                        вход запрещён (см. attended_at);
    cancelled         — запись отменена (пользователем / организатором /
                        поздно), пускать нельзя;
    not_found         — qr_token или code в системе не существуют.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bot.notifications import send_text
from app.bot.texts import ATTENDANCE_CONFIRMED
from app.models import (
    AuditActorType,
    AuditEntityType,
    AuditEvent,
    Event,
    Organizer,
    Registration,
    RegStatus,
    User,
)
from app.schemas.scan import ScanResponse
from app.services.audit import log_event


async def scan_lookup(
    session: Session, organizer: Organizer, needle_raw: str
) -> ScanResponse:
    """Найти запись по qr_token / code и отметить посещение, если уместно.

    Owner-check (`assert_event_owned`) делается до изменения статуса, чтобы
    сторонний организатор не мог погасить чужой QR случайным сканом.
    """
    needle = (needle_raw or "").strip()
    if not needle:
        return ScanResponse(
            ok=False, status="not_found", error="QR или код не введён"
        )

    # Ищем запись по qr_token (32 hex) либо по code (RG-XXXXXX, регистр любой).
    # `with_for_update` нужен против гонки: без блокировки два сканера на
    # одном QR одновременно прочитают `entries_count=0`, оба пройдут проверку
    # `0 >= 1` и оба запишут `1` — двойной проход по одному пропуску. На
    # Postgres даёт row-lock, на SQLite — no-op (single-writer и так).
    reg = session.scalar(
        select(Registration).where(Registration.qr_token == needle).with_for_update()
    )
    if reg is None:
        reg = session.scalar(
            select(Registration).where(Registration.code == needle.upper()).with_for_update()
        )
    if reg is None:
        return ScanResponse(
            ok=False, status="not_found",
            error=f"QR или код «{needle[:20]}» не найден в системе",
        )

    # Lazy-import — `app.api.deps` импортирует `app.api.v1.scan`, который
    # импортирует обратно нас. Цикл рвём здесь.
    from fastapi import HTTPException

    from app.api.deps import assert_event_owned

    event = session.get(Event, reg.event_id)
    try:
        assert_event_owned(event, organizer)
    except HTTPException as exc:
        # Не различаем «чужое мероприятие» и «не найдено вообще» — иначе
        # организатор-инсайдер мог бы брутфорсить RG-коды чужих мероприятий
        # и угадывать существование (см. SEC-V3-H1).
        if exc.status_code in (403, 404):
            return ScanResponse(
                ok=False, status="not_found",
                attended_at=None,
                error=f"QR или код «{needle[:20]}» не найден в системе",
            )
        raise
    user = session.get(User, reg.user_id)
    user_name = (user.name if user else None) or "—"
    event_title = event.title if event else "—"

    # Отменённые записи — пускать нельзя ни при каких max_entries.
    if reg.status in (
        RegStatus.CANCELLED, RegStatus.LATE_CANCELLED, RegStatus.CANCELLED_BY_ORGANIZER,
    ):
        return ScanResponse(
            ok=False, status="cancelled",
            user_name=user_name, event_title=event_title,
            attended_at=None,
            error="Запись отменена — пускать нельзя.",
        )
    # WAITLIST / NO_SHOW / DRAFT-состояния — не место в очереди.
    if reg.status not in (RegStatus.CONFIRMED, RegStatus.ATTENDED):
        return ScanResponse(
            ok=False, status="cancelled",
            user_name=user_name, event_title=event_title,
            attended_at=None,
            error=f"Запись не подтверждена (статус: {reg.status}).",
        )

    # Лимит проходов: 0 = безлимит, иначе сравниваем с entries_count.
    max_entries = event.max_entries if event else 1
    used = reg.entries_count or 0
    if max_entries and used >= max_entries:
        when = reg.last_entry_at.strftime("%H:%M:%S") if reg.last_entry_at else (
            reg.attended_at.strftime("%H:%M:%S") if reg.attended_at else "?"
        )
        return ScanResponse(
            ok=False, status="already_attended",
            user_name=user_name, event_title=event_title, attended_at=when,
            error=(
                f"Лимит проходов исчерпан ({used} из {max_entries}). "
                f"Последний скан в {when}. Повторный вход запрещён."
            ),
        )

    # Пускаем. Первый скан → status=ATTENDED + attended_at. Повторные скани
    # (когда max_entries > 1) — статус остаётся ATTENDED, обновляется only
    # entries_count и last_entry_at.
    now = datetime.now(UTC).replace(tzinfo=None)
    if reg.status == RegStatus.CONFIRMED:
        reg.status = RegStatus.ATTENDED
        reg.attended_at = now
    reg.entries_count = used + 1
    reg.last_entry_at = now
    log_event(
        session,
        event_type=AuditEvent.REGISTRATION_ATTENDED,
        actor_type=AuditActorType.ADMIN,
        organizer_id=organizer.id,
        actor_display=organizer.name or organizer.email,
        entity_type=AuditEntityType.REGISTRATION,
        entity_id=reg.id,
        payload={
            "event_id": event.id if event else None,
            "entries_count": reg.entries_count,
        },
    )
    user_wants_notify = user.notifications_enabled if user is not None else False
    reg_wants_notify = reg.notifications_enabled
    session.commit()

    # «Спасибо за визит» — только при первом проходе, чтобы не спамить
    # повторными уведомлениями того же гостя.
    if used == 0 and user is not None and user_wants_notify and reg_wants_notify:
        try:
            await send_text(chat_id=user.chat_id, text=ATTENDANCE_CONFIRMED)
        except Exception:
            pass

    extra = ""
    if max_entries == 0:
        extra = f" (проход №{reg.entries_count}, без ограничений)"
    elif max_entries > 1:
        extra = f" (проход {reg.entries_count} из {max_entries})"
    return ScanResponse(
        ok=True, status="ok",
        user_name=user_name + extra,
        event_title=event_title,
        attended_at=None,
        error=None,
    )
