"""Seed-учётки. Не секреты — демо-данные для локального запуска и CI.

После рефакторинга bootstrap'а (`app/cli/init_project.py`) в БД есть
только два аккаунта: админ РТУ МИРЭА + один организатор факультета ИПТИП.
Дополнительный «второй организатор» нужен только QA-фреймворку для проверки
изоляции данных между организаторами (IDOR/cross-tenant) — он создаётся
отдельным CI-шагом.

Учётки — `pydantic.BaseModel(frozen=True)`:
  * `EmailStr` валидирует email на месте — опечатка в seed-данных падает
    при импорте модуля, а не на странице /admin/login через час.
  * `Literal["admin","organizer"]` валидируется pydantic'ом — нельзя
    создать `Credential(role="adminn")` и узнать об этом только в тесте.
  * `frozen=True` — учётки иммутабельны: случайная мутация в одном тесте
    не должна аффектить другие.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

Role = Literal["admin", "organizer"]


class Credential(BaseModel):
    model_config = ConfigDict(frozen=True)

    email: EmailStr
    password: str
    role: Role
    label: str


ADMIN = Credential(
    email="admin@mirea.ru",
    password="admin12345",
    role="admin",
    label="admin",
)

ORGANIZER_IPTIP = Credential(
    email="iptip@mirea.ru",
    password="organizer12345",
    role="organizer",
    label="iptip",
)

# Второй организатор существует только для cross-tenant-тестов (IDOR).
# Создаётся отдельным шагом CI (см. .github/workflows/qa.yml).
ORGANIZER_QA_SECOND = Credential(
    email="qa-second@mirea.ru",
    password="organizer12345",
    role="organizer",
    label="qa-second",
)

ORGANIZERS: tuple[Credential, ...] = (ORGANIZER_IPTIP, ORGANIZER_QA_SECOND)
ALL_CREDENTIALS: tuple[Credential, ...] = (ADMIN, *ORGANIZERS)


def by_role(role: Role) -> Credential:
    if role == "admin":
        return ADMIN
    return ORGANIZER_IPTIP
