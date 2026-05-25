"""Сравнение состояний (списков событий, регистраций) до/после действия.

Применение: тест записал пользователя, нужно проверить что у конкретного
события увеличился счётчик подтверждённых, но остальные события не
тронуты. Прямое сравнение dict'ов даёт многострочный diff — этот модуль
выдаёт компактный.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def index_by(items: Iterable[dict[str, Any]], key: str = "id") -> dict[Any, dict[str, Any]]:
    """Превратить список в dict по полю-ключу. Дубликаты — последний выигрывает."""
    return {item[key]: item for item in items}


def diff_collections(
    before: Iterable[dict[str, Any]],
    after: Iterable[dict[str, Any]],
    *,
    key: str = "id",
    track: tuple[str, ...] = (),
) -> dict[str, list[Any]]:
    """Возвращает {"added": [...], "removed": [...], "changed": [...]}.

    `changed` — это записи с изменениями в полях из track. Если track пуст,
    `changed` всегда пуст (changed считается только относительно явно
    отслеживаемых полей, чтобы не реагировать на updated_at и пр.).
    """
    before_idx = index_by(before, key)
    after_idx = index_by(after, key)
    added = [after_idx[k] for k in after_idx.keys() - before_idx.keys()]
    removed = [before_idx[k] for k in before_idx.keys() - after_idx.keys()]
    changed: list[dict[str, Any]] = []
    for k in before_idx.keys() & after_idx.keys():
        if not track:
            continue
        diffs = {f: (before_idx[k].get(f), after_idx[k].get(f)) for f in track}
        diffs = {f: pair for f, pair in diffs.items() if pair[0] != pair[1]}
        if diffs:
            changed.append({"id": k, "diff": diffs})
    return {"added": added, "removed": removed, "changed": changed}


def only_changed_ids(diff: dict[str, list[Any]]) -> set[Any]:
    """Объединение id из added/removed/changed — полезно для assert."""
    ids: set[Any] = set()
    ids.update(item.get("id") for item in diff.get("added", []))
    ids.update(item.get("id") for item in diff.get("removed", []))
    ids.update(item.get("id") for item in diff.get("changed", []))
    return ids
