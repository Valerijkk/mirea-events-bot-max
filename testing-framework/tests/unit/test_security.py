"""Тесты инфраструктуры безопасности: rate-limiter."""
from __future__ import annotations

import pytest

from app.core.rate_limit import InMemoryRateLimiter

# ---------------------------------------------------------------------------
# InMemoryRateLimiter
# ---------------------------------------------------------------------------

def test_rate_limiter_allows_up_to_max():
    limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)

    assert limiter.check("ip1") is True
    assert limiter.check("ip1") is True
    assert limiter.check("ip1") is True


def test_rate_limiter_blocks_after_max():
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
    limiter.check("user")
    limiter.check("user")

    assert limiter.check("user") is False


def test_rate_limiter_isolates_keys():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)
    limiter.check("ip1")

    assert limiter.check("ip1") is False, "ip1 уже превысил"
    assert limiter.check("ip2") is True, "ip2 — независимый счётчик"


def test_rate_limiter_window_expires(monkeypatch):
    # Фейковый time.monotonic — чтобы не sleep'ить window_seconds в тесте.
    fake_now = [1000.0]
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: fake_now[0])
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=10)
    limiter.check("k")

    fake_now[0] += 5  # ещё в окне → отбит
    assert limiter.check("k") is False

    fake_now[0] += 20  # окно прошло → снова можно
    assert limiter.check("k") is True


def test_rate_limiter_reset_clears_specific_key():
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60)
    limiter.check("a")
    limiter.check("b")

    limiter.reset("a")

    assert limiter.check("a") is True
    assert limiter.check("b") is False


@pytest.mark.parametrize(
    "max_requests, window_seconds",
    [
        (0, 60),     # нулевой лимит — бессмысленно
        (-1, 60),    # отрицательный
        (5, 0),      # нулевое окно
        (5, -10),    # отрицательное окно
    ],
    ids=["zero-max", "negative-max", "zero-window", "negative-window"],
)
def test_rate_limiter_rejects_invalid_construction(max_requests: int, window_seconds: int):
    """Невалидные параметры — ValueError на старте, не молчаливая бомба в проде."""
    with pytest.raises(ValueError):
        InMemoryRateLimiter(max_requests=max_requests, window_seconds=window_seconds)


# ---------------------------------------------------------------------------
# verify_csrf удалён вместе с app.admin.csrf (#183e) — React SPA + Bearer JWT.
# ---------------------------------------------------------------------------
