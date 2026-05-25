"""Авторизация организаторов через REST. JSON-вариант `/admin/login`; токен совместим с Bearer-схемой всех остальных ручек."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.admin.auth import authenticate, create_token
from app.api.deps import DbSession
from app.config import get_settings
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    summary="Получить JWT-токен организатора",
    description=(
        "Принимает email и пароль организатора, возвращает JWT-токен. "
        "Используйте токен в заголовке `Authorization: Bearer <token>` "
        "для всех остальных ручек API."
    ),
    response_model=TokenResponse,
    responses={401: {"description": "Неверный email или пароль", "model": ErrorResponse}},
)
def login(payload: LoginRequest, session: DbSession) -> TokenResponse:
    organizer = authenticate(session, email=payload.email, password=payload.password)
    if organizer is None:
        # Единая формулировка для unknown email и wrong password — защита от user enumeration.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    settings = get_settings()
    token = create_token(organizer.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )
