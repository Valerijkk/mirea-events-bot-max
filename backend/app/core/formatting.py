"""Единый источник форматирования дат/длительностей для бота и админки.

Jinja2 шаблоны вызывают `format_event_dt` напрямую.
"""
from __future__ import annotations

from datetime import datetime


def format_event_dt(dt: datetime | None) -> str:
    """«25.05.2026 в 14:30» — день месяц год + время. Пустые значения → «—»."""
    if dt is None:
        return "—"
    return dt.strftime("%d.%m.%Y в %H:%M")


def format_duration_minutes(minutes: int | None) -> str:
    """«1 ч 30 мин» или «30 мин». None / ≤0 → «длительность не указана»."""
    if not minutes or minutes <= 0:
        return "длительность не указана"
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} ч {mins} мин"
    if hours:
        return f"{hours} ч"
    return f"{mins} мин"
