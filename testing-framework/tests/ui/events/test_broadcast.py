"""Рассылка — UI форма удалена в React SPA (#183e)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Форма broadcast на карточке события удалена с Jinja — покрыто API-тестами",
)
