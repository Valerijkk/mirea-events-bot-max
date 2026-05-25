"""Утилиты путей к артефактам (screenshots, traces)."""
from __future__ import annotations

import re
from pathlib import Path

from config.settings import get_settings


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)[:120]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def screenshots_dir(test_id: str) -> Path:
    base = get_settings().artifacts_dir / "playwright" / safe_name(test_id)
    return ensure_dir(base)


def screenshot_path(test_id: str, suffix: str = "failure") -> Path:
    return screenshots_dir(test_id) / f"{safe_name(suffix)}.png"


def trace_path(test_id: str) -> Path:
    return screenshots_dir(test_id) / "trace.zip"
