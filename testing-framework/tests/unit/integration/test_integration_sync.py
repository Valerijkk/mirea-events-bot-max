"""Integration-тесты bulk-импорта событий через `POST /api/v1/integration/events/sync`.

Покрытие:
* pos: создание batch'а, upsert по `external_id`, идемпотентность,
  auto_publish override, разные источники не конфликтуют.
* neg: отсутствующий/неверный/отозванный ключ, неверный формат payload,
  multi-tenant изоляция между ключами разных организаторов.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.admin.auth import hash_password
from app.models import Event, EventStatus, IntegrationKey, Organizer

# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def _create_key(
    int_db, organizer: Organizer, source: str = "mirea_priem",
    auto_publish: bool = False, active: bool = True, raw_key: str | None = None,
) -> tuple[IntegrationKey, str]:
    """Создать ключ в БД, вернуть (объект, plaintext)."""
    plaintext = raw_key or f"{source}.testkey_{organizer.id}_{source}"
    key = IntegrationKey(
        name=f"Test {source}",
        source=source,
        key_hash=hash_password(plaintext),
        organizer_id=organizer.id,
        active=active,
        auto_publish=auto_publish,
    )
    int_db.add(key)
    int_db.commit()
    return key, plaintext


def _sync_payload(*items: dict, auto_publish: bool | None = None) -> dict:
    """Собрать тело запроса. `items` — частичные dict'ы, остальное — defaults."""
    base = {
        "title": "Default Event",
        "starts_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        "capacity": 50,
        "event_type": "open_day",
        "format": "onsite",
    }
    events = []
    for i, override in enumerate(items, start=1):
        ev = {**base, **override}
        ev.setdefault("external_id", f"ext_{i}")
        events.append(ev)
    body = {"events": events}
    if auto_publish is not None:
        body["auto_publish"] = auto_publish
    return body


# ===========================================================================
# Аутентификация
# ===========================================================================

class TestAuth:
    def test_missing_api_key_returns_401(self, client: TestClient, alice: Organizer):
        resp = client.post("/api/v1/integration/events/sync", json=_sync_payload({}))
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"
        assert "ключ" in resp.json()["detail"].lower()

    def test_malformed_api_key_returns_401(self, client: TestClient, alice: Organizer):
        # Ключ без точки (нет source-префикса) → 401.
        resp = client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({}),
            headers={"X-API-Key": "badkey_without_dot"},
        )
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"

    def test_wrong_api_key_returns_401(self, client: TestClient, alice: Organizer, int_db):
        _create_key(int_db, alice, source="mirea_priem")
        resp = client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({}),
            headers={"X-API-Key": "mirea_priem.wrong_secret"},
        )
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"

    def test_revoked_key_returns_401(self, client: TestClient, alice: Organizer, int_db):
        key, plaintext = _create_key(int_db, alice, active=False)
        resp = client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({}),
            headers={"X-API-Key": plaintext},
        )
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"

    def test_valid_key_returns_200(self, client: TestClient, alice: Organizer, int_db):
        key, plaintext = _create_key(int_db, alice)
        resp = client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({}),
            headers={"X-API-Key": plaintext},
        )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"


# ===========================================================================
# Создание событий
# ===========================================================================

class TestCreate:
    def test_creates_single_event(self, client: TestClient, alice: Organizer, int_db):
        _, plaintext = _create_key(int_db, alice)
        body = _sync_payload({
            "external_id": "ext-1",
            "title": "День открытых дверей ИИТ",
            "event_type": "open_day",
        })
        resp = client.post(
            "/api/v1/integration/events/sync",
            json=body, headers={"X-API-Key": plaintext},
        )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["received"] == 1
        assert data["summary"]["created"] == 1
        assert data["summary"]["updated"] == 0
        assert data["results"][0]["action"] == "created"
        assert data["results"][0]["internal_id"] is not None

        # В БД событие реально появилось и принадлежит alice.
        events = int_db.query(Event).all()
        assert len(events) == 1
        assert events[0].title == "День открытых дверей ИИТ"
        assert events[0].organizer_id == alice.id
        assert events[0].external_source == "mirea_priem"
        assert events[0].external_id == "ext-1"

    def test_creates_batch_of_three(self, client: TestClient, alice: Organizer, int_db):
        _, plaintext = _create_key(int_db, alice)
        body = _sync_payload(
            {"external_id": "ext-a", "title": "Олимпиада математика"},
            {"external_id": "ext-b", "title": "Экскурсия по корпусу А"},
            {"external_id": "ext-c", "title": "Мастер-класс Python"},
        )
        resp = client.post(
            "/api/v1/integration/events/sync",
            json=body, headers={"X-API-Key": plaintext},
        )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["summary"]["created"] == 3
        assert int_db.query(Event).count() == 3

    def test_default_status_is_draft(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        # auto_publish=False (по умолчанию) → события приходят как draft.
        _, plaintext = _create_key(int_db, alice, auto_publish=False)
        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "ext-d"}),
            headers={"X-API-Key": plaintext},
        )
        ev = int_db.query(Event).filter_by(external_id="ext-d").first()
        assert ev.status == EventStatus.DRAFT

    def test_auto_publish_flag_on_key(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        _, plaintext = _create_key(int_db, alice, auto_publish=True)
        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "ext-pub"}),
            headers={"X-API-Key": plaintext},
        )
        ev = int_db.query(Event).filter_by(external_id="ext-pub").first()
        assert ev.status == EventStatus.PUBLISHED

    def test_request_override_auto_publish(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        # Ключ с auto_publish=False, но запрос переопределяет.
        _, plaintext = _create_key(int_db, alice, auto_publish=False)
        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "ext-ovr"}, auto_publish=True),
            headers={"X-API-Key": plaintext},
        )
        ev = int_db.query(Event).filter_by(external_id="ext-ovr").first()
        assert ev.status == EventStatus.PUBLISHED


