"""Иерархия исключений фреймворка."""
from __future__ import annotations

from typing import Any


class QaError(Exception):
    pass


class ConfigError(QaError):
    pass


class ApiError(QaError):
    # Поднимается из Step-ов, когда HTTP-ответ SUT не совпадает с ожидаемым.

    def __init__(self, response: Any, message: str | None = None) -> None:
        self.response = response
        status = getattr(response, "status_code", "?")
        try:
            body = response.text[:400]
        except Exception:
            body = "<no body>"
        super().__init__(message or f"API {status}: {body}")


class UiError(QaError):
    pass
