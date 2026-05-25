"""Generic-poller для асинхронных условий SUT.

Применение: дождаться, что планировщик отправил уведомление, что список
обновился, что событие сменило статус и т.п. Это не замена sync_api Playwright
(`expect(locator).to_have_text(...)`) — это для API-уровня.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def wait_for(
    condition: Callable[[], T],
    *,
    timeout_s: float = 5.0,
    poll_interval_s: float = 0.1,
    message: str = "условие не выполнилось",
) -> T:
    """Ждёт первого truthy-значения от condition() или AssertionError по таймауту.

    Параметр условия — callable, который либо возвращает значение (если оно
    truthy — оно же и результат), либо None/False, чтобы продолжить опрос.
    Исключения внутри condition пробрасываются — это сигнал «тест сломан»,
    а не «ещё не готово».
    """
    deadline = time.monotonic() + timeout_s
    last_result: T | None = None
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        last_result = result
        time.sleep(poll_interval_s)
    raise AssertionError(
        f"{message} за {timeout_s}s (последнее значение: {last_result!r})"
    )


def wait_until_equal(
    fn: Callable[[], T],
    expected: T,
    *,
    timeout_s: float = 5.0,
    poll_interval_s: float = 0.1,
    label: str = "значение",
) -> None:
    """Удобная обёртка: ждать пока fn() == expected."""
    deadline = time.monotonic() + timeout_s
    last: T | None = None
    while time.monotonic() < deadline:
        last = fn()
        if last == expected:
            return
        time.sleep(poll_interval_s)
    raise AssertionError(
        f"{label} != {expected!r} за {timeout_s}s (последнее: {last!r})"
    )
