"""Корневой conftest: подгружает .env, экспортирует фикстуру settings, правит sys.path."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.resolve()
_PROJECT_ROOT = _ROOT.parent
# Без этого pytest не находит config/, core/, pages/, ... при запуске не из директории фреймворка.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
# backend/ — для импорта `app.*` из фикстур mirea/integration.
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Для импорта app.config нужны мин. env-переменные (для случая когда .env проекта не загружен).
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("BOT_USERNAME", "test_bot")
os.environ.setdefault("JWT_SECRET", "test-secret-for-jwt-must-be-long-enough")

# Подгружаем .env как можно раньше, чтобы pydantic-settings увидел переменные.
try:
    from dotenv import load_dotenv

    env_path = _ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass

from config.settings import Settings, get_settings  # noqa: E402
from core.logger import configure_logging  # noqa: E402
from utils import bug_report as bug_report_mod  # noqa: E402
from utils.timings import TestTiming, dump_json, dump_markdown  # noqa: E402

# Глобальный sys.path-импорт фикстур: pytest_plugins должен лежать в самом верхнем conftest.
pytest_plugins = [
    "fixtures.sut_fixtures",
    "fixtures.api_fixtures",
    "fixtures.ui_fixtures",
    "fixtures.auth_fixtures",
    "fixtures.data_fixtures",
    "fixtures.mirea_fixtures",
]

_TIMINGS: list[TestTiming] = []


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session", autouse=True)
def _configure_logging(settings: Settings) -> None:
    configure_logging(settings.log_level)


@pytest.fixture(scope="session", autouse=True)
def _ensure_reports_dir(settings: Settings) -> None:
    target = settings.artifacts_dir
    target.mkdir(parents=True, exist_ok=True)
    (target / "bugs").mkdir(parents=True, exist_ok=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # type: ignore[no-untyped-def]
    outcome = yield
    report = outcome.get_result()

    # Учёт длительности — на этапе call, чтобы setup/teardown не размазывали.
    if report.when == "call":
        _TIMINGS.append(TestTiming(
            nodeid=item.nodeid,
            duration_s=report.duration,
            outcome=report.outcome,
        ))

    if report.when != "call" or not report.failed:
        return

    # 1. Скриншот для UI-падений.
    funcargs = getattr(item, "funcargs", {}) or {}
    page = (
        funcargs.get("page")
        or funcargs.get("logged_in_admin_page")
        or funcargs.get("logged_in_organizer_page")
    )
    screenshot_path: str | None = None
    video_path: str | None = None
    if page is not None:
        try:
            from core.artifacts import screenshot_path as _screenshot_path

            shot = _screenshot_path(item.nodeid, "failure")
            page.screenshot(path=str(shot), full_page=True)
            screenshot_path = str(shot)
            report.sections.append(("screenshot", screenshot_path))
            try:
                video = page.video
                if video is not None:
                    video_path = str(video.path())
            except Exception:
                video_path = None
        except Exception:
            pass

    # 2. Bug report .md — для всех упавших тестов, не только UI.
    try:
        reports_root = Path(get_settings().artifacts_dir)
        bug_root = reports_root / "bugs"

        excinfo = call.excinfo
        error_type = type(excinfo.value).__name__ if excinfo else "Unknown"
        error_message = str(excinfo.value) if excinfo else ""
        traceback = report.longreprtext or ""
        captured_log = "\n".join(
            text for header, text in report.sections if "log" in header.lower()
        )
        captured_stdout = "\n".join(
            text for header, text in report.sections if "stdout" in header.lower()
        )
        markers = sorted(m.name for m in item.iter_markers())

        bug = bug_report_mod.from_pytest_item(
            nodeid=item.nodeid,
            file_path=str(item.location[0]) if item.location else "",
            test_name=item.name,
            duration_s=report.duration,
            error_type=error_type,
            error_message=error_message,
            traceback=traceback,
            markers=markers,
            screenshot_path=screenshot_path,
            video_path=video_path,
            captured_log=captured_log,
            captured_stdout=captured_stdout,
        )
        bug_path = bug_report_mod.write(bug, bug_root)
        report.sections.append(("bug-report", str(bug_path)))
    except Exception:
        # Никогда не валим прогон, если генератор багрепортов сам кривой.
        pass


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # type: ignore[no-untyped-def]
    if not _TIMINGS:
        return
    try:
        settings = get_settings()
        root = Path(settings.artifacts_dir)
        dump_json(_TIMINGS, root / "timings.json")
        dump_markdown(_TIMINGS, root / "timings.md")
    except Exception:
        pass


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # Удобно: тест в tests/api/* получает маркер api, в tests/ui/* — ui, и т.д.
    auto_markers = {
        "tests/unit/": "unit",
        "tests/api/": "api",
        "tests/ui/": "ui",
        "tests/integration/": "integration",
        "tests/e2e/": "e2e",
    }
    for item in items:
        rel = item.nodeid.replace(os.sep, "/")
        for prefix, marker in auto_markers.items():
            if prefix in rel:
                item.add_marker(getattr(pytest.mark, marker))
                break
        if "_pos" in item.name or "_pos.py" in rel:
            item.add_marker(pytest.mark.pos)
        if "_neg" in item.name or "_neg.py" in rel:
            item.add_marker(pytest.mark.neg)
