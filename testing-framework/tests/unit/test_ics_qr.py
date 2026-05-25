"""Тесты google_calendar_url и generate_qr.

QR проверяем фактом создания файла — содержимое PNG это уже тесты Pillow/qrcode.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.models import Event, EventStatus, EventType
from app.services.ics import google_calendar_url
from app.services.qr import generate_qr

# ---------------------------------------------------------------------------
# google_calendar_url
# ---------------------------------------------------------------------------

def _make_event(title="Test", location="ауд. 101", duration_hours=2):
    return Event(
        title=title,
        description="desc",
        event_type=EventType.OPEN_DAY,
        starts_at=datetime(2026, 7, 15, 14, 0, 0),
        ends_at=datetime(2026, 7, 15, 14 + duration_hours, 0, 0),
        location=location,
        capacity=30,
        organizer_id=None,
        status=EventStatus.PUBLISHED,
    )


def test_google_calendar_url_has_event_title():
    url = google_calendar_url(_make_event(title="День открытых дверей"))
    qs = parse_qs(urlparse(url).query)
    assert "День открытых дверей" in qs["text"][0]


def test_google_calendar_url_encodes_dates_in_required_format():
    """Google Calendar ждёт диапазон `YYYYMMDDTHHMMSS/YYYYMMDDTHHMMSS`."""
    url = google_calendar_url(_make_event())
    qs = parse_qs(urlparse(url).query)
    dates = qs["dates"][0]
    assert "/" in dates
    start, end = dates.split("/")
    assert start.startswith("20260715T")
    assert end.startswith("20260715T")


def test_google_calendar_url_handles_missing_ends_at():
    """Если ends_at не задан — Google Calendar получит дефолт +1 час от starts_at."""
    event = _make_event()
    event.ends_at = None
    url = google_calendar_url(event)
    qs = parse_qs(urlparse(url).query)
    # Не падает и возвращает корректный URL
    assert "dates" in qs


def test_google_calendar_url_includes_location():
    url = google_calendar_url(_make_event(location="ауд. 301, корп. А"))
    qs = parse_qs(urlparse(url).query)
    assert "ауд. 301, корп. А" in qs["location"][0]


def test_google_calendar_url_truncates_long_description():
    """5000-символьное описание не должно раздуть URL — режем до 80 chars."""
    event = _make_event(title="Test")
    event.description = "Описание " * 1000

    url = google_calendar_url(event)

    qs = parse_qs(urlparse(url).query)
    # Декодированное description не больше лимита (80) + 1 за многоточие
    assert len(qs["details"][0]) <= 80
    assert qs["details"][0].endswith("…")


def test_google_calendar_url_truncates_long_title():
    event = _make_event(title="Очень длинное название " * 50)
    url = google_calendar_url(event)
    qs = parse_qs(urlparse(url).query)
    assert len(qs["text"][0]) <= 60
    assert qs["text"][0].endswith("…")


def test_google_calendar_url_omits_empty_params():
    """Если описания/места нет — соответствующих параметров в URL нет вообще."""
    event = _make_event(title="Только дата", location="")
    event.description = None
    event.location = None
    url = google_calendar_url(event)
    qs = parse_qs(urlparse(url).query)
    assert "details" not in qs
    assert "location" not in qs


def test_google_calendar_url_total_length_under_1000_chars():
    """URL должен влезать в inline-кнопку МАКС — эмпирический потолок ~1000 chars
    (с запасом на URL-encode кириллицы — ~9 байт на символ).
    """
    event = _make_event(
        title="День открытых дверей факультета ИТ",
        location="ауд. 301, корп. А, проспект Вернадского, 78",
    )
    event.description = (
        "Приходите познакомиться с факультетом, увидеть лаборатории, "
        "пообщаться со студентами и преподавателями."
    )
    url = google_calendar_url(event)
    assert len(url) < 1000, f"URL = {len(url)} символов: {url[:200]}…"


# ---------------------------------------------------------------------------
# generate_qr
# ---------------------------------------------------------------------------

def test_generate_qr_creates_png_file(tmp_path, monkeypatch):
    """Подменяем qr_dir на временную папку, проверяем что файл создаётся."""
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "qr_dir", str(tmp_path))

    token = "abc123def456"
    path = generate_qr(token)

    p = Path(path)
    assert p.exists()
    assert p.suffix == ".png"
    assert p.stat().st_size > 100  # картинка точно не пустая


def test_generate_qr_is_idempotent(tmp_path, monkeypatch):
    """Повторный вызов с тем же токеном не создаёт второй файл (кеш по имени)."""
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "qr_dir", str(tmp_path))

    token = "stable-token-xyz"
    path1 = generate_qr(token)
    mtime1 = Path(path1).stat().st_mtime
    path2 = generate_qr(token)
    mtime2 = Path(path2).stat().st_mtime

    assert path1 == path2
    assert mtime1 == mtime2, "файл не должен перезаписываться при повторном вызове"
