"""Генерация ссылки «Добавить в Google Calendar».

Для бота используем URL на Google Calendar — открывается одним
тапом и работает на всех ОС без скачивания файлов:

    https://calendar.google.com/calendar/render?action=TEMPLATE&text=…&dates=YYYYMMDDTHHMMSS/YYYYMMDDTHHMMSS&location=…&details=…
"""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from app.models import Event

# Длительность по умолчанию, если организатор не указал `ends_at`.
_DEFAULT_DURATION_HOURS = 2

# Жёсткий потолок длины полей. Учитываем, что кириллица в URL-encode
# раздувается в ~9 раз (один русский символ → %DX%YY = 6 байт + соседние).
# Чтобы итоговый URL не превышал ~1000 символов (комфортный лимит для
# inline-кнопки в МАКС), исходный текст режем агрессивно.
_DESC_MAX_LEN = 80
_TITLE_MAX_LEN = 60
_LOCATION_MAX_LEN = 60


def _trim(text: str, limit: int) -> str:
    """Безопасно укоротить строку до `limit` символов с «…» в конце."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def google_calendar_url(event: Event) -> str:
    """Короткая ссылка «Добавить в Google Calendar».

    Текстовые поля жёстко обрезаны (см. константы выше): иначе URL >1000 символов
    обрезается клиентом МАКС и кнопка перестаёт работать.
    """
    starts = event.starts_at
    ends = event.ends_at or (starts + timedelta(hours=_DEFAULT_DURATION_HOURS))
    fmt = "%Y%m%dT%H%M%S"

    params: list[tuple[str, str]] = [
        ("action", "TEMPLATE"),
        ("text", _trim(event.title, _TITLE_MAX_LEN)),
        ("dates", f"{starts.strftime(fmt)}/{ends.strftime(fmt)}"),
    ]
    if event.location:
        params.append(("location", _trim(event.location, _LOCATION_MAX_LEN)))
    if event.description:
        params.append(("details", _trim(event.description, _DESC_MAX_LEN)))

    return "https://calendar.google.com/calendar/render?" + urlencode(params)
