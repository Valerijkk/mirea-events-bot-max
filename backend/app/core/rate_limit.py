"""In-memory rate-limiter (sliding window).

Не slowapi/redis: проект — хакатон-демо в одном процессе, внешний redis тут
переусложнение. Контракт `check()` совместим — заменим на slowapi+redis,
когда понадобится многоинстансная инсталляция.

Sliding window даёт точную семантику «N запросов за окно» без бакетов
и угадывания интервалов; цена памяти — O(max_requests) на активный ключ.

`threading.Lock` — явная гарантия атомарности dict+deque-операций под
thread pool uvicorn'а (CPython GIL «обычно» хватает, но Lock дешёвый).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class InMemoryRateLimiter:
    """Sliding-window лимитер на одну категорию (логин / скан / …).

    Использование::

        limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)
        if not limiter.check(client_ip):
            raise HTTPException(429, "Слишком часто")
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("max_requests и window_seconds должны быть > 0")
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> bool:
        """True — пропустить, False — лимит превышен. Каждый успешный вызов
        регистрирует запрос, поэтому не вызывать дважды на один и тот же.
        """
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self._max:
                return False
            hits.append(now)
            return True

    def reset(self, key: str | None = None) -> None:
        """`key=None` — сброс всех ключей (используется в тестах)."""
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


# Модульные синглтоны. Цифры — против автоматизации, не против людей.
login_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)
# Скан QR щедрый: живой оператор не выйдет за 60/мин, брутфорс упрётся в 429.
scan_limiter = InMemoryRateLimiter(max_requests=60, window_seconds=60)
