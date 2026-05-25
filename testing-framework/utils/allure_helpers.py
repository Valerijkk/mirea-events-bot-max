"""Тонкий слой над allure-pytest: безопасный к отсутствию allure.

В CI allure всегда установлен; для разработчика, который ставит только
`requirements-dev.txt`, его может не быть. Эти обёртки превращаются в
no-op, если пакета нет — тесты не падают.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

try:
    import allure  # type: ignore[import-untyped]
    _ALLURE_AVAILABLE = True
except ImportError:  # pragma: no cover — установка прописана в requirements-dev.
    allure = None  # type: ignore[assignment]
    _ALLURE_AVAILABLE = False


T = TypeVar("T")


@contextmanager
def step(title: str) -> Iterator[None]:
    """Контекст-менеджер для шага. `with step('Залогиниться'): ...`"""
    if _ALLURE_AVAILABLE:
        with allure.step(title):  # type: ignore[attr-defined]
            yield
    else:
        yield


def attach_json(body: Any, name: str) -> None:
    if not _ALLURE_AVAILABLE:
        return
    import json as _json

    try:
        text = _json.dumps(body, ensure_ascii=False, indent=2, default=str)
    except Exception:
        text = repr(body)
    allure.attach(text, name=name, attachment_type=allure.attachment_type.JSON)  # type: ignore[attr-defined]


def attach_text(text: str, name: str) -> None:
    if not _ALLURE_AVAILABLE:
        return
    allure.attach(text, name=name, attachment_type=allure.attachment_type.TEXT)  # type: ignore[attr-defined]


def attach_screenshot(png_bytes: bytes, name: str = "screenshot") -> None:
    if not _ALLURE_AVAILABLE:
        return
    allure.attach(png_bytes, name=name, attachment_type=allure.attachment_type.PNG)  # type: ignore[attr-defined]


def tag(*labels: str) -> Callable[[T], T]:
    """Декоратор `@tag("smoke", "auth")` — навешивает severity/feature/story-метки."""
    def decorator(fn: T) -> T:
        if not _ALLURE_AVAILABLE:
            return fn
        for label in labels:
            fn = allure.tag(label)(fn)  # type: ignore[attr-defined]
        return fn
    return decorator
