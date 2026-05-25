"""Сервис согласий на обработку данных.

Что хранится: (user_id, doc_version, granted_at). Версия документа задана
константой `CONSENT_VERSION` в `app/bot/texts.py`. Если редакция документа
меняется, бот должен снова показать пользователю экран согласия — это
обеспечивает функция `has_active_consent`.

Минимизация PII (ТЗ §3): храним только версию и timestamp; никаких IP,
никаких free-form полей. Этого достаточно для аудита.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Consent


def has_active_consent(session: Session, user_id: int) -> bool:
    """True, если пользователь принял текущую (актуальную) редакцию документа.

    Старые согласия (с другим doc_version) к актуальным не приравниваются —
    в этом и смысл версионирования.
    """
    current_version = get_settings().consent_doc_version
    return session.scalar(
        select(Consent.id).where(
            Consent.user_id == user_id,
            Consent.doc_version == current_version,
        )
    ) is not None


def grant_consent(session: Session, user_id: int) -> Consent:
    """Зафиксировать согласие пользователя с актуальной версией документа.

    Идемпотентно: повторный вызов вернёт уже существующую запись (защита
    стоит на уникальном `(user_id, doc_version)`).
    """
    current_version = get_settings().consent_doc_version
    existing = session.scalar(
        select(Consent).where(
            Consent.user_id == user_id,
            Consent.doc_version == current_version,
        )
    )
    if existing is not None:
        return existing
    consent = Consent(user_id=user_id, doc_version=current_version)
    session.add(consent)
    session.flush()
    return consent
