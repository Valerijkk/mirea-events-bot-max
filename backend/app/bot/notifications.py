"""Отправка сообщений пользователям ИЗВНЕ хендлеров бота (рассылки, reminders, waitlist).

Функции возвращают `bool` и глотают исключения — один заблокировавший
бота пользователь не должен ронять цикл рассылки.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.bot.client import MaxApiError
from app.bot.instance import bot

logger = logging.getLogger(__name__)


async def send_text(
    chat_id: int,
    text: str,
    *,
    attachments: list[dict] | None = None,
) -> bool:
    """В MAX личка бота — это user_id. Параметр `chat_id` здесь — это и есть
    user_id (handlers.py всегда кладёт user_id в это поле).
    """
    try:
        await bot.send_message(text=text, user_id=chat_id, attachments=attachments)
        return True
    except MaxApiError as exc:
        logger.warning("MAX отказал при отправке в %s: %s", chat_id, exc)
        return False
    except Exception as exc:
        logger.warning("Не удалось отправить сообщение в %s: %s", chat_id, exc)
        return False


async def send_photo(
    chat_id: int,
    photo_path: Path,
    caption: str | None = None,
) -> bool:
    """QR-пропуск: предпочитаем `send_photo_url` через `QR_PUBLIC_BASE_URL`
    (стабильный путь — МАКС сам скачивает картинку), upload оставлен как
    fallback, потому что формат ответа `/uploads` плавает между версиями API.

    Если оба варианта не сработали — у пользователя уже есть отдельным
    сообщением текстовый код RG-XXXXXX, его на входе достаточно.
    """
    from app.config import get_settings
    public_base = (get_settings().qr_public_base_url or "").rstrip("/")

    if public_base:
        try:
            url = f"{public_base}/qr/{photo_path.name}"
            await bot.send_photo_url(url, user_id=chat_id, caption=caption)
            return True
        except Exception as exc:
            logger.warning(
                "send_photo_url не сработал (url=%s): %s — пробуем upload",
                f"{public_base}/qr/{photo_path.name}", exc,
            )

    try:
        await bot.send_local_photo(str(photo_path), user_id=chat_id, caption=caption)
        return True
    except MaxApiError as exc:
        logger.warning("MAX отказал при отправке фото в %s: %s", chat_id, exc)
    except Exception as exc:
        logger.warning("Не удалось отправить фото в %s: %s", chat_id, exc)

    # Не пишем «временная проблема» — это особенность текущей версии MAX API.
    fallback = caption or (
        "ℹ️ QR-пропуск картинкой не отправили — на входе достаточно "
        "показать код записи RG-… из предыдущего сообщения."
    )
    return await send_text(chat_id, fallback)
