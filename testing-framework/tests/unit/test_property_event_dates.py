"""Property-based тесты на инварианты тайм-утилит фреймворка.

Hypothesis генерирует тысячи комбинаций входных данных и ищет
случай, когда инвариант ломается. Полезно там, где параметризация
руками не покрывает «странные» крайности.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from itertools import pairwise

from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from utils.time_helpers import in_hours, split_into_slots

hyp_settings.register_profile("ci", max_examples=50, deadline=None)
hyp_settings.load_profile("ci")


@given(
    base=st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2030, 12, 31)),
    hours=st.integers(min_value=1, max_value=720),
)
def test_in_hours_is_monotonic(base: datetime, hours: int) -> None:
    """in_hours(N) всегда строго позже base, ровно на N часов."""
    result = in_hours(hours, base=base)

    assert result == base + timedelta(hours=hours)
    assert result > base


@given(
    duration=st.integers(min_value=1, max_value=600),
    slot=st.integers(min_value=1, max_value=120),
)
def test_split_into_slots_no_overlap_no_gap(duration: int, slot: int) -> None:
    """Слоты не должны пересекаться и не должны оставлять зазоров до конца."""
    base = datetime(2026, 6, 1, 10, 0, 0)
    slots = split_into_slots(base, duration, slot_minutes=slot)

    assert slots[0][0] == base
    for left, right in pairwise(slots):
        assert left[1] == right[0], f"зазор/пересечение между {left} и {right}"
    assert slots[-1][1] == base + timedelta(minutes=duration)
