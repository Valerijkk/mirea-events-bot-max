"""Self-tests утилит из utils/. Тут проверяем сами проверялки.

Эти тесты — фундамент: если сломается ассерт `assert_problem_details`, то
весь corpus negative-тестов начнёт тихо проходить. Поэтому здесь покрытие
позитив+негатив для каждой функции.
"""
from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from utils.assertions import (
    assert_event_shape,
    assert_iso_8601,
    assert_no_secret_leak,
    assert_pagination_meta,
    assert_problem_details,
    assert_status,
    assert_subset,
)


def _resp(status: int, body: dict | list | str | None = None) -> httpx.Response:
    request = httpx.Request("GET", "http://test.local/api")
    if isinstance(body, dict | list):
        return httpx.Response(status, json=body, request=request)
    if isinstance(body, str):
        return httpx.Response(status, text=body, request=request)
    return httpx.Response(status, request=request)


def test_assert_status_passes_on_match() -> None:
    assert_status(_resp(200), 200)


def test_assert_status_fails_with_body_in_message() -> None:
    resp = _resp(500, {"detail": "internal boom"})
    with pytest.raises(AssertionError, match="internal boom"):
        assert_status(resp, 200)


def test_assert_problem_details_locates_field() -> None:
    resp = _resp(422, {"detail": [{"loc": ["body", "capacity"], "msg": "must be > 0"}]})
    assert_problem_details(resp, field="capacity", error_substring="must be > 0")


def test_assert_problem_details_fails_when_field_absent() -> None:
    resp = _resp(422, {"detail": [{"loc": ["body", "title"], "msg": "x"}]})
    with pytest.raises(AssertionError, match="capacity"):
        assert_problem_details(resp, field="capacity")


def test_assert_problem_details_accepts_string_detail() -> None:
    resp = _resp(400, {"detail": "Требуется заголовок Authorization: Bearer <token>"})
    assert_problem_details(resp, status=400, error_substring="Authorization")


def test_assert_iso_8601_round_trip() -> None:
    dt = assert_iso_8601("2026-06-01T18:00:00")
    assert dt == datetime(2026, 6, 1, 18, 0, 0)


def test_assert_iso_8601_with_z_suffix() -> None:
    dt = assert_iso_8601("2026-06-01T18:00:00Z")
    assert dt.year == 2026


def test_assert_iso_8601_rejects_garbage() -> None:
    with pytest.raises(AssertionError, match="ISO-8601"):
        assert_iso_8601("вчера в шесть")


def test_assert_event_shape_passes_for_published() -> None:
    event = {
        "id": 1,
        "title": "Test",
        "starts_at": "2026-06-01T18:00:00",
        "event_type": "open_day",
        "status": "published",
        "format": "onsite",
        "capacity": 100,
    }
    assert_event_shape(event)


def test_assert_event_shape_fails_on_missing_field() -> None:
    event = {"id": 1, "title": "T"}
    with pytest.raises(AssertionError, match="не хватает"):
        assert_event_shape(event)


def test_assert_event_shape_fails_on_unknown_status() -> None:
    event = {
        "id": 1, "title": "T", "starts_at": "2026-06-01T18:00:00",
        "event_type": "open_day", "status": "weird", "format": "onsite", "capacity": 1,
    }
    with pytest.raises(AssertionError, match="неизвестный status"):
        assert_event_shape(event)


def test_assert_no_secret_leak_passes_when_clean() -> None:
    assert_no_secret_leak(_resp(200, {"name": "Иван"}), ["+7900", "Bearer "])


def test_assert_no_secret_leak_catches_phone() -> None:
    resp = _resp(200, {"phone": "+79001234567"})
    with pytest.raises(AssertionError, match="утекли"):
        assert_no_secret_leak(resp, ["+79001234567"])


def test_assert_pagination_meta_strict() -> None:
    assert_pagination_meta(
        {"items": [], "page": 2, "page_size": 25}, page=2, page_size=25,
    )


def test_assert_pagination_meta_rejects_wrong_page() -> None:
    with pytest.raises(AssertionError):
        assert_pagination_meta({"items": [], "page": 1, "page_size": 25}, page=2, page_size=25)


def test_assert_subset_passes() -> None:
    assert_subset({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 2})


def test_assert_subset_fails_on_diff() -> None:
    with pytest.raises(AssertionError, match="actual=2"):
        assert_subset({"a": 2}, {"a": 1})
