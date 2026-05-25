"""Self-tests для schema_check."""
from __future__ import annotations

import pytest

from utils.schema_check import (
    check_enum,
    check_event_response,
    check_keys,
    check_types,
)


def test_check_keys_ok() -> None:
    check_keys({"a": 1, "b": 2}, ["a", "b"])


def test_check_keys_reports_missing() -> None:
    with pytest.raises(AssertionError, match=r"'b', 'c'"):
        check_keys({"a": 1}, ["a", "b", "c"])


def test_check_types_skips_optional_none() -> None:
    check_types({"a": None, "b": "x"}, {"a": int, "b": str})


def test_check_types_rejects_wrong_type() -> None:
    with pytest.raises(AssertionError, match="ожидался int"):
        check_types({"a": "oops"}, {"a": int})


def test_check_enum_accepts_valid() -> None:
    check_enum("draft", ["draft", "published"], label="status")


def test_check_enum_rejects_invalid() -> None:
    with pytest.raises(AssertionError, match="не входит в допустимые"):
        check_enum("weird", ["draft", "published"])


def test_check_event_response_full_ok() -> None:
    event = {
        "id": 7,
        "title": "X",
        "starts_at": "2026-06-01T10:00:00",
        "ends_at": "2026-06-01T12:00:00",
        "event_type": "open_day",
        "status": "published",
        "format": "onsite",
        "capacity": 100,
        "duration_minutes": 120,
        "location": "Vernadsky 78",
        "max_entries": 1,
    }
    check_event_response(event)


def test_check_event_response_rejects_unknown_format() -> None:
    event = {
        "id": 7, "title": "X", "starts_at": "2026-06-01T10:00:00",
        "event_type": "open_day", "status": "published",
        "format": "phantom", "capacity": 100,
    }
    with pytest.raises(AssertionError, match="format=.phantom"):
        check_event_response(event)
