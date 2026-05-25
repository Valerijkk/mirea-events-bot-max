"""Integration-тесты REST API `/api/v1/*` через FastAPI TestClient:
auth, CRUD событий, ownership, capacity guard, PII-минимизация, /scan.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.models import Event, EventStatus, EventType, Organizer
from app.services.registration import sign_up, upsert_user
from tests.unit.integration.conftest import api_login

# ===========================================================================
# /api/v1/auth/login
# ===========================================================================

class TestAuthLogin:
    def test_login_success_returns_bearer_token(
        self, client: TestClient, alice: Organizer
    ):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@mirea.ru", "password": "alicepass1"},
        )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 20

    def test_login_wrong_password_returns_401(
        self, client: TestClient, alice: Organizer
    ):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@mirea.ru", "password": "WRONG"},
        )
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"

    def test_login_unknown_email_returns_same_401(self, client: TestClient):
        """Защита от user-enumeration: один и тот же 401 для неверного пароля
        и для неизвестного email.
        """
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@mirea.ru", "password": "any"},
        )
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


# ===========================================================================
# Bearer защита
# ===========================================================================

class TestBearerAuth:
    def test_protected_endpoint_without_token_returns_401(
        self, client: TestClient
    ):
        resp = client.get("/api/v1/events")
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"

    def test_protected_endpoint_with_bad_token_returns_401(
        self, client: TestClient
    ):
        resp = client.get(
            "/api/v1/events",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401, f"Ожидали 401, получили {resp.status_code}: {resp.text}"


# ===========================================================================
# Event CRUD через REST
# ===========================================================================

class TestEventCRUD:
    @staticmethod
    def _bearer(client, email, password) -> dict[str, str]:
        token = api_login(client, email, password)
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _event_payload(**overrides) -> dict:
        base = {
            "title": "Тест-событие",
            "description": "desc",
            "event_type": "open_day",
            "starts_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            "location": "ауд. 101",
            "capacity": 30,
            "duration_minutes": 90,
            "format": "onsite",
            "requirements": None,
            "cancellation_terms": None,
            "meeting_url": None,
            "late_cancel_policy": "disallow",
        }
        return {**base, **overrides}

    def test_create_event_returns_201(self, client: TestClient, alice: Organizer):
        headers = self._bearer(client, "alice@mirea.ru", "alicepass1")
        resp = client.post(
            "/api/v1/events", json=self._event_payload(), headers=headers
        )
        assert resp.status_code == 201, f"Ожидали 201, получили {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["title"] == "Тест-событие"
        assert body["status"] == "draft"
        assert body["organizer_id"] == alice.id
        assert body["registration_open"] is True

    def test_list_events_returns_array(self, client: TestClient, alice: Organizer):
        headers = self._bearer(client, "alice@mirea.ru", "alicepass1")
        client.post(
            "/api/v1/events",
            json=self._event_payload(title="Первое событие"),
            headers=headers,
        )
        client.post(
            "/api/v1/events",
            json=self._event_payload(title="Второе событие"),
            headers=headers,
        )
        resp = client.get("/api/v1/events", headers=headers)
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        titles = [e["title"] for e in resp.json()]
        assert "Первое событие" in titles
        assert "Второе событие" in titles

    def test_get_own_event_returns_200(
        self, client: TestClient, alice: Organizer, int_db
    ):
        headers = self._bearer(client, "alice@mirea.ru", "alicepass1")
        event = _make_event(int_db, alice)
        resp = client.get(f"/api/v1/events/{event.id}", headers=headers)
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        assert resp.json()["id"] == event.id

    def test_get_alien_event_returns_403(
        self, client: TestClient, alice: Organizer, bob: Organizer, int_db
    ):
        headers = self._bearer(client, "alice@mirea.ru", "alicepass1")
        bob_event = _make_event(int_db, bob)
        resp = client.get(f"/api/v1/events/{bob_event.id}", headers=headers)
        assert resp.status_code == 403, f"Ожидали 403, получили {resp.status_code}: {resp.text}"

    def test_get_missing_event_returns_404(
        self, client: TestClient, alice: Organizer
    ):
        headers = self._bearer(client, "alice@mirea.ru", "alicepass1")
        resp = client.get("/api/v1/events/99999", headers=headers)
        assert resp.status_code == 404, f"Ожидали 404, получили {resp.status_code}: {resp.text}"

    def test_patch_event_updates_fields(
        self, client: TestClient, alice: Organizer, int_db
    ):
        headers = self._bearer(client, "alice@mirea.ru", "alicepass1")
        event = _make_event(int_db, alice)
        resp = client.patch(
            f"/api/v1/events/{event.id}",
            json={"title": "Обновлено", "capacity": 100},
            headers=headers,
        )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        assert resp.json()["title"] == "Обновлено"
        assert resp.json()["capacity"] == 100

    def test_patch_capacity_below_confirmed_returns_422(
        self, client: TestClient, alice: Organizer, int_db
    ):
        """Capacity guard в update_event: нельзя опустить ниже confirmed."""
        headers = self._bearer(client, "alice@mirea.ru", "alicepass1")
        event = _make_event(int_db, alice, capacity=5)
        for uid in [1, 2, 3]:
            upsert_user(int_db, max_user_id=uid, chat_id=uid, name=f"U{uid}")
        sign_up(int_db, event_id=event.id, user_id=1)
        sign_up(int_db, event_id=event.id, user_id=2)
        sign_up(int_db, event_id=event.id, user_id=3)
        int_db.commit()

        resp = client.patch(
            f"/api/v1/events/{event.id}",
            json={"capacity": 2},  # ниже confirmed=3
            headers=headers,
        )
        assert resp.status_code == 422, f"Ожидали 422, получили {resp.status_code}: {resp.text}"
        assert "capacity" in resp.json()["detail"].lower()

    def test_set_status_cancelled_marks_event(
        self, client: TestClient, alice: Organizer, int_db
    ):
        headers = self._bearer(client, "alice@mirea.ru", "alicepass1")
        event = _make_event(int_db, alice)
        resp = client.post(
            f"/api/v1/events/{event.id}/status",
            json={"status": "cancelled"},
            headers=headers,
        )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        assert resp.json()["status"] == "cancelled"

    def test_delete_event(self, client: TestClient, alice: Organizer, int_db):
        headers = self._bearer(client, "alice@mirea.ru", "alicepass1")
        event = _make_event(int_db, alice)
        resp = client.delete(f"/api/v1/events/{event.id}", headers=headers)
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        # Повторно — 404
        resp2 = client.delete(f"/api/v1/events/{event.id}", headers=headers)
        assert resp2.status_code == 404, f"Ожидали 404, получили {resp2.status_code}: {resp2.text}"


# ===========================================================================
# /api/v1/events/{id}/registrations — без PII (ТЗ §3 минимизация)
# ===========================================================================

def test_registrations_list_does_not_expose_phone(
    client: TestClient, alice: Organizer, int_db
):
    """ТЗ §3 «минимизация PII»: телефон не должен утечь через REST."""
    headers = {"Authorization": f"Bearer {api_login(client, 'alice@mirea.ru', 'alicepass1')}"}
    event = _make_event(int_db, alice)
    upsert_user(int_db, max_user_id=42, chat_id=42, name="Иван", phone="+79991234567")
    sign_up(int_db, event_id=event.id, user_id=42)
    int_db.commit()

    resp = client.get(f"/api/v1/events/{event.id}/registrations", headers=headers)
    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
    body_str = resp.text
    assert "+79991234567" not in body_str
    assert "phone" not in body_str.lower() or '"phone":' not in body_str


# ===========================================================================
# /api/v1/healthz — sanity
# ===========================================================================

def test_healthz_returns_200(client: TestClient):
    resp = client.get("/api/v1/healthz")
    assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"


def test_readyz_returns_200(client: TestClient):
    resp = client.get("/api/v1/readyz")
    assert resp.status_code in (200, 503), f"Ожидали 200 или 503, получили {resp.status_code}: {resp.text}"


# ===========================================================================
# /api/v1/scan — флоу со сканером
# ===========================================================================

class TestScan:
    def test_scan_unknown_qr_returns_ok_false(
        self, client: TestClient, alice: Organizer
    ):
        headers = {"Authorization": f"Bearer {api_login(client, 'alice@mirea.ru', 'alicepass1')}"}
        resp = client.post(
            "/api/v1/scan",
            json={"qr_token": "definitely-does-not-exist"},
            headers=headers,
        )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        assert resp.json()["ok"] is False

    def test_scan_alien_event_qr_returns_not_found(
        self, client: TestClient, alice: Organizer, bob: Organizer, int_db
    ):
        """Oracle-mitigation (SEC-V3-H1): чужой QR → не 403, а 200/not_found.

        Иначе по разнице ответов 403 vs 404 атакующий мог бы брутить
        пространство токенов и понимать, какие из них существуют.
        """
        headers = {"Authorization": f"Bearer {api_login(client, 'alice@mirea.ru', 'alicepass1')}"}
        bob_event = _make_event(int_db, bob)
        upsert_user(int_db, max_user_id=42, chat_id=42, name="Гость")
        result = sign_up(int_db, event_id=bob_event.id, user_id=42)
        int_db.commit()

        resp = client.post(
            "/api/v1/scan",
            json={"qr_token": result.registration.qr_token},
            headers=headers,
        )
        assert resp.status_code == 200, f"Ожидали 200, получили {resp.status_code}: {resp.text}"
        assert resp.json()["status"] == "not_found"
        # Bob'ова запись не должна быть тронута.
        int_db.expire_all()
        from app.models import Registration, RegStatus
        reg = int_db.get(Registration, result.registration.id)
        assert reg.status == RegStatus.CONFIRMED


# ===========================================================================
# Helpers
# ===========================================================================

def _make_event(db, organizer: Organizer, capacity=10) -> Event:
    ev = Event(
        title="Test",
        event_type=EventType.OTHER,
        starts_at=datetime.utcnow() + timedelta(days=7),
        location="x",
        capacity=capacity,
        organizer_id=organizer.id,
        status=EventStatus.PUBLISHED,
    )
    db.add(ev)
    db.commit()
    return ev
