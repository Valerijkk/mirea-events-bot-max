"""Подготовка SUT: ожидание /readyz, опциональный spawn uvicorn."""
from __future__ import annotations

import time
from collections.abc import Iterator

import httpx
import pytest

from config.settings import Settings
from config.urls import path_readyz


def _ping_readyz(base_url: str, timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout) as client:
            resp = client.get(path_readyz())
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def sut_ready(settings: Settings) -> Iterator[bool]:
    # External режим: ждём /readyz до sut_ready_timeout.
    # Если SUT не поднят — все API/UI тесты SKIPят сами через зависимость от этой фикстуры.
    deadline = time.monotonic() + settings.sut_ready_timeout
    ready = False
    # Проверяем через api_base_url (прямой бэкенд) или base_url (nginx)
    check_url = settings.effective_api_base_url
    while time.monotonic() < deadline:
        if _ping_readyz(check_url):
            ready = True
            break
        time.sleep(0.5)
    if not ready:
        pytest.skip(
            f"SUT не отвечает на {settings.base_url}{path_readyz()} "
            f"в течение {settings.sut_ready_timeout}s. Запустите uvicorn app.main:app --port 8080."
        )
    yield ready
