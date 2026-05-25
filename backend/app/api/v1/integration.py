"""Интеграционная ручка: внешние системы вуза кидают сюда события.

Авторизация — `X-API-Key` (не JWT). Это намеренное архитектурное решение:

* JWT привязан к человеку, у него короткая жизнь (минуты), он лежит
  в cookie или Bearer'е. Это правильно для интерактивных пользователей.
* API-Key привязан к системе, живёт месяцами, передаётся в headers
  при machine-to-machine. Это правильно для интеграций.

Поэтому отдельный заголовок и отдельный механизм. Ключи хранятся в БД
как bcrypt-хеши (так же, как пароли организаторов), plaintext выдаётся
один раз при создании через CLI и больше не показывается.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.auth import verify_password
from app.api.deps import DbSession
from app.models import IntegrationKey, Organizer
from app.schemas.common import ErrorResponse
from app.schemas.integration import EventSyncRequest, EventSyncResponse
from app.services.integration import sync_events_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integration", tags=["integration"])


def _resolve_integration_key(
    session: Session, raw_key: str | None,
) -> tuple[IntegrationKey, Organizer]:
    """Найти ключ в БД по plaintext-значению.

    Формат ключа: `<source>.<random>` (например, `mirea_priem.abc123...`).
    Source в префиксе — чтобы при логине не делать full-scan по всем
    хешам всех ключей системы (хеш проверяется только для одного-двух
    ключей одной системы-источника).

    Все ошибки даём с одним и тем же сообщением — не выдаём, существует
    ли вообще такой источник (Oracle-mitigation, как в /scan).
    """
    generic_401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API-ключ невалиден или отозван",
        headers={"WWW-Authenticate": "ApiKey"},
    )

    if not raw_key or "." not in raw_key:
        raise generic_401

    source, _, _ = raw_key.partition(".")
    candidates = list(session.scalars(
        select(IntegrationKey).where(
            IntegrationKey.source == source,
            IntegrationKey.active.is_(True),
        )
    ))
    for candidate in candidates:
        if verify_password(raw_key, candidate.key_hash):
            organizer = session.get(Organizer, candidate.organizer_id)
            if organizer is None:
                # Организатор удалён — ключ автоматически становится неживым.
                raise generic_401
            return candidate, organizer

    raise generic_401


@router.post(
    "/events/sync",
    response_model=EventSyncResponse,
    summary="Bulk-импорт событий из внешней системы вуза",
    description=(
        "Принимает batch событий из ИС вуза (priem.mirea.ru, 1С, и т.д.) "
        "и идемпотентно сохраняет их во внутренней БД.\n\n"
        "**Идемпотентность**: пара `(source, external_id)` уникальна. "
        "Повторный POST того же события — `updated`, не `created`.\n\n"
        "**Авторизация**: заголовок `X-API-Key: <ключ>` (получить через CLI "
        "`python -m app.cli.init_project`).\n\n"
        "**Статусы по умолчанию**: новые события приходят как `draft`. "
        "Чтобы публиковать сразу — передайте `auto_publish=true` в теле "
        "или попросите при создании ключа `--auto-publish`.\n\n"
        "**Multi-tenant**: события привязываются к организатору-владельцу "
        "ключа. Несколько систем-источников = несколько ключей с разными "
        "владельцами.\n\n"
        "**Лимит**: до 500 событий за запрос. Для больших каталогов "
        "разбивайте на batch'и (например, по 100 за раз)."
    ),
    responses={
        401: {"description": "Отсутствует или невалиден X-API-Key", "model": ErrorResponse},
        422: {"description": "Невалидная схема payload", "model": ErrorResponse},
    },
)
def sync_events(
    payload: EventSyncRequest,
    session: DbSession,
    x_api_key: Annotated[
        str | None,
        Header(alias="X-API-Key", description="Plaintext API-ключ системы-источника"),
    ] = None,
) -> EventSyncResponse:
    integration_key, organizer = _resolve_integration_key(session, x_api_key)
    response = sync_events_batch(
        session,
        integration_key=integration_key,
        organizer=organizer,
        request=payload,
    )
    session.commit()
    logger.info(
        "integration sync: source=%s organizer=%s received=%d created=%d updated=%d failed=%d",
        integration_key.source, organizer.email, response.received,
        response.summary.created, response.summary.updated, response.summary.failed,
    )
    return response


@router.get(
    "/health",
    summary="Health-чек интеграционной ручки",
    description=(
        "Простой пинг с проверкой API-ключа. Удобно для мониторинга "
        "внешней системы: периодически дёргает /integration/health и "
        "следит, что ключ ещё валиден."
    ),
    responses={
        401: {"description": "Невалиден X-API-Key", "model": ErrorResponse},
    },
)
def integration_health(
    session: DbSession,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> dict[str, str | int | None]:
    integration_key, organizer = _resolve_integration_key(session, x_api_key)
    return {
        "status": "ok",
        "source": integration_key.source,
        "organizer": organizer.email,
        "auto_publish": integration_key.auto_publish,
        "total_synced": integration_key.total_synced,
        "last_used_at": (
            integration_key.last_used_at.isoformat()
            if integration_key.last_used_at else None
        ),
    }
