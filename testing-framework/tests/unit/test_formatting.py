"""Тесты `app/core/formatting.py` — единого источника истины для UI-форматов."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.formatting import format_duration_minutes, format_event_dt


def test_format_event_dt_returns_dash_for_none():
    assert format_event_dt(None) == "—"


def test_format_event_dt_format_matches_spec():
    """«DD.MM.YYYY в HH:MM» — контракт админских шаблонов и UX бота."""
    dt = datetime(2026, 5, 15, 14, 30)
    assert format_event_dt(dt) == "15.05.2026 в 14:30"


@pytest.mark.parametrize(
    "minutes, expected",
    [
        (None, "длительность не указана"),
        (0, "длительность не указана"),
        (-10, "длительность не указана"),
        (30, "30 мин"),
        (45, "45 мин"),
        (60, "1 ч"),
        (90, "1 ч 30 мин"),
        (120, "2 ч"),
        (135, "2 ч 15 мин"),
        (1440, "24 ч"),
    ],
    ids=[
        "none", "zero", "negative",
        "half-hour", "45-min", "one-hour",
        "hour-and-half", "two-hours", "two-hours-15-min", "full-day",
    ],
)
def test_format_duration_minutes(minutes: int | None, expected: str):
    assert format_duration_minutes(minutes) == expected
