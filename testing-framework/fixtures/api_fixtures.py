"""API-фикстуры: клиенты по ролям."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from config.settings import Settings
from core.api_client import ApiClient
from core.auth_helper import (
    admin_client as _admin_client,
)
from core.auth_helper import (
    make_unauthed_client,
    organizer_client,
    second_organizer_client,
)


@pytest.fixture(scope="session")
def api_client(settings: Settings, sut_ready: bool) -> Iterator[ApiClient]:
    client = make_unauthed_client(settings)
    yield client
    client.close()


@pytest.fixture(scope="session")
def api_as_admin(settings: Settings, sut_ready: bool) -> Iterator[ApiClient]:
    client = _admin_client(settings)
    yield client
    client.close()


@pytest.fixture(scope="session")
def api_as_organizer(settings: Settings, sut_ready: bool) -> Iterator[ApiClient]:
    client = organizer_client(settings)
    yield client
    client.close()


@pytest.fixture(scope="session")
def api_as_second_organizer(settings: Settings, sut_ready: bool) -> Iterator[ApiClient]:
    client = second_organizer_client(settings)
    yield client
    client.close()


@pytest.fixture(scope="session")
def integration_api_key(settings: Settings) -> str:
    # Решение: ключ берём из QA_INTEGRATION_API_KEY. Если не задан — SKIP integration-тестов.
    # Создание ключа через CLI вынесено в README — пишется вручную перед прогоном
    # (см. architecture.md §7 и app/cli/init_project.py).
    key = settings.integration_api_key_value
    if not key:
        pytest.skip(
            "QA_INTEGRATION_API_KEY не задан. Создайте ключ: "
            "python -m app.cli.init_project --source qa --name 'QA tests' "
            "--organizer admin@mirea.ru --auto-publish, потом положите его в .env."
        )
    return key


@pytest.fixture
def api_as_integration(settings: Settings, integration_api_key: str) -> Iterator[ApiClient]:
    client = make_unauthed_client(settings).with_api_key(integration_api_key)
    yield client
    client.close()
