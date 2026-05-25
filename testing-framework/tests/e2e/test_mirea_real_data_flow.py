"""E2E на реальных мероприятиях РТУ МИРЭА.

Идея: показать flow на живых событиях с реальными названиями (Дни
открытых дверей, олимпиады, мастер-классы) и реальными mirea.ru-ссылками.

Источник событий — `scripts/fetch_mirea_events.py` (test-only парсер),
который тянет страницы с публичного сайта МИРЭА на 30 дней вперёд.
В проде эти события придут вузом через REST API напрямую.

Поток:
1. Через X-API-Key загружаем реальный батч в БД (sync idempotent).
2. Видим, что они отдаются `GET /api/v1/events`.
3. Каждое событие соответствует публичному контракту.
"""
from __future__ import annotations

import pytest

from core.api_client import ApiClient
from steps.api.event_steps import list_events
from utils.allure_helpers import step
from utils.assertions import assert_event_shape
from utils.schema_check import check_event_response

pytestmark = pytest.mark.e2e


def test_mirea_real_events_flow(
    api_as_integration: ApiClient,
    api_as_admin: ApiClient,
    imported_mirea_events: list[dict],
    mirea_snapshot_events: list[dict],
) -> None:
    """Полный flow на реальных мероприятиях РТУ МИРЭА с публичного сайта."""
    with step("батч импортирован через /api/v1/integration/events/sync"):
        assert imported_mirea_events, "ничего не импортировалось"

        actions = {r["action"] for r in imported_mirea_events}

        assert actions.issubset({"created", "updated"}), (
            f"при импорте получили лишние action'ы: {actions}"
        )

    with step("каталог /api/v1/events содержит импортированные mirea-события"):
        events = list_events(api_as_admin, limit=200)
        snapshot_titles = {evt["title"] for evt in mirea_snapshot_events}
        catalog_titles = {evt["title"] for evt in events}
        matched = snapshot_titles & catalog_titles

        assert matched, (
            f"в каталоге не найдено ни одного mirea-события "
            f"(в snapshot {len(snapshot_titles)}, в каталоге {len(catalog_titles)})"
        )

    mirea_events = [e for e in events if e["title"] in snapshot_titles]

    with step("каждое mirea-событие соответствует публичному контракту GET /events/{id}"):
        for evt in mirea_events[:5]:
            check_event_response(evt)
            assert_event_shape(evt)


def test_mirea_event_titles_are_real(
    api_as_integration: ApiClient,
    api_as_admin: ApiClient,
    imported_mirea_events: list[dict],
    mirea_snapshot_events: list[dict],
) -> None:
    """Названия событий должны быть осмысленными (не «test_event_N»)."""
    events = list_events(api_as_admin, limit=200)
    snapshot_titles = {evt["title"] for evt in mirea_snapshot_events}
    titles_in_catalog = {e["title"] for e in events} & snapshot_titles

    # ни одного «test_event_N» — это регрессия на нашу проверку
    # против тестовых заголовков.
    for title in titles_in_catalog:
        lower = title.lower()

        assert not lower.startswith("test"), f"тестовый title пробрался в БД: {title!r}"
        assert "test event" not in lower, f"тестовый title пробрался в БД: {title!r}"
        assert len(title) >= 5, f"подозрительно короткий title: {title!r}"
