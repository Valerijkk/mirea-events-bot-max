"""Кастомные ассерты для типичных проверок SUT.

Зачем отдельный модуль: каждое утверждение даёт **доменное** имя и
прицельный assertion-error. Сравните `assert resp.status_code == 422` —
и `assert_problem_details(resp, field="capacity")` — второе при падении
сразу показывает текст ошибки сервера и подсказывает чинить капасити.

Все ассерты — pure-функции: не делают сетевых вызовов, не трогают БД.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx

_ISO_8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})?$"
)


def assert_status(resp: httpx.Response, expected: int, *, context: str = "") -> None:
    """Дружелюбное сравнение статус-кода с подсказкой по телу при падении."""
    if resp.status_code == expected:
        return
    body_preview = _safe_body(resp)
    suffix = f" ({context})" if context else ""
    raise AssertionError(
        f"ожидался HTTP {expected}, пришёл {resp.status_code}{suffix}\n"
        f"{resp.request.method} {resp.request.url}\n"
        f"тело ответа: {body_preview}"
    )


def assert_problem_details(
    resp: httpx.Response,
    *,
    status: int = 422,
    field: str | None = None,
    error_substring: str | None = None,
) -> dict[str, Any]:
    """FastAPI/Pydantic-422 в типовой форме: {"detail": [{"loc": [...], "msg": "..."}]}."""
    assert_status(resp, status)
    body = resp.json()
    detail = body.get("detail")
    if isinstance(detail, str):
        if error_substring and error_substring not in detail:
            raise AssertionError(
                f"в detail-строке нет подстроки {error_substring!r}: {detail!r}"
            )
        return body
    assert isinstance(detail, list), f"detail должен быть list или str, не {type(detail)}"
    if field is not None:
        matched = [d for d in detail if field in d.get("loc", [])]
        assert matched, (
            f"в detail нет ошибки для поля {field!r}. "
            f"loc'ы: {[d.get('loc') for d in detail]}"
        )
    if error_substring is not None:
        haystack = " ".join(d.get("msg", "") for d in detail)
        assert error_substring in haystack, (
            f"в сообщениях нет подстроки {error_substring!r}. "
            f"сообщения: {[d.get('msg') for d in detail]}"
        )
    return body


def assert_iso_8601(value: str, *, label: str = "datetime") -> datetime:
    """Парсит ISO-8601 строку и возвращает datetime. Бросает с понятным сообщением."""
    assert isinstance(value, str), f"{label}: ожидалась str, не {type(value).__name__}"
    assert _ISO_8601_RE.match(value), f"{label} не похоже на ISO-8601: {value!r}"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssertionError(f"{label}={value!r} не парсится: {exc}") from exc


def assert_event_shape(event: dict[str, Any]) -> None:
    """Минимальный контракт ответа GET /api/v1/events/{id}.

    Не проверяет ВСЕ поля (это делают contract-тесты), только нерушимые.
    Цель — на ранней стадии теста ловить «сервер вернул что-то странное».
    """
    required = {"id", "title", "starts_at", "event_type", "status", "format", "capacity"}
    missing = required - set(event.keys())
    assert not missing, f"в событии не хватает полей: {missing}. ключи: {sorted(event.keys())}"
    assert_iso_8601(event["starts_at"], label="event.starts_at")
    assert isinstance(event["id"], int), f"id должен быть int, пришёл {type(event['id'])}"
    assert event["status"] in {"draft", "published", "cancelled", "finished"}, (
        f"неизвестный status: {event['status']!r}"
    )


def assert_no_secret_leak(resp: httpx.Response, secret_substrings: list[str]) -> None:
    """Тело ответа НЕ содержит чувствительных подстрок.

    Применение: проверка что эндпоинт не отдаёт телефон, JWT, hash пароля.
    """
    body = _safe_body(resp).lower()
    leaks = [s for s in secret_substrings if s.lower() in body]
    assert not leaks, f"в теле ответа утекли подстроки: {leaks}\nтело: {body[:300]}"


def assert_pagination_meta(payload: dict[str, Any], *, page: int, page_size: int) -> None:
    """Проверка пагинационной обвязки (если эндпоинт её возвращает)."""
    assert "items" in payload or "events" in payload, (
        "ожидалась пагинационная обёртка с ключом items/events"
    )
    if "page" in payload:
        assert payload["page"] == page, f"page={payload['page']!r}, ждали {page}"
    if "page_size" in payload:
        actual_size = payload["page_size"]
        assert actual_size == page_size, f"page_size={actual_size!r}, ждали {page_size}"


def assert_subset(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    """expected ⊆ actual поэлементно (без вложенной dict-рекурсии)."""
    diffs: list[str] = []
    for k, v in expected.items():
        if k not in actual:
            diffs.append(f"нет ключа {k!r}")
            continue
        if actual[k] != v:
            diffs.append(f"{k!r}: actual={actual[k]!r} expected={v!r}")
    assert not diffs, "разница с ожиданием:\n  " + "\n  ".join(diffs)


def _safe_body(resp: httpx.Response, limit: int = 500) -> str:
    try:
        text = resp.text
    except Exception:
        text = "<нечитаемое тело>"
    return text[:limit] + ("…" if len(text) > limit else "")
