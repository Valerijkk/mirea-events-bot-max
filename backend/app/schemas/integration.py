"""DTO для интеграционного bulk-импорта событий из внешних систем вуза.

Формат заточен под структуру событий РТУ МИРЭА (mirea.ru/eventspage/...,
priem.mirea.ru/event/...): дата+время, тип, формат, место, описание,
ссылка на оригинал. Поля сделаны максимально опциональными, чтобы
внешняя система могла слать «как может» — мы доберём дефолтами.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.event import (
    EventFormatLiteral,
    EventTypeLiteral,
    LateCancelPolicyLiteral,
)


class EventSyncItem(BaseModel):
    """Одно событие в batch'е импорта.

    `external_id` обязателен — без него не сможем сделать идемпотентный
    upsert. Остальное опционально: defaults близки к реальной картине
    дней открытых дверей РТУ МИРЭА.
    """

    model_config = ConfigDict(extra="ignore")

    external_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="ID события в системе-источнике. Уникален в пределах источника.",
        examples=["den-otkrytykh-dverey-iit-2026-04-05", "evt-12345"],
    )
    title: str = Field(
        ..., min_length=3, max_length=255,
        description="Название мероприятия.",
        examples=["День открытых дверей всех образовательных программ"],
    )
    description: str | None = Field(None, description="Подробное описание (текст).")
    event_type: EventTypeLiteral = Field(
        "other",
        description="Тип. Маппинг из категорий вуза: дни открытых дверей→open_day, "
                    "олимпиады→olympiad, мастер-классы→masterclass, экскурсии→tour, "
                    "консультации→consultation, иное→other.",
    )
    starts_at: datetime = Field(..., description="Дата и время начала (UTC).")
    ends_at: datetime | None = Field(None, description="Окончание. Если пусто — +2ч от начала.")
    duration_minutes: int | None = Field(None, ge=1, le=1440)
    format: EventFormatLiteral = Field("onsite", description="online / onsite.")
    location: str | None = Field(None, max_length=255,
                                 examples=["пр. Вернадского, 78, главный корпус, актовый зал"])
    meeting_url: str | None = Field(None, max_length=512,
                                     description="Ссылка для online-формата.")
    capacity: int = Field(100, gt=0, le=10000,
                          description="Лимит мест. Если у вуза нет ограничения — ставим 100 (организатор поправит).")
    cover_url: str | None = Field(None, max_length=512, description="URL обложки события.")
    requirements: str | None = Field(None, description="Требования к участникам.")
    cancellation_terms: str | None = Field(None, description="Условия отмены.")
    late_cancel_policy: LateCancelPolicyLiteral = Field("disallow")
    max_entries: int = Field(1, ge=0, le=100)
    external_url: str | None = Field(
        None, max_length=512,
        description="Обратная ссылка на оригинал (для аудита и кнопки «открыть на сайте»).",
        examples=["https://www.mirea.ru/eventspage/den-otkrytykh-dverey-vsekh-obrazovatelnykh-programm11/"],
    )


class EventSyncRequest(BaseModel):
    """Batch для синхронизации.

    `auto_publish` переопределяет дефолт ключа на уровне конкретного
    запроса. Полезно, если внешняя система хочет «сразу опубликовать»
    проверенный набор событий, не ожидая ручной валидации.
    """

    model_config = ConfigDict(extra="ignore")

    auto_publish: bool | None = Field(
        None,
        description="Сразу опубликовать события. Если null — взять из настроек ключа.",
    )
    events: list[EventSyncItem] = Field(
        ..., min_length=1, max_length=500,
        description="События для импорта. Максимум 500 за запрос — для больших каталогов делайте несколько.",
    )


SyncAction = Literal["created", "updated", "skipped", "failed"]


class EventSyncResultItem(BaseModel):
    """Результат обработки одного события из batch'а."""

    external_id: str
    internal_id: int | None = Field(None, description="ID события во внутренней БД (если создано/обновлено).")
    action: SyncAction
    error: str | None = Field(None, description="Текст ошибки для action=failed.")


class EventSyncSummary(BaseModel):
    """Сводка по batch'у."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0


class EventSyncResponse(BaseModel):
    """Ответ ручки /api/v1/integration/events/sync."""

    source: str = Field(..., description="Имя системы-источника (взято из API-ключа).")
    received: int = Field(..., description="Сколько событий пришло в запросе.")
    results: list[EventSyncResultItem]
    summary: EventSyncSummary
