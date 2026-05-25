"""Тесты согласия на обработку данных (ТЗ §«Пользовательский процесс»).

Версионирование: при смене `CONSENT_VERSION` старое согласие перестаёт считаться
активным — это требование аудита.
"""
from __future__ import annotations

from app.bot import texts as texts_module
from app.models import Consent, User
from app.services.consent import grant_consent, has_active_consent


def _make_user(session, user_id: int = 555) -> User:
    user = User(max_user_id=user_id, chat_id=user_id, name="Test")
    session.add(user)
    session.commit()
    return user


def test_has_active_consent_returns_false_for_new_user(session):
    _make_user(session)

    assert has_active_consent(session, user_id=555) is False


def test_grant_consent_creates_record_with_current_version(session):
    _make_user(session)

    consent = grant_consent(session, user_id=555)

    assert consent.user_id == 555
    assert consent.doc_version == texts_module.CONSENT_VERSION
    assert consent.granted_at is not None


def test_has_active_consent_returns_true_after_grant(session):
    _make_user(session)
    grant_consent(session, user_id=555)

    assert has_active_consent(session, user_id=555) is True


def test_grant_consent_is_idempotent(session):
    _make_user(session)
    first = grant_consent(session, user_id=555)

    second = grant_consent(session, user_id=555)

    # Повторный grant вернёт тот же объект — одна запись в БД на (user, version).
    assert first.id == second.id
    count = session.query(Consent).filter(Consent.user_id == 555).count()
    assert count == 1


def test_old_version_consent_does_not_count(session, monkeypatch):
    """При обновлении документа старое согласие перестаёт быть активным."""
    _make_user(session)
    session.add(Consent(user_id=555, doc_version="2020-01-01-old"))
    session.commit()

    assert has_active_consent(session, user_id=555) is False
