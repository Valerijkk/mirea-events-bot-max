"""UI-фикстуры поверх Playwright sync_api."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from config.settings import Settings


@pytest.fixture(scope="module")
def playwright_instance() -> Iterator[Playwright]:
    # module, не session: sync_playwright держит ProactorEventLoop открытым,
    # и unit-тесты с asyncio.run() падают, если loop ещё жив к концу прогона.
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="module")
def browser(playwright_instance: Playwright, settings: Settings) -> Iterator[Browser]:
    launcher = getattr(playwright_instance, settings.browser)
    instance = launcher.launch(
        headless=settings.headless,
        slow_mo=settings.slow_mo_ms,
    )
    yield instance
    instance.close()


@pytest.fixture
def context_factory(
    browser: Browser,
    settings: Settings,
) -> Iterator[Any]:
    # Решение: фабрика, чтобы тест мог запросить второй context (например, два пользователя).
    created: list[BrowserContext] = []
    # Включаем video/trace по настройке. video — папка, не файл: playwright сам генерирует имя.
    video_dir = settings.artifacts_dir / "videos"
    if settings.capture_video:
        video_dir.mkdir(parents=True, exist_ok=True)

    def _factory(**overrides: Any) -> BrowserContext:
        base: dict[str, Any] = {
            "viewport": {
                "width": settings.viewport_width,
                "height": settings.viewport_height,
            },
            "locale": "ru-RU",
            "ignore_https_errors": True,
        }
        if settings.capture_video:
            base["record_video_dir"] = str(video_dir)
            base["record_video_size"] = {
                "width": settings.viewport_width,
                "height": settings.viewport_height,
            }
        base.update(overrides)
        ctx = browser.new_context(**base)
        ctx.set_default_timeout(settings.ui_default_timeout_ms)
        if settings.capture_trace:
            ctx.tracing.start(screenshots=True, snapshots=True, sources=False)
        created.append(ctx)
        return ctx

    yield _factory
    for ctx in created:
        try:
            if settings.capture_trace:
                trace_path = settings.artifacts_dir / "traces" / f"trace-{id(ctx)}.zip"
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                ctx.tracing.stop(path=str(trace_path))
            ctx.close()
        except Exception:
            pass


@pytest.fixture
def context(context_factory: Any) -> Iterator[BrowserContext]:
    ctx = context_factory()
    yield ctx


@pytest.fixture
def page(context: BrowserContext) -> Iterator[Page]:
    page = context.new_page()
    yield page
    page.close()
