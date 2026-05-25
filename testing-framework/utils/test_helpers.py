"""Общие хелперы для тестов — единое место для часто повторяющихся приколов.

Раньше эти функции жили локально в каждом test-файле (с префиксом `_`),
из-за чего одна и та же логика дублировалась в нескольких местах
(JWT-распаковка, поиск seed-события, поиск чужого event'а).

Сюда не складываем:
  * специфические для одного теста one-shot хелперы;
  * фикстуры pytest — те идут в `fixtures/`;
  * домен-специфичные степы — те идут в `steps/`.
"""
from __future__ import annotations

import base64
import json

import pytest

from config.urls import path_event_registrations, path_events
from core.api_client import ApiClient

# ---------------------------------------------------------------------------
# JWT — распаковка payload без проверки подписи.
# ---------------------------------------------------------------------------

def organizer_id_from_token(token: str | None) -> int | None:
    """Достать `sub` из JWT-payload (BASE64URL) — нам не нужна валидация подписи,
    только узнать чьим именем подписан токен."""
    if not token:
        return None
    try:
        _, payload_b64, _ = token.split(".")
        padded = payload_b64 + "=" * ((4 - len(payload_b64) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Поиск seed-данных (published events, регистраций).
# ---------------------------------------------------------------------------

def published_event_id_or_skip(api: ApiClient, *, limit: int = 5) -> int:
    """Вернуть id первого опубликованного события или SKIP-нуть тест.

    Используется в read-only тестах, которым нужно «любое опубликованное»
    (broadcasts, registrations, stats).
    """
    body = api.get(path_events(), params={"status": "published", "limit": limit}).json()
    if not body:
        pytest.skip("В seed нет опубликованных событий — нечего тестировать.")
    return int(body[0]["id"])


def first_owned_event(api: ApiClient) -> dict | None:
    """Найти первое событие, принадлежащее владельцу текущего JWT-токена.

    Каталог `/api/v1/events` глобально видим, но admin-операции
    (`/export.csv`, `/poster`, `/duplicate`) защищены IDOR-проверкой по
    `organizer_id`. После seed-импорта в начале списка стоят события
    другого организатора — этой функцией находим первое «своё».
    """
    my_id = organizer_id_from_token(api.token)
    if my_id is None:
        return None
    events = api.get("/api/v1/events?limit=200").json()
    for evt in events:
        if evt.get("organizer_id") == my_id:
            return evt
    return None


def find_confirmed_registration_code(api: ApiClient) -> tuple[int, str]:
    """Найти пару (event_id, code) для confirmed-регистрации.

    Идём по опубликованным событиям, пока не найдём то, у которого
    есть хотя бы одна `confirmed`-запись. Если ничего не нашли —
    SKIP. Используется в `/scan` pos-тесте.
    """
    events = api.get(path_events(), params={"status": "published", "limit": 20}).json()
    for evt in events:
        resp = api.get(
            path_event_registrations(evt["id"]),
            params={"status": "confirmed"},
        )
        if resp.status_code != 200:
            continue  # 403 — чужое событие, пропускаем
        body = resp.json()
        if isinstance(body, list) and body:
            return int(evt["id"]), str(body[0]["code"])
    pytest.skip("Нет confirmed-регистраций в seed — нечего сканировать.")
    raise AssertionError("unreachable")  # для mypy
