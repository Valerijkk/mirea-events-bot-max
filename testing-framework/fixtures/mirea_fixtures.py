"""Фикстуры для QA-тестов на реальных мероприятиях РТУ МИРЭА.

Используют test-only-парсер `scripts/fetch_mirea_events.py`:
  1. Если есть кэш-файл `scripts/.mirea_cache.json` — берём оттуда.
  2. Если нет — тянем с mirea.ru один раз за сессию.
  3. Фильтруем по окну [now, now+30 дней].

Парсер живёт **вне** `app/` намеренно: на проде ИС вуза кладёт события
напрямую через `POST /api/v1/integration/events/sync`, локального парсера
быть не должно.
"""
from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core.api_client import ApiClient
from steps.api.integration_steps import sync_events

# Подкладываем корень репозитория в sys.path, чтобы импортировать
# scripts/fetch_mirea_events как обычный модуль (только при локальной разработке).
# В CI scripts/ отсутствует — тесты автоматически скипаются.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from scripts.fetch_mirea_events import (
        fetch_all,
        filter_within_days,
        load_cache,
        save_cache,
    )
    _SCRIPTS_AVAILABLE = True
except ImportError:
    _SCRIPTS_AVAILABLE = False

_CACHE_PATH = _REPO_ROOT / "scripts" / ".mirea_cache.json"


@pytest.fixture(scope="session")
def mirea_snapshot_events() -> list[dict[str, Any]]:
    """Реальные события РТУ МИРЭА в формате EventSyncItem.

    Сначала пробуем кэш, иначе тянем live с mirea.ru. Если live тоже
    недоступен (нет интернета в CI) или scripts/ недоступен — возвращаем
    пустой список, тесты скипнутся через `assert events`.
    """
    if not _SCRIPTS_AVAILABLE:
        return []

    cached = load_cache(_CACHE_PATH)
    if cached:
        events = cached
    else:
        try:
            events = fetch_all()
            if events:
                save_cache(_CACHE_PATH, events)
        except Exception:
            events = []

    fresh = filter_within_days(events, days=30)
    return [evt.to_sync_item() for evt in fresh]


@pytest.fixture(scope="session")
def mirea_snapshot_by_type(
    mirea_snapshot_events: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Группировка событий по event_type — для параметризации по open_day/olympiad/etc."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for evt in mirea_snapshot_events:
        grouped.setdefault(evt["event_type"], []).append(evt)
    return grouped


@pytest.fixture
def imported_mirea_events(
    api_as_integration: ApiClient,
    mirea_snapshot_events: list[dict[str, Any]],
) -> Iterator[list[dict[str, Any]]]:
    """Импортирует свежий батч через `/api/v1/integration/events/sync`.

    Отмечаем все как `auto_publish=True`, чтобы они сразу появлялись в
    каталоге и были видны read-only тестам. Cleanup не делаем — sync
    идемпотентный по `(source, external_id)`, повторный прогон апдейтит.
    """
    if not mirea_snapshot_events:
        pytest.skip("Не удалось получить события с mirea.ru (нет кэша/интернета).")

    response = sync_events(api_as_integration, mirea_snapshot_events, auto_publish=True)
    yield response["results"]
