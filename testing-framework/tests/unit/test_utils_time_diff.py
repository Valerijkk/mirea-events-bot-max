"""Self-tests time_helpers и diff."""
from __future__ import annotations

from datetime import datetime, timedelta

from utils.diff import diff_collections, index_by, only_changed_ids
from utils.time_helpers import (
    in_days,
    in_hours,
    in_minutes,
    iso,
    split_into_slots,
    tomorrow_at,
)


_BASE = datetime(2026, 5, 20, 12, 0, 0)


def test_in_minutes_adds_to_base() -> None:
    assert in_minutes(30, base=_BASE) == datetime(2026, 5, 20, 12, 30)


def test_in_hours_adds_to_base() -> None:
    assert in_hours(2, base=_BASE) == datetime(2026, 5, 20, 14, 0)


def test_in_days_adds_to_base() -> None:
    assert in_days(7, base=_BASE) == datetime(2026, 5, 27, 12, 0)


def test_tomorrow_at_normalizes_time() -> None:
    result = tomorrow_at(10, 30, base=_BASE)
    assert result.date() == (_BASE + timedelta(days=1)).date()
    assert (result.hour, result.minute, result.second, result.microsecond) == (10, 30, 0, 0)


def test_iso_strips_microseconds() -> None:
    dt = datetime(2026, 5, 20, 12, 0, 0, 999999)
    assert iso(dt) == "2026-05-20T12:00:00"


def test_split_into_slots_even_distribution() -> None:
    slots = split_into_slots(_BASE, 60, slot_minutes=15)
    assert len(slots) == 4
    assert slots[0] == (_BASE, _BASE + timedelta(minutes=15))
    assert slots[-1][1] == _BASE + timedelta(minutes=60)


def test_split_into_slots_uneven_tail() -> None:
    slots = split_into_slots(_BASE, 50, slot_minutes=20)
    assert len(slots) == 3
    assert slots[-1] == (_BASE + timedelta(minutes=40), _BASE + timedelta(minutes=50))


def test_index_by_takes_last_on_duplicate() -> None:
    items = [{"id": 1, "x": "a"}, {"id": 1, "x": "b"}, {"id": 2, "x": "c"}]
    idx = index_by(items, key="id")
    assert idx[1]["x"] == "b"
    assert idx[2]["x"] == "c"


def test_diff_collections_detects_added_and_removed() -> None:
    before = [{"id": 1}, {"id": 2}]
    after = [{"id": 2}, {"id": 3}]
    diff = diff_collections(before, after)
    assert [a["id"] for a in diff["added"]] == [3]
    assert [r["id"] for r in diff["removed"]] == [1]
    assert diff["changed"] == []


def test_diff_collections_tracked_field_changed() -> None:
    before = [{"id": 1, "status": "draft", "title": "A"}]
    after = [{"id": 1, "status": "published", "title": "A"}]
    diff = diff_collections(before, after, track=("status",))
    assert diff["changed"] == [{"id": 1, "diff": {"status": ("draft", "published")}}]


def test_only_changed_ids_unions_all_buckets() -> None:
    diff = {
        "added": [{"id": 3}],
        "removed": [{"id": 1}],
        "changed": [{"id": 2}],
    }
    assert only_changed_ids(diff) == {1, 2, 3}
