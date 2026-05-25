"""Учёт длительности каждого теста + сводный отчёт.

Pytest умеет `--durations=N`, но это печать в stdout. Нам нужен
машинно-читаемый JSON (`reports/timings.json`) + Markdown-сводка
(`reports/timings.md`) для приложения к багрепортам и для CI-артефактов.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class TestTiming:
    __test__ = False

    nodeid: str
    duration_s: float
    outcome: str   # passed / failed / skipped / error / xfailed / xpassed


def dump_json(timings: Iterable[TestTiming], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(t) for t in timings]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def dump_markdown(timings: list[TestTiming], path: Path, *, top: int = 25) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_ = sorted(timings, key=lambda t: t.duration_s, reverse=True)
    total = sum(t.duration_s for t in timings)
    passed = sum(1 for t in timings if t.outcome == "passed")
    failed = sum(1 for t in timings if t.outcome == "failed")
    skipped = sum(1 for t in timings if t.outcome == "skipped")

    lines = [
        "# Длительность тестов",
        "",
        f"Всего тестов: **{len(timings)}** · "
        f"passed: **{passed}** · failed: **{failed}** · skipped: **{skipped}** · "
        f"суммарно: **{total:.2f} с**",
        "",
        f"## Top-{top} самых медленных",
        "",
        "| # | Тест | Результат | Время, с |",
        "|---|------|-----------|----------|",
    ]
    for i, t in enumerate(sorted_[:top], 1):
        lines.append(f"| {i} | `{t.nodeid}` | {t.outcome} | {t.duration_s:.3f} |")

    if failed:
        lines += ["", "## Упавшие", "", "| Тест | Время, с |", "|------|----------|"]
        for t in sorted_:
            if t.outcome == "failed":
                lines.append(f"| `{t.nodeid}` | {t.duration_s:.3f} |")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
