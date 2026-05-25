"""Автогенератор баг-репорта в формате Markdown при падении теста.

Когда тест падает, особенно UI/e2e, документировать руками: тащить скрин,
выписывать traceback, копировать nodeid — больно и легко забыть деталь.
Этот модуль формирует одностраничный `.md`, готовый к закидыванию в
Jira/Issue/Confluence: контекст, шаги воспроизведения, артефакты,
окружение, traceback. Имя файла — детерминированное по nodeid, чтобы
повторный прогон перезаписал актуальный отчёт.

Подключается из pytest_runtest_makereport (см. conftest.py).
"""
from __future__ import annotations

import os
import platform
import re
import sys
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass
class BugReport:
    """Структура того, что попадёт в .md. Заполняется хуками по мере прогона."""

    nodeid: str
    test_file: str
    test_name: str
    failed_at: datetime
    duration_s: float
    markers: list[str] = field(default_factory=list)
    error_type: str = ""
    error_message: str = ""
    traceback: str = ""
    screenshot_path: str | None = None
    video_path: str | None = None
    har_path: str | None = None
    captured_log: str = ""
    captured_stdout: str = ""
    last_request: dict[str, str] | None = None
    last_response: dict[str, str] | None = None
    env_snapshot: dict[str, str] = field(default_factory=dict)
    reproduction_command: str = ""


def file_path_for(nodeid: str, root: Path) -> Path:
    """Детерминированный путь к .md по nodeid."""
    safe = _SAFE_NAME_RE.sub("_", nodeid).strip("_")[:180]
    return root / f"{safe}.md"


def render(report: BugReport) -> str:
    """Заполнить шаблон. Чистый I/O вынесен в `write`."""
    repro = report.reproduction_command or f"pytest {report.nodeid} -v"
    body = textwrap.dedent(f"""\
        # Bug report: {report.test_name}

        > Сформировано автоматически фреймворком тестирования mirea-events-bot.
        > Файл: `{report.test_file}` · node: `{report.nodeid}`

        ## Сводка
        | Параметр | Значение |
        |---|---|
        | Когда упало | {report.failed_at:%Y-%m-%d %H:%M:%S} |
        | Длительность | {report.duration_s:.2f} с |
        | Маркеры | {", ".join(report.markers) or "—"} |
        | Ошибка | `{report.error_type}` |

        ## Сообщение
        ```
        {report.error_message.strip() or "—"}
        ```

        ## Шаги воспроизведения
        1. Поднять SUT: `python -m uvicorn app.main:app --port 8080`.
        2. Накатить демо-данные: `python -m app.cli.init_project`.
        3. Запустить упавший тест отдельно: `{repro}`.

        ## Артефакты
        - Скриншот: {_link(report.screenshot_path)}
        - Видео: {_link(report.video_path)}
        - HAR-trace: {_link(report.har_path)}

        ## Последний HTTP-запрос
        {_kv_block(report.last_request) or "_не зафиксирован_"}

        ## Последний HTTP-ответ
        {_kv_block(report.last_response) or "_не зафиксирован_"}

        ## Захваченные логи
        ```
        {_truncate(report.captured_log, 4000) or "—"}
        ```

        ## Stdout/stderr теста
        ```
        {_truncate(report.captured_stdout, 2000) or "—"}
        ```

        ## Traceback
        ```python
        {_truncate(report.traceback, 6000) or "—"}
        ```

        ## Окружение
        {_kv_block(report.env_snapshot) or "—"}
        """)
    return body


def write(report: BugReport, root: Path) -> Path:
    """Записать .md и вернуть путь."""
    root.mkdir(parents=True, exist_ok=True)
    target = file_path_for(report.nodeid, root)
    target.write_text(render(report), encoding="utf-8")
    return target


def collect_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Снимок окружения для секции «Окружение». Никаких секретов."""
    snapshot = {
        "Python": sys.version.split()[0],
        "Platform": f"{platform.system()} {platform.release()}",
        "Время": datetime.now(UTC).isoformat(timespec="seconds"),
        "Working dir": str(Path.cwd()),
        "Env QA_BASE_URL": os.getenv("QA_BASE_URL", "—"),
        "Env QA_BROWSER": os.getenv("QA_BROWSER", "—"),
        "Env QA_HEADLESS": os.getenv("QA_HEADLESS", "—"),
    }
    if extra:
        snapshot.update(extra)
    return snapshot


def _link(path: str | None) -> str:
    if not path:
        return "_нет_"
    return f"[`{Path(path).name}`]({path})"


def _kv_block(data: dict[str, str] | None) -> str:
    if not data:
        return ""
    lines = []
    for k, v in data.items():
        v_short = _truncate(str(v), 400).replace("\n", " ")
        lines.append(f"- **{k}**: `{v_short}`")
    return "\n".join(lines)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[обрезано, всего {len(text)} символов]"


def from_pytest_item(
    nodeid: str,
    *,
    file_path: str,
    test_name: str,
    duration_s: float,
    error_type: str,
    error_message: str,
    traceback: str,
    markers: Iterable[str] = (),
    screenshot_path: str | None = None,
    video_path: str | None = None,
    captured_log: str = "",
    captured_stdout: str = "",
    last_request: dict[str, str] | None = None,
    last_response: dict[str, str] | None = None,
    env_extra: dict[str, str] | None = None,
) -> BugReport:
    """Фабрика — собрать BugReport из данных, доступных pytest-хуку."""
    return BugReport(
        nodeid=nodeid,
        test_file=file_path,
        test_name=test_name,
        failed_at=datetime.now(UTC),
        duration_s=duration_s,
        markers=list(markers),
        error_type=error_type,
        error_message=error_message,
        traceback=traceback,
        screenshot_path=screenshot_path,
        video_path=video_path,
        captured_log=captured_log,
        captured_stdout=captured_stdout,
        last_request=last_request,
        last_response=last_response,
        env_snapshot=collect_env(env_extra),
        reproduction_command=f"pytest {nodeid} -v --tb=long",
    )
