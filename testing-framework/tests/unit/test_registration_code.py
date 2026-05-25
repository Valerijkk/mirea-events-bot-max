"""Тесты человекочитаемого кода записи RG-XXXXXX.

Алфавит без 0/O/1/I — чтобы код не путали при ручной передиктовке.
"""
from __future__ import annotations

import re

from app.models import _generate_reg_code
from app.services.registration import sign_up, upsert_user


def test_reg_code_matches_pattern():
    code = _generate_reg_code()

    assert re.match(r"^RG-[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}$", code), code


def test_reg_code_does_not_contain_ambiguous_chars():
    """0/O/1/I не должны попадаться: путают пользователя при наборе кода."""
    codes = [_generate_reg_code() for _ in range(200)]

    for c in codes:
        for bad in "01OI":
            assert bad not in c, f"{c} содержит {bad!r}"


def test_reg_code_uniqueness_on_large_batch():
    # 32^6 ≈ 1.07e9 — коллизий на 1000 не ждём
    codes = {_generate_reg_code() for _ in range(1000)}
    assert len(codes) == 1000


def test_signup_attaches_code_to_registration(session, event_factory):
    event = event_factory(capacity=5)
    upsert_user(session, max_user_id=42, chat_id=42, name="Test")

    result = sign_up(session, event_id=event.id, user_id=42)

    assert result.registration.code.startswith("RG-")
    assert len(result.registration.code) == 9
