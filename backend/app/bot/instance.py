"""Синглтоны клиента MAX и диспетчера на весь процесс.

Жизненный цикл клиента (открытие/закрытие HTTP-сессии) — в `app.main`.
"""
from __future__ import annotations

from app.bot.client import MaxClient
from app.bot.dispatcher import Dispatcher
from app.config import get_settings

_settings = get_settings()

# Один HTTP-клиент на процесс — переиспользует пул соединений.
bot: MaxClient = MaxClient(token=_settings.bot_token)
dp: Dispatcher = Dispatcher()
