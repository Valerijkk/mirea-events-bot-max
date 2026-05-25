"""Конфигурация приложения.

Все значения читаются из `.env` или окружения. Pydantic Settings гарантирует,
что отсутствующие обязательные поля упадут при старте, а не позже —
тяжёлой ошибкой посреди обработки запроса.
"""
from __future__ import annotations

import re
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# bot_username попадает в SPA deeplink и публичные ссылки. Жёсткий whitelist
# допустимых символов — defence in depth. Telegram/MAX и так разрешают
# только латиницу/цифры/подчёркивание/точку в username.
_BOT_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,64}$")

# Маркер «дефолтного» секрета: если пользователь его не переопределил, мы
# либо падаем (prod), либо генерируем эфемерный (dev). Хардкодить «change-me…»
# нельзя — увидев такой секрет в кодовой базе, любой может выпустить JWT.
_JWT_SECRET_PLACEHOLDER = "__GENERATE__"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # extra="ignore" — игнорируем неизвестные переменные окружения, чтобы
        # системные переменные (PATH, HOME и пр.) не ломали загрузку.
        extra="ignore",
    )

    # ----- Мессенджер МАКС -----
    bot_token: str
    bot_username: str = "mirea_events_bot"
    # Если webhook_url не задан — приложение работает в режиме long polling.
    webhook_url: str | None = None
    webhook_secret: str | None = None

    # ----- База данных -----
    database_url: str = "sqlite:///./data/mirea-events.db"

    # ----- Авторизация админки -----
    # Секрет для подписи JWT. Если не задан — сгенерируется эфемерный (после
    # рестарта все сессии умрут). На проде ОБЯЗАТЕЛЬНО задать через `.env`,
    # минимум 32 символа.
    jwt_secret: str = _JWT_SECRET_PLACEHOLDER
    jwt_expire_minutes: int = 480  # рабочий день

    @field_validator("bot_username", mode="after")
    @classmethod
    def _validate_bot_username(cls, v: str) -> str:
        if not _BOT_USERNAME_RE.match(v):
            raise ValueError(
                "BOT_USERNAME должен содержать только A-Z, a-z, 0-9, _, . "
                "(длина 3-64) — иначе риск инъекции в SPA deeplink."
            )
        return v

    @field_validator("jwt_secret", mode="after")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        if v == _JWT_SECRET_PLACEHOLDER:
            # Эфемерный секрет — токены проживут только до перезапуска.
            # На хакатоне это ок, на проде заставит явно задать переменную
            # (длинный «не угадаешь» секрет вместо безопасного «change-me»).
            return secrets.token_urlsafe(48)
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET слишком короткий: нужно минимум 32 символа. "
                "Сгенерируйте: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return v

    # ----- Прочее -----
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins",
    )
    tz: str = "Europe/Moscow"
    log_level: str = "INFO"
    qr_dir: str = "./data/qr"

    # Публичный base-url для отдачи QR-картинок в МАКС. Нужен, потому что
    # МАКС-серверы не могут скачать картинку с `127.0.0.1` — для send_photo_url
    # нужен URL, доступный из интернета. Если задан (например, ngrok / прод-домен),
    # бот будет слать `<qr_public_base_url>/qr/<token>.png` через send_photo_url
    # вместо upload (надёжнее). Если пусто — пробуем upload (работает редко из-за
    # капризов МАКС API) и при ошибке пользователь получает текстовый код.
    qr_public_base_url: str = ""

    # ----- Согласие на обработку данных (ТЗ §«Пользовательский процесс») -----
    # Версия документа согласия. При изменении формулировок в шаблоне согласия
    # бот заново попросит пользователя нажать «Я согласен». Хранится здесь, а
    # не в `app/bot/texts.py`, потому что это политика обработки данных, а
    # не «текст бота» — её прочитает и юрист, и devops.
    consent_doc_version: str = "2026-05-15"

    # ----- Производные значения -----

    @property
    def qr_path(self) -> Path:
        """Гарантированно существующая папка для QR. Создаётся при первом обращении."""
        path = Path(self.qr_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_webhook_mode(self) -> bool:
        """True — приложение должно слушать webhook; False — long polling."""
        return bool(self.webhook_url)


@lru_cache
def get_settings() -> Settings:
    """Кешированный синглтон настроек. Загружается один раз за процесс."""
    return Settings()
