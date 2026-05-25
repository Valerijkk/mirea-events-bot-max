"""Positive: CRUD /api/v1/events."""
from __future__ import annotations

import pytest

from config.urls import path_audit_logs, path_event, path_events
from core.api_client import ApiClient
from factories.event_factory import EventBuilder, minimal_event_payload


@pytest.mark.smoke
def test_create_event_minimal_valid_returns_201(api_as_organizer: ApiClient) -> None:
    payload = minimal_event_payload()

    resp = api_as_organizer.post_json(path_events(), json=payload)

    assert resp.status_code == 201, f"Ожидали 201, получили {resp.status_code}: {resp.text}"
    event = resp.json()

    assert event["status"] == "draft"
    assert event["id"] > 0
    # deeplink_payload — обязательный синтетический атрибут для бота.
    assert event.get("deeplink_payload"), "ожидаем deeplink_payload в ответе"

    api_as_organizer.delete(path_event(event["id"]))


def test_get_own_event_returns_full_object(
    api_as_organizer: ApiClient,
    clean_event: dict,
) -> None:
    resp = api_as_organizer.get(path_event(clean_event["id"]))

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body["id"] == clean_event["id"]
    assert body["title"] == clean_event["title"]


def test_patch_event_updates_single_field(
    api_as_organizer: ApiClient,
    clean_event: dict,
) -> None:
    new_title = f"{clean_event['title']} — изменено"

    resp = api_as_organizer.patch_json(
        path_event(clean_event["id"]),
        json={"title": new_title},
    )

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert resp.json()["title"] == new_title


def test_delete_own_event_then_get_404(api_as_organizer: ApiClient) -> None:
    # создаём свежее событие, чтобы безопасно его сносить
    created = api_as_organizer.post_json(path_events(), json=minimal_event_payload()).json()
    event_id = created["id"]

    resp = api_as_organizer.delete(path_event(event_id))

    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    assert resp.json().get("ok") is True

    follow_up = api_as_organizer.get(path_event(event_id))

    assert follow_up.status_code == 404, (
        f"Ожидали 404, получили {follow_up.status_code}: {follow_up.text}"
    )


def test_create_event_with_builder_online_format(api_as_organizer: ApiClient) -> None:
    payload = EventBuilder().online().with_capacity(10).build()

    resp = api_as_organizer.post_json(path_events(), json=payload)

    assert resp.status_code == 201, f"Ожидали 201, получили {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body["format"] == "online"

    api_as_organizer.delete(path_event(body["id"]))


@pytest.mark.api
@pytest.mark.pos
def test_create_event_writes_audit_log(
    api_as_admin: ApiClient,
    api_as_organizer: ApiClient,
) -> None:
    """Создание мероприятия записывает запись в audit_log с правильным actor_type."""
    payload = minimal_event_payload()
    resp = api_as_organizer.post_json(path_events(), json=payload)
    assert resp.status_code == 201, f"Ожидали 201, получили {resp.status_code}: {resp.text}"
    event_id = resp.json()["id"]

    audit_resp = api_as_admin.get(
        path_audit_logs(),
        params={"entity_type": "event", "entity_id": event_id, "event_type": "event.created"},
    )
    assert audit_resp.status_code == 200, (
        f"Ожидали 200, получили {audit_resp.status_code}: {audit_resp.text}"
    )
    logs = audit_resp.json()["items"]
    assert len(logs) >= 1
    assert logs[0]["event_type"] == "event.created"
    assert logs[0]["actor_type"] == "organizer"

    api_as_organizer.delete(path_event(event_id))
