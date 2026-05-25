"""Диспетчер событий MAX-бота.

Своя реализация вместо `maxapi`: библиотека несовместима с реальным API
по Postman-коллекции организаторов. Поддерживаем long polling и webhook
из одной модели обработчиков.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.bot.client import MaxApiError, MaxClient, get_update_type

logger = logging.getLogger(__name__)

Handler = Callable[[dict, MaxClient], Awaitable[None]]


class Dispatcher:
    """Маршрутизатор событий по полю `update_type`."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def on(self, update_type: str) -> Callable[[Handler], Handler]:
        def decorator(handler: Handler) -> Handler:
            self._handlers.setdefault(update_type, []).append(handler)
            return handler

        return decorator

    async def handle_update(self, update: dict, client: MaxClient) -> None:
        """Ошибки внутри хендлера глотаем — кривой update не должен валить polling."""
        update_type = get_update_type(update) or "unknown"
        handlers = self._handlers.get(update_type, [])
        if not handlers:
            logger.debug("No handler for update_type=%s", update_type)
            return
        for handler in handlers:
            try:
                await handler(update, client)
            except Exception:
                logger.exception("Handler for %s failed", update_type)

    async def run_polling(
        self,
        client: MaxClient,
        *,
        types: list[str] | None = None,
        stop_event: asyncio.Event | None = None,
        poll_timeout: int = 3,
    ) -> None:
        """`stop_event` — для корректного завершения из lifespan."""
        marker: int | None = None
        types = types or list(self._handlers.keys()) or [
            "message_created",
            "bot_started",
            "message_callback",
        ]
        logger.info("Long polling started for types=%s", types)

        while True:
            if stop_event is not None and stop_event.is_set():
                logger.info("Long polling stopped")
                return
            try:
                response = await client.get_updates(marker=marker, types=types, timeout=poll_timeout)
            except asyncio.CancelledError:
                raise
            except MaxApiError as exc:
                logger.warning("MAX /updates returned %s: %s", exc.status_code, exc.body)
                await asyncio.sleep(3)
                continue
            except Exception:
                logger.exception("Long polling iteration failed")
                await asyncio.sleep(3)
                continue

            updates = response.get("updates") or []
            new_marker = response.get("marker")
            if new_marker is not None:
                marker = new_marker

            for update in updates:
                await self.handle_update(update, client)
