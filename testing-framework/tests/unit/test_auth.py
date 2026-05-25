"""Тесты авторизации админки: bcrypt, JWT, authenticate, current_organizer."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.admin.auth import (
    ALGORITHM,
    AdminLoginRequired,
    authenticate,
    create_token,
    current_organizer,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import get_settings
from app.models import Organizer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_organizer(session, email: str = "test@mirea.ru", password: str = "secret12") -> Organizer:
    org = Organizer(
        email=email,
        password_hash=hash_password(password),
        name="Test",
        role="organizer",
    )
    session.add(org)
    session.commit()
    return org


# ---------------------------------------------------------------------------
# Хеширование паролей
# ---------------------------------------------------------------------------

def test_hash_password_produces_verifiable_hash():
    plain = "supersecret"

    hashed = hash_password(plain)

    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct")

    assert verify_password("wrong", hashed) is False


# ---------------------------------------------------------------------------
# JWT round-trip
# ---------------------------------------------------------------------------

def test_create_and_decode_token_roundtrip():
    organizer_id = 42

    token = create_token(organizer_id)
    decoded = decode_token(token)

    assert decoded == organizer_id


@pytest.mark.parametrize(
    "bad_token, label",
    [
        ("not-a-jwt", "garbage"),
        ("", "empty"),
        # Подписан другим секретом
        (
            jwt.encode(
                {"sub": "1", "exp": datetime.now(UTC) + timedelta(minutes=5)},
                "wrong-secret-but-also-long-enough-for-anything",
                algorithm=ALGORITHM,
            ),
            "wrong-signature",
        ),
        # Просроченный токен (подписанный правильным секретом)
        (
            jwt.encode(
                {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)},
                get_settings().jwt_secret,
                algorithm=ALGORITHM,
            ),
            "expired",
        ),
    ],
    ids=["garbage", "empty", "wrong-signature", "expired"],
)
def test_decode_token_rejects_invalid_tokens(bad_token: str, label: str):
    """decode_token возвращает None для любого «не своего» JWT."""
    assert decode_token(bad_token) is None, f"должен отклонить случай {label}"


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

def test_authenticate_succeeds_with_correct_credentials(session):
    org = _create_organizer(session, email="alice@mirea.ru", password="hunter2!")

    result = authenticate(session, email="alice@mirea.ru", password="hunter2!")

    assert result is not None
    assert result.id == org.id


@pytest.mark.parametrize(
    "email, password",
    [
        ("bob@mirea.ru", "WRONGpass1"),  # неверный пароль
        ("ghost@mirea.ru", "anything"),  # неизвестный email
    ],
    ids=["wrong-password", "unknown-email"],
)
def test_authenticate_returns_none_for_bad_credentials(session, email: str, password: str):
    """Обе негативные ветки возвращают None — защита от user-enumeration:
    по типу ошибки нельзя понять, существует ли email в системе.
    """
    _create_organizer(session, email="bob@mirea.ru", password="rightpass1")

    assert authenticate(session, email=email, password=password) is None


# ---------------------------------------------------------------------------
# current_organizer (cookie-зависимость)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "token_value, case",
    [
        (None, "no-cookie"),
        ("not-a-jwt", "invalid-token"),
        (create_token(organizer_id=99999), "unknown-organizer-id"),
    ],
    ids=["no-cookie", "invalid-token", "unknown-organizer"],
)
def test_current_organizer_raises_on_bad_auth(session, token_value: str | None, case: str):
    """AdminLoginRequired поднимается при любой проблеме с авторизацией —
    main.py конвертирует это в 303 на /admin/login. Лазейки в виде «вернуть
    None для unknown-id» быть не должно.
    """
    with pytest.raises(AdminLoginRequired):
        current_organizer(token=token_value, session=session)


def test_current_organizer_returns_user_for_valid_token(session):
    org = _create_organizer(session)
    token = create_token(org.id)

    result = current_organizer(token=token, session=session)

    assert result.id == org.id
    assert result.email == org.email
