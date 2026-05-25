"""Снимок состояния SUT через API + восстановление через cleanup-ID.

Тестовый фреймворк не лазит в БД напрямую (это нарушает black-box).
Снимок — это набор id'ов созданных в тесте сущностей, чтобы teardown
их снёс через REST API. Используется фикстурой `clean_state` ниже.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.api_client import ApiClient

logger = logging.getLogger("qa.snapshot")


@dataclass
class StateLedger:
    """Реестр созданных в тесте сущностей. Cleanup идёт в обратном порядке."""

    event_ids: list[int] = field(default_factory=list)
    organizer_ids: list[int] = field(default_factory=list)
    integration_key_ids: list[int] = field(default_factory=list)

    def track_event(self, event_id: int) -> int:
        self.event_ids.append(event_id)
        return event_id

    def track_organizer(self, organizer_id: int) -> int:
        self.organizer_ids.append(organizer_id)
        return organizer_id

    def track_integration_key(self, key_id: int) -> int:
        self.integration_key_ids.append(key_id)
        return key_id

    def cleanup(self, admin: ApiClient) -> None:
        """Best-effort удаление в обратном порядке создания.

        Удаляем как admin, потому что только admin может удалять чужие
        ресурсы (организатор может только свои). Ошибки 404/403 глотаем —
        тест мог сам удалить, или другая фикстура успела раньше.
        """
        for event_id in reversed(self.event_ids):
            self._delete(admin, f"/api/v1/events/{event_id}")
        for key_id in reversed(self.integration_key_ids):
            self._delete(admin, f"/admin/integration-keys/{key_id}")
        # Организаторов админ-API не удаляет (только деактивирует), оставляем.

    @staticmethod
    def _delete(admin: ApiClient, path: str) -> None:
        try:
            resp = admin.delete(path)
            if resp.status_code not in (200, 204, 404, 403):
                logger.warning("cleanup %s -> %s", path, resp.status_code)
        except Exception as exc:
            logger.info("cleanup %s ignored: %s", path, exc)
