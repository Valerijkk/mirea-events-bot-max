"""Pydantic-схемы REST API. Отделены от ORM, чтобы менять схему БД без слома контракта и не отдавать «всё, что есть»."""

from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.broadcast import BroadcastRead, BroadcastRequest, BroadcastResult
from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.event import (
    EventCreate,
    EventRead,
    EventStatusUpdate,
    EventUpdate,
)
from app.schemas.registration import RegistrationRead, UserRead
from app.schemas.scan import ScanRequest, ScanResponse
from app.schemas.stats import EventStats, GlobalStats

__all__ = [
    "BroadcastRead",
    "BroadcastRequest",
    "BroadcastResult",
    "ErrorResponse",
    "EventCreate",
    "EventRead",
    "EventStats",
    "EventStatusUpdate",
    "EventUpdate",
    "GlobalStats",
    "LoginRequest",
    "MessageResponse",
    "RegistrationRead",
    "ScanRequest",
    "ScanResponse",
    "TokenResponse",
    "UserRead",
]
