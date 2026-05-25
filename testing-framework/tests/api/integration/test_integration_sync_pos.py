"""Positive: POST /api/v1/integration/events/sync."""
from __future__ import annotations

import uuid

from config.urls import path_integration_sync
from core.api_client import ApiClient
from factories.integration_event_factory import IntegrationEventFactory


def _summary(resp_json: dict) -> dict:
    """API возвращает счётчики либо в подобъекте `summary`, либо плоско.

    Локальный для модуля: больше нигде не используется — выносить в
    общий utils смысла нет.
    """
    return resp_json.get("summary", resp_json)


def test_sync_one_event_creates(api_as_integration: ApiClient) -> None:
    payload = {"events": [IntegrationEventFactory.build()]}

    resp = api_as_integration.post_json(path_integration_sync(), json=payload)

    assert resp.status_code in (200, 201), (
        f"Ожидали 200 или 201, получили {resp.status_code}: {resp.text}"
    )
    summary = _summary(resp.json())

    # счётчики: ровно одно созданное, ноль обновлённых
    assert summary.get("created", 0) == 1
    assert summary.get("updated", 0) == 0


def test_sync_same_external_id_updates(api_as_integration: ApiClient) -> None:
    # фиксированный external_id, чтобы повторный sync был upsert
    fixed_id = f"qa-fixed-{uuid.uuid4().hex[:8]}"
    item = IntegrationEventFactory.build(external_id=fixed_id)

    first = api_as_integration.post_json(
        path_integration_sync(),
        json={"events": [item]},
    )

    assert first.status_code in (200, 201), (
        f"Ожидали 200 или 201, получили {first.status_code}: {first.text}"
    )

    # повторный sync того же external_id (updated, не дубликат)
    second = api_as_integration.post_json(
        path_integration_sync(),
        json={"events": [item]},
    )

    # идемпотентность: вторая запись помечена как updated
    assert second.status_code in (200, 201), (
        f"Ожидали 200 или 201, получили {second.status_code}: {second.text}"
    )
    assert _summary(second.json()).get("updated", 0) == 1
