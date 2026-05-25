"""CSV/постер — admin HTML-эндпоинты удалены в #183e."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="/admin/events/{id}/export.csv и /poster удалены — ждём REST-аналог в API",
)
