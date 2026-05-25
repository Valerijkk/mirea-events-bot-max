"""Хендлеры MAX-бота.

Обращения к БД — через короткие `session_scope`: значения снимаем в
локальные переменные до закрытия сессии, иначе SQLAlchemy упадёт на
lazy-loading во время сетевого вызова к MAX.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.bot.client import (
    MaxClient,
    get_bot_started_payload,
    get_callback_id,
    get_callback_payload,
    get_chat_id,
    get_message_text,
    get_user_id,
    get_user_name,
    get_user_username,
)
from app.bot.instance import dp
from app.bot.keyboards import (
    calendar_link_kb,
    cancel_confirm_kb,
    consent_kb,
    event_card_kb,
    events_list_kb,
    main_menu_kb,
    my_registration_kb,
    signup_summary_kb,
    slot_picker_kb,
)
from app.bot.notifications import send_photo, send_text
from app.bot.texts import (
    BTN,
    CANCEL_CONFIRM,
    CANCEL_DONE,
    CANCEL_DONE_WITH_PROMOTION,
    CANCEL_KEEP,
    CANCEL_NOT_FOUND,
    ASK_NAME,
    CONSENT_REQUEST,
    CONSENT_REQUIRED,
    DISCLAIMER,
    NAME_SAVED,
    EVENT_CANCELLATION_TERMS,
    EVENT_CARD,
    EVENT_DETAILS_EXTRA,
    EVENT_FULL_CARD_SUFFIX,
    EVENT_LIST_HEADER,
    EVENT_NOT_FOUND,
    EVENT_REGISTRATION_CLOSED_SUFFIX,
    HELP,
    LATE_CANCEL_DONE,
    LATE_CANCEL_FORBIDDEN,
    MY_EMPTY,
    MY_HEADER,
    MY_ITEM_ATTENDED,
    MY_ITEM_CANCELLED,
    MY_ITEM_CONFIRMED,
    MY_ITEM_WAITLIST,
    NO_EVENTS,
    NOTIFY_OFF_DONE,
    NOTIFY_ON_DONE,
    REG_ALREADY,
    REG_CONFIRMED,
    REG_NOTIFICATION_TOGGLED_OFF,
    REG_NOTIFICATION_TOGGLED_ON,
    REG_WAITLIST,
    SIGNUP_SUMMARY,
    SLOT_PICKER_HEADER,
    UNKNOWN,
    WAITLIST_PROMOTED,
    WELCOME,
)
from app.core.formatting import format_event_dt
from app.db import session_scope
from app.models import (
    AuditActorType,
    AuditEntityType,
    AuditEvent,
    Event,
    EventFormat,
    EventStatus,
    EventType,
    Registration,
    RegStatus,
    User,
)
from app.scheduler import schedule_reminders_for_registration
from app.services.audit import log_event
from app.services.consent import grant_consent, has_active_consent
from app.services.qr import generate_qr
from app.services.registration import (
    cancel_registration,
    get_active_events,
    get_event_by_payload,
    get_user_registrations,
    sign_up,
    upsert_user,
)
from app.services.slots import upcoming_slots_with_capacity

_EVENT_TYPE_LABELS: dict[str, str] = {
    EventType.OPEN_DAY: "🏛 День открытых дверей",
    EventType.MASTERCLASS: "🛠 Мастер-класс",
    EventType.OLYMPIAD: "🏆 Олимпиада",
    EventType.TOUR: "🚶 Экскурсия",
    EventType.CONSULTATION: "💬 Консультация",
    EventType.OTHER: "🎓 Мероприятие",
}

logger = logging.getLogger(__name__)

# user_id-ы, ожидающие ввода ФИО после согласия (in-memory, живёт до перезапуска)
_AWAITING_NAME: set[int] = set()


def _is_valid_fio(text: str) -> bool:
    """Проверяет, что строка — полное ФИО: ровно 3 слова, каждое с заглавной буквы.

    Допускаем дефис внутри слова (Иванов-Петров), апостроф (О'Брайен).
    Только кириллица и латиница.
    """
    import re
    parts = text.split()
    if len(parts) < 3:
        return False
    pattern = re.compile(r"^[А-ЯЁA-Z][а-яёa-zА-ЯЁA-Z'\-]+$")
    return all(pattern.match(p) for p in parts)


@dp.on("bot_started")
async def on_bot_started(update: dict, client: MaxClient) -> None:
    user_id = get_user_id(update)
    chat_id = get_chat_id(update) or user_id
    payload = get_bot_started_payload(update)
    name = get_user_name(update)
    username = get_user_username(update)

    if user_id is None:
        logger.warning("bot_started без user_id: %s", update)
        return

    with session_scope() as session:
        upsert_user(
            session,
            max_user_id=user_id,
            chat_id=chat_id or user_id,
            name=name,
            username=username,
        )
        consent_ok = has_active_consent(session, user_id)

    # ТЗ §«Пользовательский процесс»: дисклеймер+согласие перед каталогом.
    if not consent_ok:
        await _show_consent_screen(client, user_id, pending_payload=payload)
        return

    if payload and payload.startswith("event_"):
        await _show_event_by_payload(client, user_id, payload)
    else:
        await client.send_message(text=WELCOME, user_id=user_id, attachments=[main_menu_kb()])


async def _show_consent_screen(
    client: MaxClient, user_id: int, *, pending_payload: str | None = None
) -> None:
    """Welcome+дисклеймер+согласие одним сообщением (вместо стены из трёх).

    Если пришёл deeplink event_xxx — сохраняем в БД, чтобы применить после
    клика «Я согласен» (иначе теряется точка входа с афиши/QR-кода).
    """
    if pending_payload and pending_payload.startswith("event_"):
        with session_scope() as session:
            user = session.get(User, user_id)
            if user is not None:
                user.pending_deeplink_payload = pending_payload

    await client.send_message(
        text=CONSENT_REQUEST, user_id=user_id, attachments=[consent_kb()]
    )


@dp.on("message_created")
async def on_message(update: dict, client: MaxClient) -> None:
    user_id = get_user_id(update)
    if user_id is None:
        return
    text = (get_message_text(update) or "").strip()

    # Ожидаем ввод ФИО после согласия на обработку персданных
    if user_id in _AWAITING_NAME:
        _AWAITING_NAME.discard(user_id)
        fio = text.strip()
        if not fio or fio.startswith("/") or not _is_valid_fio(fio):
            _AWAITING_NAME.add(user_id)
            await client.send_message(
                text=(
                    "❌ Некорректное ФИО.\n\n"
                    "Нужно ввести *полное* ФИО — три слова, каждое с заглавной буквы.\n"
                    "Например: *Иванов Иван Иванович*"
                ),
                user_id=user_id,
            )
            return
        # Сохраняем ФИО и продолжаем к афише
        pending = None
        with session_scope() as session:
            user = session.get(User, user_id)
            if user is not None:
                user.name = fio
                pending = user.pending_deeplink_payload
                user.pending_deeplink_payload = None
        await client.send_message(
            text=NAME_SAVED.format(name=fio),
            user_id=user_id,
            attachments=[main_menu_kb()],
        )
        if pending and pending.startswith("event_"):
            await _show_event_by_payload(client, user_id, pending)
        else:
            await _show_events_list(client, user_id)
        return

    # /start (включая deeplink: "/start event_<payload>")
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""
        name = get_user_name(update)
        username = get_user_username(update)
        with session_scope() as session:
            upsert_user(
                session,
                max_user_id=user_id,
                chat_id=user_id,
                name=name,
                username=username,
            )
            consent_ok = has_active_consent(session, user_id)

        if not consent_ok:
            await _show_consent_screen(client, user_id, pending_payload=payload)
            return

        if payload.startswith("event_"):
            await _show_event_by_payload(client, user_id, payload)
        else:
            await client.send_message(text=WELCOME, user_id=user_id, attachments=[main_menu_kb()])
        return

    if text == "/help":
        await client.send_message(text=HELP, user_id=user_id, attachments=[main_menu_kb()])
        return

    # ТЗ: дисклеймер должен быть доступен в любой момент.
    if text == "/about":
        await client.send_message(text=DISCLAIMER, user_id=user_id, attachments=[main_menu_kb()])
        return

    if text == "/notify_off":
        _set_notifications(user_id, enabled=False)
        await client.send_message(text=NOTIFY_OFF_DONE, user_id=user_id, attachments=[main_menu_kb()])
        return
    if text == "/notify_on":
        _set_notifications(user_id, enabled=True)
        await client.send_message(text=NOTIFY_ON_DONE, user_id=user_id, attachments=[main_menu_kb()])
        return

    # Текстовые кнопки главного меню (если рендерили reply-стиль).
    if text == BTN.EVENTS:
        await _show_events_list(client, user_id)
        return
    if text == BTN.MY:
        await _show_my_registrations(client, user_id)
        return
    if text == BTN.HELP:
        await client.send_message(text=HELP, user_id=user_id, attachments=[main_menu_kb()])
        return

    await client.send_message(text=UNKNOWN, user_id=user_id, attachments=[main_menu_kb()])


def _set_notifications(user_id: int, *, enabled: bool) -> None:
    with session_scope() as session:
        user = session.get(User, user_id)
        if user is not None:
            user.notifications_enabled = enabled


@dp.on("message_callback")
async def on_callback(update: dict, client: MaxClient) -> None:
    user_id = get_user_id(update)
    payload = get_callback_payload(update)

    callback_id = get_callback_id(update)
    if callback_id:
        try:
            await client.answer_callback(callback_id)
        except Exception:
            logger.warning("answer_callback failed for %s", callback_id)

    if user_id is None or payload is None:
        logger.warning("message_callback без user_id/payload: %s", update)
        return

    if payload == "noop":
        return

    # TODO: заменить if-chain на _CALLBACK_ROUTES dict (см. code-review замечание)

    # Согласие проверяем до всех остальных callback'ов.
    if payload == "consent":
        with session_scope() as session:
            grant_consent(session, user_id)
            # pending_deeplink_payload НЕ сбрасываем — применим после сбора ФИО.

        # После согласия запрашиваем ФИО (ФЗ-152: фиксируем субъекта данных).
        _AWAITING_NAME.add(user_id)
        await client.send_message(text=ASK_NAME, user_id=user_id)
        return

    if not _ensure_consent(user_id):
        await client.send_message(text=CONSENT_REQUIRED, user_id=user_id)
        await _show_consent_screen(client, user_id)
        return

    if payload == "menu":
        await client.send_message(text=WELCOME, user_id=user_id, attachments=[main_menu_kb()])
        return
    if payload == "events":
        await _show_events_list(client, user_id)
        return
    if payload == "my":
        await _show_my_registrations(client, user_id)
        return
    if payload == "help":
        await client.send_message(text=HELP, user_id=user_id, attachments=[main_menu_kb()])
        return

    if payload.startswith("event:"):
        await _show_event_by_id(client, user_id, int(payload.split(":", 1)[1]))
        return

    if payload.startswith("details:"):
        await _show_event_details(client, user_id, int(payload.split(":", 1)[1]))
        return

    if payload.startswith(("signup:", "waitlist:")):
        # Сначала сводка/выбор слота — запись создаём только в confirm:.
        await _start_signup_flow(client, user_id, int(payload.split(":", 1)[1]))
        return

    if payload.startswith("slot:"):
        # slot:<event_id>:<slot_id>
        _, event_id_s, slot_id_s = payload.split(":", 2)
        await _show_signup_summary(client, user_id, int(event_id_s), int(slot_id_s))
        return

    if payload.startswith("confirm:"):
        parts = payload.split(":")
        event_id = int(parts[1])
        slot_id = int(parts[2]) if len(parts) > 2 else None
        await _do_signup(client, user_id, event_id, slot_id=slot_id)
        return

    if payload.startswith("cancel:"):
        registration_id = int(payload.split(":", 1)[1])
        with session_scope() as session:
            reg = session.get(Registration, registration_id)
            if reg is None or reg.user_id != user_id:
                await client.send_message(text=CANCEL_NOT_FOUND, user_id=user_id)
                return
            event_title = reg.event.title
        await client.send_message(
            text=CANCEL_CONFIRM.format(title=event_title),
            user_id=user_id,
            attachments=[cancel_confirm_kb(registration_id)],
        )
        return

    if payload.startswith("cancel_yes:"):
        await _do_cancel(client, user_id, int(payload.split(":", 1)[1]))
        return

    if payload.startswith("cancel_no:"):
        await client.send_message(text=CANCEL_KEEP, user_id=user_id, attachments=[main_menu_kb()])
        return

    if payload.startswith("qr:"):
        await _resend_qr(client, user_id, int(payload.split(":", 1)[1]))
        return

    if payload.startswith("notif_off:"):
        await _toggle_reg_notifications(client, user_id, int(payload.split(":", 1)[1]), enabled=False)
        return

    if payload.startswith("notif_on:"):
        await _toggle_reg_notifications(client, user_id, int(payload.split(":", 1)[1]), enabled=True)
        return

    if payload.startswith("ics:"):
        await _send_ics(client, user_id, int(payload.split(":", 1)[1]))
        return

    logger.info("Unknown callback payload: %s", payload)


def _ensure_consent(user_id: int) -> bool:
    with session_scope() as session:
        return has_active_consent(session, user_id)


async def _toggle_reg_notifications(
    client: MaxClient, user_id: int, registration_id: int, *, enabled: bool
) -> None:
    with session_scope() as session:
        reg = session.get(Registration, registration_id)
        if reg is None or reg.user_id != user_id:
            await client.send_message(text=CANCEL_NOT_FOUND, user_id=user_id)
            return
        reg.notifications_enabled = enabled
    text = REG_NOTIFICATION_TOGGLED_ON if enabled else REG_NOTIFICATION_TOGGLED_OFF
    await client.send_message(text=text, user_id=user_id)


async def _show_events_list(client: MaxClient, user_id: int) -> None:
    with session_scope() as session:
        events = get_active_events(session)
        if not events:
            await client.send_message(text=NO_EVENTS, user_id=user_id, attachments=[main_menu_kb()])
            return
        snapshot = [(e.id, e.title) for e in events]

    fake = [type("E", (), {"id": eid, "title": title}) for eid, title in snapshot]
    await client.send_message(
        text=EVENT_LIST_HEADER,
        user_id=user_id,
        attachments=[events_list_kb(fake)],
    )


async def _show_event_by_payload(client: MaxClient, user_id: int, payload: str) -> None:
    with session_scope() as session:
        event = get_event_by_payload(session, payload)
        if event is None:
            await client.send_message(text=EVENT_NOT_FOUND, user_id=user_id, attachments=[main_menu_kb()])
            return
        await _send_event_card(client, user_id, event)


async def _show_event_by_id(client: MaxClient, user_id: int, event_id: int) -> None:
    with session_scope() as session:
        event = session.get(Event, event_id)
        if event is None:
            await client.send_message(text=EVENT_NOT_FOUND, user_id=user_id, attachments=[main_menu_kb()])
            return
        await _send_event_card(client, user_id, event)


def _format_duration(event: Event) -> str:
    """Явный `duration_minutes`, иначе считаем по `ends_at - starts_at`."""
    from app.core.formatting import format_duration_minutes
    minutes = event.duration_minutes
    if minutes is None and event.ends_at is not None:
        minutes = int((event.ends_at - event.starts_at).total_seconds() // 60)
    return format_duration_minutes(minutes)


def _format_event_format(event: Event) -> str:
    if event.format == EventFormat.ONLINE:
        return "💻 Онлайн" + (f" — {event.meeting_url}" if event.meeting_url else "")
    return "📍 Очно — " + (event.location or "адрес уточняется")


async def _send_event_card(
    client: MaxClient, user_id: int, event: Event, *, show_details: bool = False
) -> None:
    """`show_details=True` — режим «Подробнее» (ТЗ §«Пользовательский процесс»)."""
    free = event.free_slots()
    type_label = _EVENT_TYPE_LABELS.get(event.event_type, _EVENT_TYPE_LABELS[EventType.OTHER])
    text = type_label + "\n\n" + EVENT_CARD.format(
        title=event.title,
        description=event.description or "",
        date_str=format_event_dt(event.starts_at),
        duration=_format_duration(event),
        format_line=_format_event_format(event),
        free=free,
        capacity=event.total_capacity(),
    )

    if show_details:
        if event.requirements:
            text += EVENT_DETAILS_EXTRA.format(requirements=event.requirements)
        if event.cancellation_terms:
            text += EVENT_CANCELLATION_TERMS.format(terms=event.cancellation_terms)

    # ТЗ: статус «Регистрация закрыта».
    if not event.registration_open:
        text += EVENT_REGISTRATION_CLOSED_SUFFIX
    elif free == 0:
        text += EVENT_FULL_CARD_SUFFIX

    attachments: list[dict] = []
    if event.cover_url:
        attachments.append({"type": "image", "payload": {"url": event.cover_url}})
    attachments.append(
        event_card_kb(
            event.id,
            has_free_slots=free > 0,
            registration_open=event.registration_open and event.can_accept_registrations(),
            show_details_button=not show_details,
        )
    )

    await client.send_message(text=text, user_id=user_id, attachments=attachments)


async def _show_event_details(client: MaxClient, user_id: int, event_id: int) -> None:
    with session_scope() as session:
        event = session.get(Event, event_id)
        if event is None:
            await client.send_message(text=EVENT_NOT_FOUND, user_id=user_id)
            return
        await _send_event_card(client, user_id, event, show_details=True)


async def _start_signup_flow(client: MaxClient, user_id: int, event_id: int) -> None:
    """ТЗ §«Пользовательский процесс»: запись создаём только в confirm:."""
    with session_scope() as session:
        event = session.get(Event, event_id)
        if event is None:
            await client.send_message(text=EVENT_NOT_FOUND, user_id=user_id)
            return
        if not event.can_accept_registrations():
            # Старый callback — организатор уже закрыл регистрацию.
            await _send_event_card(client, user_id, event)
            return
        has_slots = event.has_slots()
        if has_slots:
            slots_data = upcoming_slots_with_capacity(session, event_id)
            # Захватываем локально — после выхода из сессии станут detached.
            slot_rows = list(slots_data)
        else:
            slot_rows = []

    if has_slots:
        if not slot_rows:
            await client.send_message(text=EVENT_NOT_FOUND, user_id=user_id)
            return
        await client.send_message(
            text=SLOT_PICKER_HEADER,
            user_id=user_id,
            attachments=[slot_picker_kb(event_id, slot_rows)],
        )
    else:
        await _show_signup_summary(client, user_id, event_id, slot_id=None)


async def _show_signup_summary(
    client: MaxClient, user_id: int, event_id: int, slot_id: int | None
) -> None:
    """Сводка перед подтверждением (ТЗ §«Пользовательский процесс»)."""
    with session_scope() as session:
        event = session.get(Event, event_id)
        if event is None:
            await client.send_message(text=EVENT_NOT_FOUND, user_id=user_id)
            return
        slot_line = ""
        if slot_id is not None:
            from app.models import EventSlot
            slot = session.get(EventSlot, slot_id)
            if slot is None or slot.event_id != event_id:
                await client.send_message(text=EVENT_NOT_FOUND, user_id=user_id)
                return
            label = slot.label or format_event_dt(slot.starts_at)
            slot_line = f"🕒 Слот: {label}\n"
        text = SIGNUP_SUMMARY.format(
            title=event.title,
            date_str=format_event_dt(event.starts_at),
            slot_line=slot_line,
            format_line=_format_event_format(event),
        )

    await client.send_message(
        text=text,
        user_id=user_id,
        attachments=[signup_summary_kb(event_id, slot_id)],
    )


_SIGNUP_ERROR_MESSAGES = {
    "event is not published": "🚫 Мероприятие не опубликовано или недоступно для записи.",
    "registration closed": "🚫 Регистрация на это мероприятие закрыта.",
    "capacity reached": "🚫 К сожалению, все места заняты.",
    "already registered": "🚫 Вы уже зарегистрированы на это мероприятие.",
}


async def _do_signup(
    client: MaxClient,
    user_id: int,
    event_id: int,
    *,
    slot_id: int | None = None,
) -> None:
    """Двойной тап на «Подтверждаю» гасится двумя слоями:
    1) `sign_up` идемпотентен по `(event_id, user_id)` → already_registered=True;
    2) `IntegrityError` на uq_reg_event_user — fallback от гонки между процессами.
    """
    from sqlalchemy.exc import IntegrityError

    with session_scope() as session:
        try:
            result = sign_up(
                session, event_id=event_id, user_id=user_id, slot_id=slot_id
            )
        except ValueError as e:
            # Состояние мероприятия изменилось между сводкой и confirm.
            msg = _SIGNUP_ERROR_MESSAGES.get(str(e).lower())
            if msg is None:
                msg = "🚫 Не удалось записаться. Попробуйте позже."
            await client.send_message(text=msg, user_id=user_id)
            return
        except IntegrityError:
            # Гонка на uq_reg_event_user между параллельными запросами.
            await client.send_message(text=REG_ALREADY, user_id=user_id)
            return

        if result.already_registered:
            await client.send_message(text=REG_ALREADY, user_id=user_id)
            return

        event = session.get(Event, event_id)
        reg = result.registration
        user = session.get(User, user_id)
        actor_display = (user.name if user else None) or (user.username if user else None)
        log_event(
            session,
            event_type=(
                AuditEvent.WAITLIST_JOINED if result.is_waitlist else AuditEvent.REGISTRATION_CREATED
            ),
            actor_type=AuditActorType.USER,
            user_id=user_id,
            actor_display=actor_display,
            entity_type=AuditEntityType.REGISTRATION,
            entity_id=reg.id,
            payload={"event_id": event_id, "slot_id": slot_id},
        )
        reg_id = reg.id
        reg_code = reg.code
        qr_token = reg.qr_token
        ev_title = event.title  # type: ignore[union-attr]
        ev_location = event.location or "—"  # type: ignore[union-attr]
        # Для слотов reminders считаем от времени слота, а не от события
        # в целом — иначе напоминание придёт к чужому времени.
        if reg.slot is not None:
            ev_date = reg.slot.starts_at
            ev_starts_at = reg.slot.starts_at
        else:
            ev_date = event.starts_at  # type: ignore[union-attr]
            ev_starts_at = event.starts_at  # type: ignore[union-attr]

    if result.is_waitlist:
        await client.send_message(
            text=REG_WAITLIST.format(
                title=ev_title,
                date_str=format_event_dt(ev_date),
                position=result.waitlist_position,
            ),
            user_id=user_id,
            attachments=[main_menu_kb()],
        )
        return

    caption = REG_CONFIRMED.format(
        title=ev_title,
        date_str=format_event_dt(ev_date),
        location=ev_location,
        code=reg_code,
    )
    await client.send_message(text=caption, user_id=user_id, attachments=[main_menu_kb()])
    # QR отдельным сообщением, чтобы код можно было скопировать из текста.
    qr_path = generate_qr(qr_token)
    await send_photo(chat_id=user_id, photo_path=qr_path, caption=None)
    schedule_reminders_for_registration(reg_id, ev_starts_at)


async def _do_cancel(client: MaxClient, user_id: int, registration_id: int) -> None:
    """Late-cancel policy:
    * `forbidden_late` → политика DISALLOW, отмена запрещена;
    * `late` → место в пул не возвращаем;
    * иначе — промотируем следующего из waitlist и шлём ему QR.
    """
    with session_scope() as session:
        result = cancel_registration(session, registration_id, user_id)
        if result.cancelled:
            reg = session.get(Registration, registration_id)
            user = session.get(User, user_id)
            actor_display = (user.name if user else None) or (user.username if user else None)
            log_event(
                session,
                event_type=AuditEvent.REGISTRATION_CANCELLED,
                actor_type=AuditActorType.USER,
                user_id=user_id,
                actor_display=actor_display,
                entity_type=AuditEntityType.REGISTRATION,
                entity_id=registration_id,
                payload={
                    "event_id": reg.event_id if reg else None,
                    "late": result.late,
                },
            )
        promoted_data = None
        if result.cancelled and result.promoted_registration is not None:
            p = result.promoted_registration
            promoted_data = {
                "user_id": p.user_id,
                "reg_id": p.id,
                "ev_starts_at": p.event.starts_at,
                "title": p.event.title,
                "date_str": format_event_dt(p.event.starts_at),
                "qr_token": p.qr_token,
                "code": p.code,
            }

    if result.forbidden_late:
        await client.send_message(text=LATE_CANCEL_FORBIDDEN, user_id=user_id)
        return

    if not result.cancelled:
        await client.send_message(text=CANCEL_NOT_FOUND, user_id=user_id)
        return

    if result.late:
        await client.send_message(
            text=LATE_CANCEL_DONE, user_id=user_id, attachments=[main_menu_kb()]
        )
        return

    if promoted_data:
        qr_path = generate_qr(promoted_data["qr_token"])  # type: ignore[arg-type]
        caption = WAITLIST_PROMOTED.format(
            title=promoted_data["title"], date_str=promoted_data["date_str"]
        )
        full_caption = caption + f"\n\n🔢 Код записи: {promoted_data['code']}"
        await send_text(chat_id=promoted_data["user_id"], text=full_caption)  # type: ignore[arg-type]
        await send_photo(
            chat_id=promoted_data["user_id"], photo_path=qr_path, caption=None  # type: ignore[arg-type]
        )
        # Планируем напоминания для promoted-участника (24ч и 1ч до начала)
        schedule_reminders_for_registration(
            promoted_data["reg_id"],  # type: ignore[arg-type]
            promoted_data["ev_starts_at"],  # type: ignore[arg-type]
        )
        await client.send_message(
            text=CANCEL_DONE_WITH_PROMOTION,
            user_id=user_id,
            attachments=[main_menu_kb()],
        )
    else:
        await client.send_message(
            text=CANCEL_DONE, user_id=user_id, attachments=[main_menu_kb()]
        )


async def _resend_qr(client: MaxClient, user_id: int, registration_id: int) -> None:
    """Повторно присылает QR-пропуск пользователю по запросу из «Мои записи»."""
    with session_scope() as session:
        reg = session.get(Registration, registration_id)
        if reg is None or reg.user_id != user_id:
            await client.send_message(text=CANCEL_NOT_FOUND, user_id=user_id)
            return
        if reg.status not in (RegStatus.CONFIRMED, RegStatus.WAITLIST):
            await client.send_message(
                text="🚫 QR доступен только для активных записей.",
                user_id=user_id,
            )
            return
        qr_token = reg.qr_token

    qr_path = generate_qr(qr_token)
    await client.send_message(
        text=f"🎫 Твой QR-пропуск. Покажи его на входе.",
        user_id=user_id,
    )
    await send_photo(chat_id=user_id, photo_path=qr_path, caption=None)



async def _send_ics(client: MaxClient, user_id: int, registration_id: int) -> None:
    """Google Calendar URL вместо .ics: открывается одним тапом на любом устройстве."""
    from app.services.ics import google_calendar_url

    with session_scope() as session:
        reg = session.get(Registration, registration_id)
        if reg is None or reg.user_id != user_id:
            await client.send_message(text="Не нашёл запись.", user_id=user_id)
            return
        event = reg.event
        url = google_calendar_url(event)
        title = event.title
        date_str = format_event_dt(event.starts_at)
        location = event.location or "—"

    text = (
        f"📅 Добавить в календарь\n\n"
        f"🎓 {title}\n"
        f"🗓 {date_str}\n"
        f"📍 {location}\n\n"
        f"Нажмите на ссылку ниже — откроется Google Calendar с готовым событием. "
        f"Жмёте «Сохранить» — и всё, оно в вашем расписании.\n\n"
        f"{url}"
    )
    button = calendar_link_kb(url)
    await client.send_message(text=text, user_id=user_id, attachments=[button])


async def _show_my_registrations(client: MaxClient, user_id: int) -> None:
    """Архив — одним общим сообщением, активные — карточками с кнопками."""
    with session_scope() as session:
        regs = get_user_registrations(session, user_id)
        if not regs:
            await client.send_message(text=MY_EMPTY, user_id=user_id, attachments=[main_menu_kb()])
            return

        items = []
        for r in regs:
            # Мероприятие отменено организатором — клиент видит CANCELLED,
            # даже если запись в БД ещё CONFIRMED/WAITLIST. Иначе вылезла бы
            # кнопка «отменить» для уже отменённого события.
            effective_status = (
                RegStatus.CANCELLED
                if r.event.status == EventStatus.CANCELLED
                else r.status
            )
            when = r.slot.starts_at if r.slot is not None else r.event.starts_at
            items.append(
                {
                    "id": r.id,
                    "title": r.event.title,
                    "date_str": format_event_dt(when),
                    "location": r.event.location or "—",
                    "status": effective_status,
                    "position": r.waitlist_position,
                    "is_past": when < datetime.now(UTC).replace(tzinfo=None),
                    "notifications_enabled": r.notifications_enabled,
                    "code": r.code,
                }
            )

    active = [it for it in items if it["status"] in (RegStatus.CONFIRMED, RegStatus.WAITLIST)]
    archive = [it for it in items if it["status"] not in (RegStatus.CONFIRMED, RegStatus.WAITLIST)]

    if not active and archive:
        lines = [MY_HEADER]
        for it in archive:
            text, _ = _render_my_item(it)
            if text:
                lines.append(text)
        await client.send_message(
            text="\n\n".join(lines), user_id=user_id, attachments=[main_menu_kb()]
        )
        return

    await client.send_message(text=MY_HEADER, user_id=user_id)
    for item in active:
        text, keyboard = _render_my_item(item)
        if text is None:
            continue
        attachments = [keyboard] if keyboard is not None else None
        await client.send_message(text=text, user_id=user_id, attachments=attachments)
    if archive:
        lines = ["📜 Архив:"]
        for it in archive:
            text, _ = _render_my_item(it)
            if text:
                lines.append(text)
        await client.send_message(text="\n\n".join(lines), user_id=user_id)


def _render_my_item(item: dict) -> tuple[str | None, dict | None]:
    """Для активных записей подмешиваем код — его показывают на входе."""
    status_value = item["status"]
    notif_on = item.get("notifications_enabled", True)
    code_line = f"\n🔢 {item['code']}" if item.get("code") else ""

    if status_value == RegStatus.CONFIRMED:
        text = MY_ITEM_CONFIRMED.format(**item) + code_line
        return text, my_registration_kb(
            item["id"], can_cancel=not item["is_past"], notifications_enabled=notif_on
        )
    if status_value == RegStatus.WAITLIST:
        text = MY_ITEM_WAITLIST.format(**item) + code_line
        return text, my_registration_kb(
            item["id"], can_cancel=True, notifications_enabled=notif_on
        )
    if status_value == RegStatus.CANCELLED:
        return MY_ITEM_CANCELLED.format(**item), None
    if status_value == RegStatus.LATE_CANCELLED:
        return "❌ " + item["title"] + " (поздняя отмена)\n📅 " + item["date_str"], None
    if status_value == RegStatus.CANCELLED_BY_ORGANIZER:
        return "📌 " + item["title"] + " (отменено организатором)\n📅 " + item["date_str"], None
    if status_value == RegStatus.ATTENDED:
        return MY_ITEM_ATTENDED.format(**item), None
    return None, None
