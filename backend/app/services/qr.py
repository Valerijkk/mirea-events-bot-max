"""Генерация QR-кодов для пропусков на мероприятия.

QR-код кодирует уникальный `qr_token` из таблицы `registrations`. На входе
организатор сканирует код своим телефоном или ноутбуком — фронтенд страницы
сканера шлёт значение в `POST /api/v1/scan`, и мы отмечаем посещение.

Картинки кешируются на диске: один токен → один файл. Это и быстрее
(не нужно перерисовывать QR при каждом запросе), и предсказуемо
по дисковому потреблению.
"""
from __future__ import annotations

from pathlib import Path

import qrcode

from app.config import get_settings

_settings = get_settings()


def generate_qr(token: str) -> Path:
    """Сгенерировать (или вернуть из кеша) PNG c QR для токена."""
    out_path = _settings.qr_path / f"{token}.png"
    if out_path.exists():
        return out_path

    img = qrcode.make(token)
    img.save(str(out_path))
    return out_path
