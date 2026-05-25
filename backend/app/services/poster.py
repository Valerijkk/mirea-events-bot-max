"""Генерация печатного постера мероприятия (PNG).

Логика: берём deeplink-payload события → собираем URL вида
`https://max.me/<bot_username>?start=<payload>` → рисуем большой QR-код
на белом холсте формата A4 (1240×1754 при 150 DPI) с заголовком,
датой, местом и подписью «Сканируй и записывайся».

Возвращает байты PNG. Не сохраняем файл — это одноразовый артефакт для
скачивания, кешировать смысла нет.

Зависимости: только `qrcode` + `Pillow` (уже стоят, для QR-пропусков).
"""
from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

import qrcode
from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.models import Event

# A4 при 150 DPI: 1240×1754 пикселей. Достаточно для качественной A4-печати.
_A4_W = 1240
_A4_H = 1754

# Размер QR — большой, чтобы сканировать с 1.5-2 метров (фото на стене).
_QR_SIZE = 800

# Размеры шрифтов. Используем default PIL-шрифт — без зависимости от системных
# фонтов. В прод-варианте подгрузили бы Inter/Montserrat.
_TITLE_FONT_SIZE = 64
_BODY_FONT_SIZE = 32
_FOOTER_FONT_SIZE = 28


def _load_font(size: int) -> Any:
    """Попробовать DejaVuSans (есть в Pillow-стандарте), иначе bitmap-fallback.

    Без TTF получится моноширинный bitmap — некрасиво, но печатается.
    Возвращаемый тип `Any`: Pillow стабилизировал ImageFont/FreeTypeFont по-разному
    в разных версиях, оба объекта duck-typed для draw.text().
    """
    for candidate in ("DejaVuSans-Bold.ttf", "arial.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Очень простой word-wrap по символам. Для постера хватает."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 > max_chars:
            if current:
                lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip()
    if current:
        lines.append(current)
    return lines


def generate_event_poster(event: Event) -> bytes:
    """Сгенерировать PNG-постер мероприятия (A4, 150 DPI). Возвращает bytes."""
    bot_username = get_settings().bot_username
    deeplink = f"https://max.me/{bot_username}?start={event.deeplink_payload}"

    # Сам QR — высокая коррекция ошибок, чтобы переживал смятие/печать.
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=20,
        border=2,
    )
    qr.add_data(deeplink)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    # Resampling.LANCZOS — современный путь (Pillow 10+); Image.LANCZOS deprecated.
    qr_img = qr_img.resize((_QR_SIZE, _QR_SIZE), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (_A4_W, _A4_H), "white")
    draw = ImageDraw.Draw(canvas)

    title_font = _load_font(_TITLE_FONT_SIZE)
    body_font = _load_font(_BODY_FONT_SIZE)
    footer_font = _load_font(_FOOTER_FONT_SIZE)

    type_label = {
        "open_day": "ДЕНЬ ОТКРЫТЫХ ДВЕРЕЙ",
        "masterclass": "МАСТЕР-КЛАСС",
        "olympiad": "ОЛИМПИАДА",
        "tour": "ЭКСКУРСИЯ",
        "consultation": "КОНСУЛЬТАЦИЯ",
    }.get(event.event_type, "МЕРОПРИЯТИЕ")
    draw.text((80, 80), "РТУ МИРЭА", fill="#94a3b8", font=footer_font)
    draw.text((80, 130), type_label, fill="#4f46e5", font=body_font)

    title_lines = _wrap_text(event.title, max_chars=28)
    y = 200
    # Жёсткий лимит в 3 строки — длинные названия лучше обрезать, чем
    # ронять QR ниже области печати.
    for line in title_lines[:3]:
        draw.text((80, y), line, fill="#0f172a", font=title_font)
        y += _TITLE_FONT_SIZE + 8

    y += 30
    date_str = event.starts_at.strftime("%d.%m.%Y · %H:%M")
    draw.text((80, y), f"🗓  {date_str}", fill="#334155", font=body_font)
    y += _BODY_FONT_SIZE + 20
    if event.location:
        for line in _wrap_text(event.location, max_chars=42)[:2]:
            draw.text((80, y), f"📍  {line}", fill="#334155", font=body_font)
            y += _BODY_FONT_SIZE + 12

    qr_x = (_A4_W - _QR_SIZE) // 2
    qr_y = _A4_H - _QR_SIZE - 220
    canvas.paste(qr_img, (qr_x, qr_y))

    cta = "Наведи камеру и запишись"
    cta_bbox = draw.textbbox((0, 0), cta, font=body_font)
    cta_w = cta_bbox[2] - cta_bbox[0]
    draw.text(
        ((_A4_W - cta_w) // 2, qr_y - _BODY_FONT_SIZE - 20),
        cta, fill="#0f172a", font=body_font,
    )

    footer = f"@{bot_username} · бот РТУ МИРЭА в МАХ"
    foot_bbox = draw.textbbox((0, 0), footer, font=footer_font)
    foot_w = foot_bbox[2] - foot_bbox[0]
    draw.text(
        ((_A4_W - foot_w) // 2, qr_y + _QR_SIZE + 30),
        footer, fill="#64748b", font=footer_font,
    )

    draw.text(
        (80, _A4_H - 60),
        f"Сгенерировано {datetime.now(UTC).strftime('%d.%m.%Y')} · mirea-events-bot",
        fill="#cbd5e1", font=footer_font,
    )

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()
