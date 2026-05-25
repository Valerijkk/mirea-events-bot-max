"""Разовая инициализация проекта на пустой машине.

Что делает:
  1. Создаёт таблицы (init_db).
  2. Заводит администратора `admin@mirea.ru`.
  3. Заводит организатора факультета ИПТИП `iptip@mirea.ru`.
  4. Заводит второго организатора `qa-second@mirea.ru` — нужен для
     QA cross-tenant (IDOR) тестов.
  5. Создаёт `IntegrationKey` для приёма событий от ИС вуза
     (`source=mirea_main`) и для QA-нужд (`source=qa`).

События в БД **не наполняются** — это делает либо ИС вуза в проде
(`POST /api/v1/integration/events/sync`), либо локальный test-only
парсер `scripts/fetch_mirea_events.py` для QA.

Запуск:
    python -m app.cli.init_project

Пароли — через `ADMIN_PASSWORD` / `ORG_PASSWORD` / `SECOND_ORG_PASSWORD`
env-переменные (по умолчанию демо-значения).
"""
from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime

from sqlalchemy import select

from app.admin.auth import hash_password
from app.db import session_scope
from app.db_init import init_db
from app.models import IntegrationKey, Organizer

ADMIN_EMAIL = "admin@mirea.ru"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin12345")
ADMIN_NAME = "Администратор РТУ МИРЭА"
ADMIN_DEPT = "РТУ МИРЭА"

ORG_EMAIL = "iptip@mirea.ru"
ORG_PASSWORD = os.getenv("ORG_PASSWORD", "organizer12345")
ORG_NAME = "Институт перспективных технологий и индустриального программирования"
ORG_DEPT = "ИПТИП"

# Второй организатор — нужен исключительно для воспроизводимой multi-tenant
# демонстрации и для регрессионных QA-тестов на cross-tenant 403 (его события
# существуют, к ним нельзя достучаться через токен `iptip`-организатора).
SECOND_ORG_EMAIL = "qa-second@mirea.ru"
SECOND_ORG_PASSWORD = os.getenv("SECOND_ORG_PASSWORD", "organizer12345")
SECOND_ORG_NAME = "QA Second Organizer"
SECOND_ORG_DEPT = "QA"


def _upsert_organizer(
    session, *, email: str, password: str, name: str, department: str, role: str,
) -> Organizer:
    existing = session.scalar(select(Organizer).where(Organizer.email == email))
    if existing is not None:
        print(f"[i] {role:9s} {email} — уже существует, пропускаю.")
        return existing
    organizer = Organizer(
        email=email,
        password_hash=hash_password(password),
        name=name,
        department=department,
        role=role,
    )
    session.add(organizer)
    session.flush()
    print(f"[+] {role:9s} {email} — создан (id={organizer.id}).")
    return organizer


def _upsert_integration_key(
    session, *, source: str, name: str, organizer: Organizer, auto_publish: bool,
) -> str | None:
    """Заводит/обновляет IntegrationKey, возвращает plaintext-ключ если только что создан."""
    existing = session.scalar(select(IntegrationKey).where(IntegrationKey.source == source))
    if existing is not None:
        if existing.organizer_id != organizer.id:
            existing.organizer_id = organizer.id
            print(f"[i] integration-key {source}: владелец переключен на {organizer.email}.")
        existing.active = True
        existing.auto_publish = auto_publish
        print(f"[i] integration-key {source} — уже существует, ключ не показывается повторно.")
        return None

    raw = f"{source}.{secrets.token_urlsafe(32)}"
    session.add(IntegrationKey(
        name=name,
        source=source,
        key_hash=hash_password(raw),
        organizer_id=organizer.id,
        active=True,
        auto_publish=auto_publish,
    ))
    session.flush()
    print(f"[+] integration-key {source} (organizer={organizer.email}) создан.")
    return raw


def main() -> int:
    print("=" * 60)
    print("  Инициализация mirea-events-bot")
    print("=" * 60)

    init_db()
    print("[OK] Таблицы БД готовы.")

    fresh_keys: list[tuple[str, str]] = []

    with session_scope() as session:
        admin = _upsert_organizer(
            session,
            email=ADMIN_EMAIL, password=ADMIN_PASSWORD,
            name=ADMIN_NAME, department=ADMIN_DEPT, role="admin",
        )
        _upsert_organizer(
            session,
            email=ORG_EMAIL, password=ORG_PASSWORD,
            name=ORG_NAME, department=ORG_DEPT, role="organizer",
        )
        _upsert_organizer(
            session,
            email=SECOND_ORG_EMAIL, password=SECOND_ORG_PASSWORD,
            name=SECOND_ORG_NAME, department=SECOND_ORG_DEPT, role="organizer",
        )

        # mirea_main — для прод-импорта от ИС вуза. На проде ключ выдаётся
        # вузу под подпись. Локально просто создаём, чтобы интеграционная
        # ручка была работоспособна сразу.
        mirea_key = _upsert_integration_key(
            session,
            source="mirea_main",
            name="Импорт от ИС вуза",
            organizer=admin,
            auto_publish=True,
        )
        if mirea_key:
            fresh_keys.append(("mirea_main", mirea_key))

        # qa — для локального test-only парсера scripts/fetch_mirea_events.py
        # и интеграционных QA-тестов фреймворка.
        qa_key = _upsert_integration_key(
            session,
            source="qa",
            name="QA tests + scripts/fetch_mirea_events",
            organizer=admin,
            auto_publish=True,
        )
        if qa_key:
            fresh_keys.append(("qa", qa_key))

    print()
    print("=" * 60)
    print("  Готово")
    print("=" * 60)
    print(f"  admin:        {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"  организатор:  {ORG_EMAIL} / {ORG_PASSWORD} (ИПТИП)")
    print(f"  организатор:  {SECOND_ORG_EMAIL} / {SECOND_ORG_PASSWORD} (QA cross-tenant)")
    print(f"  прогон:       {datetime.now(UTC):%Y-%m-%d %H:%M UTC}")

    if fresh_keys:
        print()
        print("  ВНИМАНИЕ — integration-ключи показаны один раз, сохраните:")
        for source, key in fresh_keys:
            print(f"    {source:12s}: {key}")
        print()
        print("  Для QA-парсера в test-окружении положите ключ в")
        print("  testing-framework/.env: QA_INTEGRATION_API_KEY=<qa-ключ>")

    print()
    print("Запустить SUT:  make dev   (или: uvicorn app.main:app --port 8080)")
    print("Наполнить БД событиями (test-only): python scripts/fetch_mirea_events.py --api-key=<qa-ключ>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