# ===========================================================================
# Идемпотентность / upsert
# ===========================================================================

class TestIdempotency:
    def test_repeat_same_batch_gives_updates(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        _, plaintext = _create_key(int_db, alice)
        body = _sync_payload({"external_id": "stable-1", "title": "Первый прогон"})

        first = client.post(
            "/api/v1/integration/events/sync",
            json=body, headers={"X-API-Key": plaintext},
        )
        assert first.json()["summary"]["created"] == 1

        second = client.post(
            "/api/v1/integration/events/sync",
            json=body, headers={"X-API-Key": plaintext},
        )
        assert second.json()["summary"]["updated"] == 1
        assert second.json()["summary"]["created"] == 0

        # В БД ровно одно событие — дубликата нет.
        assert int_db.query(Event).filter_by(external_id="stable-1").count() == 1

    def test_update_changes_fields(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        _, plaintext = _create_key(int_db, alice)
        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "upd-1", "title": "Старое название"}),
            headers={"X-API-Key": plaintext},
        )

        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({
                "external_id": "upd-1",
                "title": "Новое название",
                "capacity": 200,
            }),
            headers={"X-API-Key": plaintext},
        )
        ev = int_db.query(Event).filter_by(external_id="upd-1").first()
        assert ev.title == "Новое название"
        assert ev.capacity == 200

    def test_update_preserves_manual_status(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        """Оператор отменил событие вручную — повторный sync не должен его воскресить."""
        _, plaintext = _create_key(int_db, alice, auto_publish=True)
        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "preserve-1"}),
            headers={"X-API-Key": plaintext},
        )
        # Оператор отменил.
        ev = int_db.query(Event).filter_by(external_id="preserve-1").first()
        ev.status = EventStatus.CANCELLED
        int_db.commit()

        # Внешняя система снова шлёт это событие.
        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "preserve-1", "title": "Обновлённое"}),
            headers={"X-API-Key": plaintext},
        )
        int_db.refresh(ev)
        # Статус НЕ откатился к published.
        assert ev.status == EventStatus.CANCELLED
        # Но название обновилось.
        assert ev.title == "Обновлённое"


# ===========================================================================
# Multi-tenant изоляция
# ===========================================================================

class TestMultiTenant:
    def test_events_belong_to_key_owner(
        self, client: TestClient, alice: Organizer, bob: Organizer, int_db,
    ):
        _, alice_key = _create_key(int_db, alice, source="alice_src")
        _, bob_key = _create_key(int_db, bob, source="bob_src")

        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "from-alice"}),
            headers={"X-API-Key": alice_key},
        )
        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "from-bob"}),
            headers={"X-API-Key": bob_key},
        )

        alice_ev = int_db.query(Event).filter_by(external_id="from-alice").first()
        bob_ev = int_db.query(Event).filter_by(external_id="from-bob").first()
        assert alice_ev.organizer_id == alice.id
        assert bob_ev.organizer_id == bob.id

    def test_different_sources_share_external_id(
        self, client: TestClient, alice: Organizer, bob: Organizer, int_db,
    ):
        """Один и тот же external_id из РАЗНЫХ источников = два события."""
        _, alice_key = _create_key(int_db, alice, source="src_a")
        _, bob_key = _create_key(int_db, bob, source="src_b")

        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "evt-1"}),
            headers={"X-API-Key": alice_key},
        )
        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "evt-1"}),
            headers={"X-API-Key": bob_key},
        )
        # Два события: одно от alice_src, второе от bob_src.
        assert int_db.query(Event).filter_by(external_id="evt-1").count() == 2


# ===========================================================================
# Валидация payload
# ===========================================================================

class TestValidation:
    def test_empty_events_list_returns_422(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        _, plaintext = _create_key(int_db, alice)
        resp = client.post(
            "/api/v1/integration/events/sync",
            json={"events": []},
            headers={"X-API-Key": plaintext},
        )
        assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"

    def test_missing_external_id_returns_422(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        _, plaintext = _create_key(int_db, alice)
        resp = client.post(
            "/api/v1/integration/events/sync",
            json={"events": [{
                "title": "X" * 10,
                "starts_at": datetime.utcnow().isoformat(),
                "capacity": 10,
            }]},
            headers={"X-API-Key": plaintext},
        )
        assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"

    def test_negative_capacity_returns_422(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        _, plaintext = _create_key(int_db, alice)
        resp = client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload({"external_id": "x", "capacity": -1}),
            headers={"X-API-Key": plaintext},
        )
        assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"


# ===========================================================================
# Health
# ===========================================================================

class TestIntegrationHealth:
    def test_health_with_valid_key(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        _, plaintext = _create_key(int_db, alice, source="hc_test")
        resp = client.get(
            "/api/v1/integration/health",
            headers={"X-API-Key": plaintext},
        )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "ok"
        assert data["source"] == "hc_test"
        assert data["organizer"] == "alice@mirea.ru"

    def test_health_without_key(self, client: TestClient):
        resp = client.get("/api/v1/integration/health")
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


# ===========================================================================
# Аудит использования
# ===========================================================================

class TestAudit:
    def test_total_synced_increments(
        self, client: TestClient, alice: Organizer, int_db,
    ):
        key, plaintext = _create_key(int_db, alice)
        assert key.total_synced == 0
        assert key.last_used_at is None

        client.post(
            "/api/v1/integration/events/sync",
            json=_sync_payload(
                {"external_id": "a"}, {"external_id": "b"}, {"external_id": "c"},
            ),
            headers={"X-API-Key": plaintext},
        )
        int_db.refresh(key)
        assert key.total_synced == 3
        assert key.last_used_at is not None
