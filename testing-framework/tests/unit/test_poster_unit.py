"""Unit-тесты на генератор постера. Чистая функция, in-memory PNG."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models import Event, EventStatus, EventType


def _make_event(db, organizer, **kw) -> Event:
    ev = Event(
        title=kw.get("title", "Тестовое мероприятие"),
        description=kw.get("description", "desc"),
        event_type=kw.get("event_type", EventType.OPEN_DAY),
        starts_at=kw.get("starts_at", datetime.utcnow() + timedelta(days=7)),
        location=kw.get("location", "ауд. 101"),
        capacity=kw.get("capacity", 10),
        duration_minutes=kw.get("duration_minutes", 90),
        format=kw.get("format", "onsite"),
        organizer_id=organizer.id,
        status=kw.get("status", EventStatus.PUBLISHED),
        max_entries=kw.get("max_entries", 1),
    )
    db.add(ev)
    db.commit()
    return ev


def test_poster_generation_produces_valid_png(session, organizer):
    """Постер — это PNG-байты, начинаются с PNG-сигнатуры, >50KB."""
    from app.services.poster import generate_event_poster
    event = _make_event(session, organizer, title="День открытых дверей")

    png_bytes = generate_event_poster(event)

    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n", "не PNG-сигнатура"
    assert len(png_bytes) > 50_000, f"PNG слишком маленький: {len(png_bytes)} bytes"


def test_poster_with_long_title_doesnt_crash(session, organizer):
    """Wrap текста не должен ломаться на очень длинных заголовках."""
    from app.services.poster import generate_event_poster
    event = _make_event(session, organizer, title="Очень длинное название " * 5)

    png = generate_event_poster(event)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_poster_without_location(session, organizer):
    """Постер без места не должен падать — просто пропускаем блок."""
    from app.services.poster import generate_event_poster
    event = _make_event(session, organizer, location=None)
    png = generate_event_poster(event)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
