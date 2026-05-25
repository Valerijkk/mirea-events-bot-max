"""Retry-обёртка для flaky-операций.

В отличие от pytest-rerunfailures (перезапускает тест целиком), эта обёртка
ретраит **внутри** теста — конкретный запрос. Применение: rate-limit,
временная недоступность планировщика, очередь.

Принципы:
* По умолчанию ретраят только сетевые/timeout/429. Бизнес-ошибки (400/422)
  пробрасываем — повтор не поможет.
* Экспоненциальный back-off, но с потолком.
* Жёсткий лимит max_attempts, чтобы один кривой тест не сжёг весь bucket.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

import httpx

T = TypeVar("T")

logger = logging.getLogger("qa.retry")

# По умолчанию повторяем эти статусы. 429 — rate-limit, 502/503/504 — gateway.
DEFAULT_RETRY_STATUSES = frozenset({429, 502, 503, 504})


def retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay_s: float = 0.25,
    max_delay_s: float = 4.0,
    retry_statuses: frozenset[int] = DEFAULT_RETRY_STATUSES,
    label: str = "operation",
) -> T:
    """Ретраит fn() с экспоненциальным back-off.

    Если fn возвращает httpx.Response, проверяет .status_code против retry_statuses.
    Если fn кидает httpx.TransportError или TimeoutException — также ретрай.
    Иные исключения пробрасываются без ретрая.
    """
    last_exc: Exception | None = None
    last_response: httpx.Response | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = fn()
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            logger.info("retry %s/%s: %s — %s", attempt, max_attempts, label, exc)
        else:
            if isinstance(result, httpx.Response) and result.status_code in retry_statuses:
                last_response = result
                logger.info(
                    "retry %s/%s: %s — статус %s",
                    attempt, max_attempts, label, result.status_code,
                )
            else:
                return result
        if attempt == max_attempts:
            break
        delay = min(max_delay_s, base_delay_s * (2 ** (attempt - 1)))
        time.sleep(delay)
    if last_response is not None:
        return last_response  # type: ignore[return-value]
    assert last_exc is not None  # mypy
    raise last_exc
