"""Позитивные тесты фильтров каталога на реальном датасете МИРЭА.

Источник событий — `scripts/fetch_mirea_events.py` (test-only парсер).
В проде те же события приходят от ИС вуза через REST.

Тесты пишутся в виде «если события есть — они должны соответствовать
фильтру». Если live-парсинг ничего не вернул (нет интернета в CI) —
фикстура SKIP-нет.
"""
from __future__ import annotations

import pytest

from core.api_client import ApiClient
from steps.api.event_steps import list_events
from utils.allure_helpers import step

pytestmark = [pytest.mark.api, pytest.mark.pos]


def test_filter_by_type_olympiad_returns_only_olympiads(
    api_as_integration: ApiClient,
    api_as_admin: ApiClient,
    imported_mirea_events: list[dict],
) -> None:
    with step("GET /events?type=olympiad"):
        events = list_events(api_as_admin, type="olympiad", limit=100)

    non_olympiads = [e["event_type"] for e in events if e["event_type"] != "olympiad"]

    assert not non_olympiads, f"фильтр type=olympiad пропустил: {non_olympiads}"


def test_filter_by_format_online_returns_only_online(
    api_as_integration: ApiClient,
    api_as_admin: ApiClient,
    imported_mirea_events: list[dict],
) -> None:
    with step("GET /events?format=online"):
        events = list_events(api_as_admin, format="online", limit=100)

    non_online = [e["format"] for e in events if e["format"] != "online"]

    assert not non_online, f"фильтр format=online пропустил: {non_online}"


def test_filter_published_excludes_drafts(
    api_as_integration: ApiClient,
    api_as_admin: ApiClient,
    imported_mirea_events: list[dict],
) -> None:
    with step("GET /events?status=published"):
        events = list_events(api_as_admin, status="published", limit=200)

    statuses = {e["status"] for e in events}

    assert statuses <= {"published"}, f"в фильтре published пришли {statuses}"


def test_mirea_events_have_no_empty_titles(
    api_as_integration: ApiClient,
    api_as_admin: ApiClient,
    imported_mirea_events: list[dict],
    mirea_snapshot_events: list[dict],
) -> None:
    """Регрессия: ничего не должно прийти с пустым/нечитаемым title."""
    snapshot_titles = {e["title"] for e in mirea_snapshot_events}
    events = list_events(api_as_admin, limit=200)
    mirea_in_catalog = [e for e in events if e["title"] in snapshot_titles]

    for evt in mirea_in_catalog:
        assert evt["title"] and len(evt["title"]) >= 5, f"короткий title: {evt!r}"

        title_lower = evt["title"].lower()
        # 'тест' как отдельное слово — чтобы не цепляться к «есте**ствен**но», «протес**т**ировано».
        assert not (
            title_lower.startswith("тест ")
            or " тест " in title_lower
            or title_lower.endswith(" тест")
            or "test event" in title_lower
        ), f"остался тестовый title: {evt['title']!r}"
