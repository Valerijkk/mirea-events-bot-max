"""Единый fake MaxClient для unit-тестов бота."""
from __future__ import annotations

from typing import Any


class FakeMaxClient:
    """Тестовый дублёр MaxClient — перехватывает отправленные сообщения."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_message(
        self,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        text: str = "",
        keyboard: dict | None = None,
        attachments: list | None = None,
        **kwargs: Any,
    ) -> dict:
        self.messages.append({
            "user_id": user_id,
            "chat_id": chat_id,
            "text": text,
            "keyboard": keyboard,
            "attachments": attachments,
        })
        return {"ok": True}

    async def send_photo_url(self, photo_url: str, **kwargs: Any) -> dict:
        self.messages.append({"photo_url": photo_url, **kwargs})
        return {"ok": True}

    async def send_local_photo(self, file_path: str, **kwargs: Any) -> dict:
        self.messages.append({"photo_local": file_path, **kwargs})
        return {"ok": True}

    async def edit_message(
        self,
        *,
        message_id: int,
        text: str = "",
        keyboard: dict | None = None,
        **kwargs: Any,
    ) -> dict:
        return {"ok": True}

    async def answer_callback(self, *, callback_id: str, text: str = "") -> dict:
        return {"ok": True}

    def last_text(self) -> str:
        """Текст последнего отправленного сообщения."""
        return self.messages[-1]["text"] if self.messages else ""

    def all_texts(self) -> list[str]:
        return [m["text"] for m in self.messages if "text" in m]

    def texts_sent(self) -> list[str]:
        return self.all_texts()

    def texts(self) -> list[str]:
        return self.all_texts()

    def clear(self) -> None:
        self.messages.clear()
