"""Фабрика payload-ов EventCreate для POST /api/v1/events."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import Any

import factory
from faker import Faker

_fake_ru = Faker("ru_RU")


def _future_isoformat(days_ahead: int = 21) -> str:
    return (datetime.now() + timedelta(days=days_ahead)).replace(microsecond=0).isoformat()


class EventFactory(factory.DictFactory):
    # title: Faker даёт длинный sentence — отрезаем до 200, плюс UUID для уникальности.
    title = factory.LazyFunction(
        lambda: f"{_fake_ru.sentence(nb_words=4).rstrip('.')[:200]} #{uuid.uuid4().hex[:6]}"
    )
    description = factory.LazyFunction(lambda: _fake_ru.paragraph(nb_sentences=2))
    event_type = "open_day"
    capacity = factory.LazyFunction(lambda: random.randint(20, 200))
    duration_minutes = 90
    format = "onsite"
    location = factory.LazyFunction(lambda: f"ауд. {random.randint(100, 599)}")
    starts_at = factory.LazyFunction(_future_isoformat)

    class Params:
        # Trait-маркеры на случай дополнительных полей.
        online = factory.Trait(
            format="online",
            meeting_url="https://meet.example.com/room-qa",
            location=None,
        )


class EventBuilder:
    # Builder-обёртка: chainable конфигурация — для тестов, где
    # читаемость «с какой capacity билдим» важнее.

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(EventFactory.build())

    def with_title(self, value: str) -> EventBuilder:
        self._data["title"] = value
        return self

    def with_capacity(self, value: int) -> EventBuilder:
        self._data["capacity"] = value
        return self

    def with_duration(self, value: int) -> EventBuilder:
        self._data["duration_minutes"] = value
        return self

    def with_starts_at(self, value: str) -> EventBuilder:
        self._data["starts_at"] = value
        return self

    def with_event_type(self, value: str) -> EventBuilder:
        self._data["event_type"] = value
        return self

    def online(self, meeting_url: str = "https://meet.example.com/room-qa") -> EventBuilder:
        self._data["format"] = "online"
        self._data["meeting_url"] = meeting_url
        self._data.pop("location", None)
        return self

    def onsite(self, location: str = "ауд. 301") -> EventBuilder:
        self._data["format"] = "onsite"
        self._data["location"] = location
        self._data.pop("meeting_url", None)
        return self

    def build(self) -> dict[str, Any]:
        return dict(self._data)


def minimal_event_payload() -> dict[str, Any]:
    # Минимальный валидный payload (только обязательные поля).
    return {
        "title": f"Минимальное событие #{uuid.uuid4().hex[:6]}",
        "starts_at": _future_isoformat(),
        "capacity": 30,
    }
