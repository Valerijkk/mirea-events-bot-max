"""Фикстуры тестовых данных: событие с автоматическим cleanup."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from core.api_client import ApiClient
from factories.event_factory import EventBuilder, minimal_event_payload
from steps.api.event_steps import create_event, delete_event


@pytest.fixture
def event_factory_with_cleanup(api_as_organizer: ApiClient) -> Iterator[Any]:
    # Тест получает callable, который и создаёт, и регистрирует на cleanup.
    created_ids: list[int] = []

    def _create(**overrides: Any) -> dict[str, Any]:
        payload = EventBuilder()
        for key, value in overrides.items():
            method = getattr(payload, f"with_{key}", None)
            if method is None:
                # Прямая правка для полей без with_*-сахара.
                payload._data[key] = value
            else:
                method(value)
        data = payload.build()
        event = create_event(api_as_organizer, data)
        created_ids.append(event["id"])
        return event

    yield _create

    for event_id in created_ids:
        try:
            delete_event(api_as_organizer, event_id)
        except Exception:
            # Cleanup best-effort: не падаем, если событие уже удалено.
            pass


@pytest.fixture
def clean_event(api_as_organizer: ApiClient) -> Iterator[dict[str, Any]]:
    # Создаёт одно мероприятие и гарантированно удаляет в teardown.
    event = create_event(api_as_organizer, minimal_event_payload())
    yield event
    try:
        delete_event(api_as_organizer, event["id"])
    except Exception:
        pass


@pytest.fixture
def published_event(
    api_as_organizer: ApiClient,
    event_factory_with_cleanup: Any,
) -> dict[str, Any]:
    # Создаём draft → переводим в published; cleanup делается фабрикой.
    from steps.api.event_steps import change_status

    event = event_factory_with_cleanup()
    change_status(api_as_organizer, event["id"], "published")
    return event
