"""Импорт событий из внешних систем вуза (priem.mirea.ru, ИС МИРЭА, 1С).

Принципы:

* **Идемпотентность**. Идентификатор события во внешней системе
  (`external_source` + `external_id`) — единственный ключ для upsert'а.
  Повторный POST того же batch'а даёт `action=updated` без дубликатов.

* **Per-item обработка**. Один невалидный элемент не валит весь batch.
  Возвращаем структурированный отчёт со статусом для каждого события.

* **Safe-mode по умолчанию**. Новые события приходят как `draft`,
  оператор их проверяет и публикует вручную. Поведение переопределяется
  флагом ключа (`auto_publish`) или явным полем запроса.

* **Мульти-tenant сохраняется**. Все события привязываются к организатору,
  который владеет API-ключом. Сменили ключ — новые события идут другому
  организатору, старые остаются у прежнего владельца.

* **Soft cancel**. Этот сервис никогда не удаляет события. Если внешняя
  система перестала их слать — они остаются в БД (могут уже быть записи).
  Закрытие — отдельным эндпоинтом `/events/{id}/status` с `cancelled`.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Event, EventStatus, IntegrationKey, Organizer
from app.schemas.integration import (
    EventSyncItem,
    EventSyncRequest,
    EventSyncResponse,
    EventSyncResultItem,
    EventSyncSummary,
)

logger = logging.getLogger(__name__)


def sync_events_batch(
    session: Session,
    *,
    integration_key: IntegrationKey,
    organizer: Organizer,
    request: EventSyncRequest,
) -> EventSyncResponse:
    """Импортирует batch событий из внешней системы.

    Параметры:
        session: открытая SQLAlchemy-сессия. Сервис делает flush после
            каждого upsert'а, чтобы получить `event.id` для ответа,
            но commit делает вызывающий (роутер).
        integration_key: проверенный API-ключ (содержит source и
            organizer-владельца).
        organizer: организатор, которому будут принадлежать события.
            Должен совпадать с `integration_key.organizer_id`.
        request: payload — список событий + опциональный override
            на auto_publish.

    Возвращает:
        EventSyncResponse — структурированная сводка с per-item статусом.
        Не raises на per-item ошибках; raises только на критических
        проблемах сессии (упадёт сам SQLAlchemy).
    """
    # Auto-publish: явный override в запросе > настройка ключа.
    auto_publish = (
        request.auto_publish
        if request.auto_publish is not None
        else integration_key.auto_publish
    )
    target_status = (
        EventStatus.PUBLISHED if auto_publish else EventStatus.DRAFT
    )

    results: list[EventSyncResultItem] = []
    summary = EventSyncSummary()

    for item in request.events:
        try:
            action, internal_id = _upsert_event(
                session,
                source=integration_key.source,
                organizer_id=organizer.id,
                item=item,
                target_status=target_status,
            )
        except ValueError as exc:
            # Бизнес-валидация (например, конфликт капасити). Per-item.
            results.append(EventSyncResultItem(
                external_id=item.external_id,
                internal_id=None,
                action="failed",
                error=str(exc),
            ))
            summary.failed += 1
            continue
        except IntegrityError as exc:
            # Если БД вернула constraint — откатываем эту операцию и
            # продолжаем с остальными.
            session.rollback()
            logger.warning(
                "sync: IntegrityError на %s/%s: %s",
                integration_key.source, item.external_id, exc,
            )
            results.append(EventSyncResultItem(
                external_id=item.external_id,
                internal_id=None,
                action="failed",
                error="конфликт уникальности — проверьте deeplink_payload",
            ))
            summary.failed += 1
            continue

        results.append(EventSyncResultItem(
            external_id=item.external_id,
            internal_id=internal_id,
            action=action,
            error=None,
        ))
        if action == "created":
            summary.created += 1
        elif action == "updated":
            summary.updated += 1
        else:
            summary.skipped += 1

    # Аудит использования ключа.
    integration_key.last_used_at = datetime.now(UTC)
    integration_key.total_synced += summary.created + summary.updated
    session.flush()

    return EventSyncResponse(
        source=integration_key.source,
        received=len(request.events),
        results=results,
        summary=summary,
    )


def _upsert_event(
    session: Session,
    *,
    source: str,
    organizer_id: int,
    item: EventSyncItem,
    target_status: str,
) -> tuple[str, int]:
    """Один upsert. Возвращает (action, event.id)."""
    existing = session.scalar(
        select(Event).where(
            Event.external_source == source,
            Event.external_id == item.external_id,
        )
    )

    # Заполняем ends_at, если внешняя система не дала.
    ends_at = item.ends_at
    if ends_at is None and item.duration_minutes:
        ends_at = item.starts_at + timedelta(minutes=item.duration_minutes)

    if existing is None:
        event = Event(
            title=item.title,
            description=item.description,
            event_type=item.event_type,
            starts_at=item.starts_at,
            ends_at=ends_at,
            location=item.location,
            cover_url=item.cover_url,
            capacity=item.capacity,
            duration_minutes=item.duration_minutes,
            format=item.format,
            requirements=item.requirements,
            cancellation_terms=item.cancellation_terms,
            meeting_url=item.meeting_url,
            late_cancel_policy=item.late_cancel_policy,
            max_entries=item.max_entries,
            organizer_id=organizer_id,
            status=target_status,
            external_source=source,
            external_id=item.external_id,
            external_url=item.external_url,
        )
        session.add(event)
        session.flush()
        return "created", event.id

    # Update — обновляем только то, что пришло; не трогаем status,
    # если событие уже было опубликовано/отменено вручную оператором
    # (внешняя система не должна откатывать ручные решения).
    existing.title = item.title
    existing.description = item.description
    existing.event_type = item.event_type
    existing.starts_at = item.starts_at
    existing.ends_at = ends_at
    existing.location = item.location
    existing.cover_url = item.cover_url
    existing.capacity = item.capacity
    existing.duration_minutes = item.duration_minutes
    existing.format = item.format
    existing.requirements = item.requirements
    existing.cancellation_terms = item.cancellation_terms
    existing.meeting_url = item.meeting_url
    existing.late_cancel_policy = item.late_cancel_policy
    existing.max_entries = item.max_entries
    existing.external_url = item.external_url
    # status НЕ трогаем — это решение оператора.
    session.flush()
    return "updated", existing.id
