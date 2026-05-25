# Безопасность

## Поддерживаемые версии

Проект разработан в рамках хакатона. Поддерживается только текущая ветка `main`.

## Куда сообщать об уязвимости

Если вы нашли уязвимость, **не открывайте публичный issue** — это раскроет её до выхода
фикса. Вместо этого:

1. Напишите на email мейнтейнера (в `pyproject.toml` → `[project.contact]`).
2. Опишите: вектор атаки, минимальный PoC, потенциальный импакт.
3. Ответ — в течение 7 дней. Фикс — в течение 30 дней при подтверждении.

Без раскрытия публично до выхода патча. После релиза — благодарность в release notes.

## Что считается уязвимостью

* Обход авторизации (JWT Bearer, X-API-Key).
* IDOR — доступ организатора к чужим мероприятиям или записям.
* SQL injection, XSS, CSRF (несмотря на double-submit), open redirect.
* Утечка PII (телефон, email, ФИО абитуриентов).
* Брут-форс паролей или QR-токенов без срабатывания rate-limit.
* Возможность массовой рассылки от чужого имени.

## Что НЕ считается

* DoS через исчерпание соединений к Postgres без наличия CVE в самой БД.
* Доступ к AdminPanel с легитимными учётными данными (это by design).
* Отсутствие 2FA — не в scope хакатонного кейса.

## Меры в коде

* JWT Bearer-токены для REST API; срок жизни настраивается через `JWT_EXPIRE_MINUTES`.
* `assert_event_owned` / `OwnedEvent` dep на каждом роуте с `event_id` (IDOR-защита).
* `GET /events` фильтрует по `organizer_id` для роли `organizer` — список не утекает.
* Bcrypt cost=12 для паролей; constant-time сравнение через passlib.
* Rate-limit: 5/мин на `/auth/login`, 60/мин на `/scan` (по IP/organizer).
* Security headers: X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy, Permissions-Policy.
* XSS-защита: React SPA — типизированный API-клиент без innerHTML, без dangerouslySetInnerHTML.
* CSV-injection защита в экспортах (ячейки с `= + - @ \t \r` префиксируются `'`).
* `X-API-Key` для интеграционной ручки — bcrypt-хеш + source-prefix lookup, generic 401 (Oracle mitigation).
* ФИО пользователей хранится только после явного согласия (ФЗ-152); прочие PII не собираются.

## Проверки

```bash
python -m bandit -r app/
python -m pip_audit -r requirements.txt
cd testing-framework && pytest tests/unit/test_security.py tests/unit/test_regressions_final.py
```
