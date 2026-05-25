"""Тонкая обёртка над logging. structlog подключается опционально."""
from __future__ import annotations

import logging
import sys
from typing import Any

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    _CONFIGURED = True


def get_logger(name: str = "qa") -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def mask_secrets(payload: Any) -> Any:
    # Маскируем поля, попадающие в логи: пароли, токены, csrf.
    if not isinstance(payload, dict):
        return payload
    sensitive = {"password", "access_token", "_csrf", "csrf_token", "X-API-Key", "x-api-key"}
    return {k: ("***" if k in sensitive else v) for k, v in payload.items()}
