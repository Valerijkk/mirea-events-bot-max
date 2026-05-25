"""Singleton-настройки фреймворка. Источник: env → .env → defaults."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Целевой SUT
    # base_url — единая точка входа (Nginx/80 в Docker, 8080 локально без Docker).
    # api_base_url — прямой бэкенд для API-тестов (обходит nginx, быстрее).
    base_url: str = "http://127.0.0.1:8080"
    api_base_url: str | None = None  # если None — используется base_url
    sut_mode: Literal["external", "spawn"] = "external"
    sut_ready_timeout: int = 30

    @property
    def effective_api_base_url(self) -> str:
        """URL для API-тестов: прямой бэкенд если задан, иначе base_url."""
        return self.api_base_url if self.api_base_url else self.base_url

    # Учётки (значения совпадают со app/cli/init_project.py — не секреты)
    admin_email: str = "admin@mirea.ru"
    admin_password: SecretStr = SecretStr("admin12345")
    organizer_email: str = "iptip@mirea.ru"
    organizer_password: SecretStr = SecretStr("organizer12345")
    # Второй организатор — только для QA cross-tenant тестов (IDOR),
    # создаётся отдельным CI-шагом в .github/workflows/qa.yml.
    second_organizer_email: str = "qa-second@mirea.ru"
    second_organizer_password: SecretStr = SecretStr("organizer12345")

    # X-API-Key для /api/v1/integration/*. Если пуст — integration-тесты SKIP.
    integration_api_key: SecretStr | None = None

    # Браузер
    browser: Literal["chromium", "firefox", "webkit"] = "chromium"
    headless: bool = True
    slow_mo_ms: int = 0
    viewport_width: int = 1366
    viewport_height: int = 768

    # Тайминги
    http_timeout_s: float = 15.0
    ui_default_timeout_ms: int = 5000

    # Артефакты
    artifacts_dir: Path = Path("./reports")
    capture_video: bool = False
    capture_trace: bool = False
    capture_har: bool = False

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # API-таймаут оставлен как алиас под имя из .env.example/architecture.
    api_timeout: float = Field(default=15.0, validation_alias="QA_API_TIMEOUT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QA_",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def admin_password_value(self) -> str:
        return self.admin_password.get_secret_value()

    @property
    def organizer_password_value(self) -> str:
        return self.organizer_password.get_secret_value()

    @property
    def second_organizer_password_value(self) -> str:
        return self.second_organizer_password.get_secret_value()

    @property
    def integration_api_key_value(self) -> str | None:
        return self.integration_api_key.get_secret_value() if self.integration_api_key else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # lru_cache гарантирует Singleton на процесс — те же гарантии, что в app/config.py.
    return Settings()
