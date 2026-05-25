"""Фабрика payload-ов EventSyncItem для /integration/events/sync."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import factory
from faker import Faker

_fake_ru = Faker("ru_RU")


def _future_isoformat(days_ahead: int = 30) -> str:
    return (datetime.now() + timedelta(days=days_ahead)).replace(microsecond=0).isoformat()


class IntegrationEventFactory(factory.DictFactory):
    external_id = factory.LazyFunction(lambda: f"qa-{uuid.uuid4().hex[:12]}")
    title = factory.LazyFunction(
        lambda: f"Интеграционное событие {_fake_ru.word()} #{uuid.uuid4().hex[:4]}"
    )
    starts_at = factory.LazyFunction(_future_isoformat)
    capacity = 100
    event_type = "open_day"
    format = "onsite"
    location = "корп. А, ауд. 200"


def fixed_external_id(value: str) -> dict[str, Any]:
    # Для теста идемпотентности: фиксируем external_id, чтобы дважды слать одно и то же.
    return IntegrationEventFactory.build(external_id=value)
