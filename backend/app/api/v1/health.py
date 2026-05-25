"""Liveness/readiness. БД проверяется только в /readyz — короткий сбой Postgres не должен убивать liveness."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.schemas.common import MessageResponse

router = APIRouter(tags=["health"])


@router.get(
    "/healthz",
    summary="Liveness-проверка",
    description="Возвращает `ok: true` если процесс жив. Не обращается к БД.",
    response_model=MessageResponse,
)
async def liveness() -> MessageResponse:
    return MessageResponse(ok=True, message="alive")


@router.get(
    "/readyz",
    summary="Readiness-проверка",
    description="Проверяет, что приложение готово обслуживать запросы (в т.ч. БД доступна).",
    response_model=MessageResponse,
    responses={503: {"description": "Подсистема недоступна (например, БД).", "model": MessageResponse}},
)
async def readiness(session: DbSession) -> MessageResponse:
    session.execute(text("SELECT 1"))
    return MessageResponse(ok=True, message="ready")
