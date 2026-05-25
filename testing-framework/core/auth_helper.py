"""Хелперы для логина: дают готовый ApiClient под нужной ролью."""
from __future__ import annotations

from config.credentials import ADMIN, ORGANIZER_IPTIP, ORGANIZER_QA_SECOND, Credential
from config.settings import Settings
from core.api_client import ApiClient


def make_unauthed_client(settings: Settings) -> ApiClient:
    return ApiClient(base_url=settings.effective_api_base_url, timeout=settings.http_timeout_s)


def login_as(settings: Settings, credential: Credential) -> ApiClient:
    client = make_unauthed_client(settings)
    client.authenticate(credential.email, credential.password)
    return client


def admin_client(settings: Settings) -> ApiClient:
    # Учитываем .env: если QA_ADMIN_* перекрыли — берём из Settings, иначе из ADMIN.
    cred = Credential(
        email=settings.admin_email,
        password=settings.admin_password_value,
        role="admin",
        label=ADMIN.label,
    )
    return login_as(settings, cred)


def organizer_client(settings: Settings) -> ApiClient:
    cred = Credential(
        email=settings.organizer_email,
        password=settings.organizer_password_value,
        role="organizer",
        label=ORGANIZER_IPTIP.label,
    )
    return login_as(settings, cred)


def second_organizer_client(settings: Settings) -> ApiClient:
    cred = Credential(
        email=settings.second_organizer_email,
        password=settings.second_organizer_password_value,
        role="organizer",
        label=ORGANIZER_QA_SECOND.label,
    )
    return login_as(settings, cred)
