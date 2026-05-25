"""Self-tests багрепорт-генератора."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


from utils.bug_report import (
    BugReport,
    collect_env,
    file_path_for,
    from_pytest_item,
    render,
    write,
)


def _sample_report(nodeid: str = "tests/api/auth/test_login_neg.py::test_wrong_password") -> BugReport:
    return BugReport(
        nodeid=nodeid,
        test_file="tests/api/auth/test_login_neg.py",
        test_name="test_wrong_password",
        failed_at=datetime(2026, 5, 20, 18, 30, 0),
        duration_s=1.234,
        markers=["api", "neg"],
        error_type="AssertionError",
        error_message="ожидался 401, пришёл 500",
        traceback="Traceback (most recent call last):\n  ...",
        last_request={"method": "POST", "url": "/api/v1/auth/login"},
        last_response={"status": "500", "body": "internal error"},
        env_snapshot={"Python": "3.11.0", "Platform": "Windows"},
        reproduction_command="pytest tests/api/auth/test_login_neg.py::test_wrong_password -v",
    )


def test_render_includes_test_name() -> None:
    md = render(_sample_report())
    assert "test_wrong_password" in md
    assert "AssertionError" in md
    assert "ожидался 401" in md


def test_render_includes_repro_command() -> None:
    md = render(_sample_report())
    assert "pytest tests/api/auth/test_login_neg.py::test_wrong_password" in md


def test_render_handles_missing_artifacts() -> None:
    report = _sample_report()
    md = render(report)
    assert "_нет_" in md  # link на скрин/видео без значения


def test_render_includes_markers_section() -> None:
    md = render(_sample_report())
    assert "api, neg" in md


def test_file_path_for_sanitizes_nodeid(tmp_path: Path) -> None:
    target = file_path_for("tests/api/auth/test_login_neg.py::test_x", tmp_path)
    assert target.parent == tmp_path
    assert ":" not in target.name
    assert target.suffix == ".md"


def test_write_creates_file_on_disk(tmp_path: Path) -> None:
    path = write(_sample_report(), tmp_path)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "test_wrong_password" in text


def test_write_creates_parent_dir(tmp_path: Path) -> None:
    deep = tmp_path / "level" / "another"
    path = write(_sample_report(), deep)
    assert path.exists()


def test_collect_env_returns_basic_keys() -> None:
    env = collect_env({"Custom": "val"})
    assert "Python" in env
    assert "Platform" in env
    assert env["Custom"] == "val"


def test_from_pytest_item_collects_full_report() -> None:
    report = from_pytest_item(
        nodeid="tests/x::test_y",
        file_path="tests/x.py",
        test_name="test_y",
        duration_s=0.5,
        error_type="ValueError",
        error_message="bad value",
        traceback="line 1\nline 2",
        markers=["api"],
    )
    assert report.error_type == "ValueError"
    assert "Python" in report.env_snapshot
    assert "pytest tests/x::test_y" in report.reproduction_command


def test_render_truncates_long_traceback() -> None:
    huge_tb = "x" * 20000
    md = render(BugReport(
        nodeid="a", test_file="b", test_name="c",
        failed_at=datetime.utcnow(), duration_s=0.0,
        traceback=huge_tb,
    ))
    assert "обрезано" in md
