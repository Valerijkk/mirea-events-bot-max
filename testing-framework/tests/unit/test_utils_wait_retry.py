"""Self-tests для wait_for и retry."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from utils.retry import retry
from utils.wait_for import wait_for, wait_until_equal


def test_wait_for_returns_first_truthy() -> None:
    counter = {"n": 0}

    def cond() -> int | None:
        counter["n"] += 1
        return 42 if counter["n"] >= 3 else None

    result = wait_for(cond, timeout_s=1.0, poll_interval_s=0.01)
    assert result == 42
    assert counter["n"] >= 3


def test_wait_for_raises_on_timeout() -> None:
    with pytest.raises(AssertionError, match="условие не выполнилось"):
        wait_for(lambda: None, timeout_s=0.05, poll_interval_s=0.01)


def test_wait_for_propagates_exceptions() -> None:
    def broken() -> Any:
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError, match="kaboom"):
        wait_for(broken, timeout_s=1.0)


def test_wait_until_equal_succeeds() -> None:
    seq = iter([1, 1, 2, 3])
    wait_until_equal(lambda: next(seq), 3, timeout_s=1.0, poll_interval_s=0.01)


def test_wait_until_equal_times_out() -> None:
    with pytest.raises(AssertionError, match="последнее: 1"):
        wait_until_equal(lambda: 1, 2, timeout_s=0.05, poll_interval_s=0.01)


def _resp(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("GET", "http://test/x"))


def test_retry_succeeds_on_first_attempt() -> None:
    calls = MagicMock(return_value=_resp(200))
    result = retry(calls, max_attempts=3)
    assert result.status_code == 200, f"Ожидали 200, получили {result.status_code}: {result.text}"
    assert calls.call_count == 1


def test_retry_recovers_after_429() -> None:
    responses = iter([_resp(429), _resp(429), _resp(200)])
    result = retry(lambda: next(responses), max_attempts=3, base_delay_s=0.01)
    assert result.status_code == 200, f"Ожидали 200, получили {result.status_code}: {result.text}"


def test_retry_gives_up_after_max_attempts() -> None:
    result = retry(lambda: _resp(503), max_attempts=2, base_delay_s=0.01)
    assert result.status_code == 503, f"Ожидали 503, получили {result.status_code}: {result.text}"


def test_retry_does_not_retry_business_errors() -> None:
    calls = MagicMock(return_value=_resp(422))
    retry(calls, max_attempts=5, base_delay_s=0.01)
    assert calls.call_count == 1


def test_retry_handles_transport_errors() -> None:
    attempts = {"n": 0}

    def flappy() -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise httpx.ConnectError("net flap")
        return _resp(200)

    result = retry(flappy, max_attempts=3, base_delay_s=0.01)
    assert result.status_code == 200, f"Ожидали 200, получили {result.status_code}: {result.text}"
    assert attempts["n"] == 2


def test_retry_propagates_unexpected_exception() -> None:
    def boom() -> httpx.Response:
        raise ValueError("not a network error")

    with pytest.raises(ValueError):
        retry(boom, max_attempts=3, base_delay_s=0.01)
