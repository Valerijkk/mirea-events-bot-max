"""Self-tests для utils.timings."""
from __future__ import annotations

import json
from pathlib import Path

from utils.timings import TestTiming, dump_json, dump_markdown


def _sample() -> list[TestTiming]:
    return [
        TestTiming("a", 0.5, "passed"),
        TestTiming("b", 1.2, "failed"),
        TestTiming("c", 0.05, "passed"),
        TestTiming("d", 0.001, "skipped"),
    ]


def test_dump_json_writes_valid_array(tmp_path: Path) -> None:
    target = tmp_path / "t.json"
    dump_json(_sample(), target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert len(data) == 4
    assert data[0]["nodeid"] == "a"


def test_dump_markdown_orders_by_slowest(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    dump_markdown(_sample(), target, top=3)
    text = target.read_text(encoding="utf-8")
    pos_b = text.find("`b`")
    pos_a = text.find("`a`")
    pos_c = text.find("`c`")
    assert pos_b < pos_a < pos_c, "Top-{top} должен идти от самого медленного"


def test_dump_markdown_summarizes_counts(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    dump_markdown(_sample(), target)
    text = target.read_text(encoding="utf-8")
    assert "passed: **2**" in text
    assert "failed: **1**" in text
    assert "skipped: **1**" in text


def test_dump_markdown_includes_failed_section(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    dump_markdown(_sample(), target)
    text = target.read_text(encoding="utf-8")
    assert "## Упавшие" in text
    assert "`b`" in text.split("## Упавшие")[1]
