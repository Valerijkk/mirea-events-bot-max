"""Negative: POST /api/v1/integration/events/sync."""
from __future__ import annotations

from config.urls import path_integration_sync
from core.api_client import ApiClient
from factories.integration_event_factory import IntegrationEventFactory


def test_sync_without_key_returns_401(api_client: ApiClient) -> None:
    payload = {"events": [IntegrationEventFactory.build()]}

    resp = api_client.post_json(path_integration_sync(), json=payload)

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


def test_sync_with_bad_key_returns_401(api_client: ApiClient) -> None:
    bad = api_client.with_api_key("fake.never-existed")
    payload = {"events": [IntegrationEventFactory.build()]}

    resp = bad.post_json(path_integration_sync(), json=payload)

    assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"

    bad.close()


def test_sync_empty_events_returns_422(api_as_integration: ApiClient) -> None:
    resp = api_as_integration.post_json(path_integration_sync(), json={"events": []})

    assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"


def test_sync_empty_external_id_returns_422(api_as_integration: ApiClient) -> None:
    item = IntegrationEventFactory.build(external_id="")

    resp = api_as_integration.post_json(
        path_integration_sync(),
        json={"events": [item]},
    )

    assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"
