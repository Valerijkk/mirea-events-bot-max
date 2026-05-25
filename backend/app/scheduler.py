"""Планировщик задач: напоминания за 24 часа и за 1 час до начала.

Архитектура простая и предсказуемая:

1. При успешной записи `schedule_reminders_for_registration` создаёт две
   строки в таблице `reminders` (по одной на каждый тип напоминания).
2. APScheduler раз в минуту вызывает `process_due_reminders`, который
   выбирает строки с `sent=False` и `remind_at <= now()` и отправляет.
3. После отправки строка помечается `sent=True` — повторно она не уйдёт.

Когда трафик вырастет (>500 рассылок в минуту), эту схему легко заменить
на Celery + Redis или ARQ без изменения API сервисов — достаточно
переписать `process_due_reminders` и `start_scheduler`.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.bot.notifications import send_text
from app.bot.texts import REMINDER_DAY_BEFORE, REMINDER_HOUR_BEFORE
from app.db import session_scope
from app.models import (
    AuditActorType,
    AuditEntityType,
    AuditEvent,
    Event,
    EventStatus,
    Registration,
    RegStatus,
    Reminder,
    User,
)
from app.services.audit import log_event

logger = logging.getLogger(__name__)

# Таймзона нужна только для расписания (если будут cron-таски). Сравнения
# remind_at/now ведутся в naive UTC — колонка DateTime без tzinfo.
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


def schedule_reminders_for_registration(registration_id: int, event_starts_at: datetime) -> None:
    """Запланировать две напоминалки для одной записи.

    Если функция вызывается повторно (например, после повторной записи) —
    «незакрытые» старые напоминания удаляются, чтобы не было дублей.
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_scope() as session:
        # Сносим неотправленные старые напоминания этой регистрации.
        existing = session.scalars(
            select(Reminder).where(Reminder.registration_id == registration_id)
        ).all()
        for old in existing:
            if not old.sent:
                session.delete(old)

        day_before = event_starts_at - timedelta(hours=24)
        hour_before = event_starts_at - timedelta(hours=1)

        # Создаём напоминания только если время ещё впереди — иначе бессмысленно.
        if day_before > now:
            session.add(Reminder(registration_id=registration_id, remind_at=day_before, kind="day_before"))
        if hour_before > now:
            session.add(Reminder(registration_id=registration_id, remind_at=hour_before, kind="hour_before"))


async def process_due_reminders() -> None:
    """Пройтись по всем «созревшим» напоминаниям и отправить их."""
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_scope() as session:
        due = list(
            session.scalars(
                select(Reminder).where(Reminder.remind_at <= now, Reminder.sent.is_(False))
            )
        )

        for reminder in due:
            if (now - reminder.remind_at).total_seconds() > 300:
                log_event(
                    session,
                    event_type=AuditEvent.REMINDER_STALE_SKIPPED,
                    actor_type=AuditActorType.SYSTEM,
                    entity_type=AuditEntityType.REGISTRATION,
                    entity_id=reminder.registration_id,
                    payload={"reminder_id": reminder.id, "kind": reminder.kind},
                )
                reminder.sent = True
                reminder.sent_at = now
                continue

            reg = session.get(Registration, reminder.registration_id)
            # Запись отменили после планирования — гасим напоминание молча.
            if reg is None or reg.status != RegStatus.CONFIRMED:
                reminder.sent = True
                reminder.sent_at = now
                continue

            event = session.get(Event, reg.event_id)
            user = session.get(User, reg.user_id)
            # Не шлём, если:
            # * мероприятие отменено — иначе абитуриент придёт к закрытым дверям;
            # * пользователь глобально отключил уведомления (`/notify_off`);
            # * пользователь отключил уведомления именно по этой записи
            #   (ТЗ §«Пользовательский процесс»: per-event тоггл).
            if (
                event is None
                or event.status == EventStatus.CANCELLED
                or user is None
                or not user.notifications_enabled
                or not reg.notifications_enabled
            ):
                reminder.sent = True
                reminder.sent_at = now
                continue

            if reminder.kind == "day_before":
                text = REMINDER_DAY_BEFORE.format(
                    title=event.title,
                    location=event.location or "—",
                    time_str=event.starts_at.strftime("%H:%M"),
                )
            elif reminder.kind == "hour_before":
                text = REMINDER_HOUR_BEFORE.format(
                    title=event.title,
                    location=event.location or "—",
                )
            else:
                # Неизвестный тип — пропускаем, чтобы оно не зависало в очереди.
                reminder.sent = True
                reminder.sent_at = now
                continue

            delivered = await send_text(chat_id=user.chat_id, text=text)
            reminder.sent = True
            reminder.sent_at = now
            if delivered:
                log_event(
                    session,
                    event_type=AuditEvent.REMINDER_SENT,
                    actor_type=AuditActorType.SYSTEM,
                    entity_type=AuditEntityType.REGISTRATION,
                    entity_id=reg.id,
                    payload={
                        "reminder_id": reminder.id,
                        "kind": reminder.kind,
                        "event_id": event.id,
                    },
                )
            if not delivered:
                # Логируем для оператора, но не ретраим — иначе риск спама,
                # если пользователь заблокировал бота.
                logger.warning("Напоминание %s не доставлено пользователю %s", reminder.id, user.max_user_id)


def start_scheduler() -> None:
    """Включить тик планировщика. Безопасно вызывать повторно."""
    if scheduler.running:
        return
    scheduler.add_job(
        process_due_reminders,
        trigger="interval",
        minutes=1,
        id="reminders_tick",
        replace_existing=True,
        # max_instances=1 — гарантия, что предыдущий тик закончится,
        # прежде чем стартует следующий.
        max_instances=1,
    )
    scheduler.start()
    logger.info("APScheduler started")


def stop_scheduler() -> None:
    """Корректно остановить планировщик при завершении приложения."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
