"""Инфраструктура для integration-тестов через FastAPI TestClient.

App собирается без бот-lifespan (нет сетевых вызовов к MAX), `get_session`
подменяется на in-memory SQLite.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 — регистрация моделей в Base.metadata
from app.admin.auth import hash_password
from app.api import api_v1_router
from app.core.rate_limit import login_limiter, scan_limiter
from app.core.security_headers import SecurityHeadersMiddleware
from app.db import Base, get_session
from app.models import Organizer


@pytest.fixture
def int_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def int_session_factory(int_engine):
    return sessionmaker(
        bind=int_engine, autoflush=False, expire_on_commit=False, future=True
    )


@pytest.fixture
def int_db(int_session_factory) -> Iterator[Session]:
    s = int_session_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    login_limiter.reset()
    scan_limiter.reset()


@pytest.fixture
def app(int_session_factory) -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(SecurityHeadersMiddleware)
    test_app.include_router(api_v1_router)

    def _override_get_session() -> Iterator[Session]:
        s = int_session_factory()
        try:
            yield s
        finally:
            s.close()

    test_app.dependency_overrides[get_session] = _override_get_session
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def admin_organizer(int_db) -> Organizer:
    org = Organizer(
        email="admin@mirea.ru",
        password_hash=hash_password("adminpass1"),
        name="Главный админ",
        role="admin",
    )
    int_db.add(org)
    int_db.commit()
    return org


@pytest.fixture
def alice(int_db) -> Organizer:
    org = Organizer(
        email="alice@mirea.ru",
        password_hash=hash_password("alicepass1"),
        name="Алиса",
        department="Каф. ИТ",
        role="organizer",
    )
    int_db.add(org)
    int_db.commit()
    return org


@pytest.fixture
def bob(int_db) -> Organizer:
    org = Organizer(
        email="bob@mirea.ru",
        password_hash=hash_password("bobpass1234"),
        name="Боб",
        department="Каф. ФИ",
        role="organizer",
    )
    int_db.add(org)
    int_db.commit()
    return org


def api_login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"api login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


def login_admin(client: TestClient, email: str, password: str) -> str:
    """Алиас: HTML /admin/login удалён — логин только через REST."""
    return api_login(client, email, password)


def get_csrf(_client: TestClient) -> str:
    """Legacy stub — Jinja CSRF удалён в #183e. Только для import в skip-тестах."""
    raise RuntimeError("get_csrf: HTML admin removed, use api_login + Bearer JWT")
