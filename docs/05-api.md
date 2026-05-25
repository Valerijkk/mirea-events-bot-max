# 5. REST API

Все ручки доступны под префиксом **`/api/v1`**. Интерактивная документация
— на `/docs` (Swagger UI) и `/redoc`.

Порты в dev:
* backend напрямую — `:8000`;
* через nginx (docker-compose) — `:80`, API проксируется на backend;
* CI и testing-framework по умолчанию — SUT на `:8080`.

## Авторизация

Все ручки, кроме `/healthz`, `/readyz` и `/auth/login`, требуют JWT:

```
Authorization: Bearer <ваш_токен>
```

Токен — `POST /api/v1/auth/login`. TTL по умолчанию 8 часов
(`JWT_EXPIRE_MINUTES` в `.env`).

### Роли

| Роль | JWT claim | Ограничения |
|------|-----------|-------------|
| `organizer` | `role=organizer` | Видит и меняет **только свои** events (`organizer_id` в токене). `GET /events/{id}` чужого → **403**. |
| `admin` | `role=admin` | Полный доступ ко всем events + `/stats`, `/audit-logs`, `/organizers`. |

IDOR-защита — `assert_event_owned` / dependency `OwnedEvent`. Admin обходит.

## Таблица ручек

| Метод   | Путь                                                | Тег             | Доступ        | Что делает                                       |
|---------|-----------------------------------------------------|-----------------|---------------|--------------------------------------------------|
| GET     | `/api/v1/healthz`                                   | health          | публичный     | Liveness (без БД).                               |
| GET     | `/api/v1/readyz`                                    | health          | публичный     | Readiness (пинг БД).                             |
| POST    | `/api/v1/auth/login`                                | auth            | публичный     | Выдать JWT по email/паролю.                      |
| GET     | `/api/v1/events`                                    | events          | JWT           | Список с фильтрами (organizer — только свои).    |
| POST    | `/api/v1/events`                                    | events          | JWT           | Создать (`draft`).                               |
| GET     | `/api/v1/events/{id}`                               | events          | JWT + owner   | Карточка мероприятия.                            |
| PATCH   | `/api/v1/events/{id}`                               | events          | JWT + owner   | Частичное обновление.                            |
| POST    | `/api/v1/events/{id}/status`                        | events          | JWT + owner   | publish / cancel / finish.                       |
| DELETE  | `/api/v1/events/{id}`                               | events          | JWT + owner   | Жёсткое удаление.                                |
| GET     | `/api/v1/events/{id}/slots`                         | slots           | JWT + owner   | Список слотов.                                   |
| POST    | `/api/v1/events/{id}/slots`                         | slots           | JWT + owner   | Добавить слот.                                   |
| DELETE  | `/api/v1/events/{id}/slots/{slot_id}`               | slots           | JWT + owner   | Удалить слот.                                    |
| GET     | `/api/v1/events/{id}/registrations`                 | registrations   | JWT + owner   | Записи на мероприятие.                           |
| POST    | `/api/v1/events/{id}/registrations/{reg_id}/cancel` | registrations   | JWT + owner   | Отмена организатором.                            |
| POST    | `/api/v1/events/{id}/broadcasts`                    | broadcasts      | JWT + owner   | Рассылка участникам.                             |
| GET     | `/api/v1/events/{id}/broadcasts`                    | broadcasts      | JWT + owner   | История рассылок.                                |
| POST    | `/api/v1/scan`                                      | scan            | JWT + owner   | Отметить посещение по QR.                        |
| GET     | `/api/v1/stats`                                     | stats           | **admin**     | Глобальная статистика.                           |
| GET     | `/api/v1/stats/registrations-by-day`                | stats           | **admin**     | Регистрации по дням (график Stats).              |
| GET     | `/api/v1/events/{id}/stats`                         | stats           | JWT + owner   | Воронка по мероприятию.                          |
| GET     | `/api/v1/audit-logs`                                | audit           | **admin**     | Журнал с фильтрами и пагинацией.                 |
| GET     | `/api/v1/organizers`                                | organizers      | **admin**     | Список организаторов.                            |
| POST    | `/api/v1/organizers`                                | organizers      | **admin**     | Создать учётку.                                  |
| PATCH   | `/api/v1/organizers/{id}`                           | organizers      | **admin**     | Обновить (роль, пароль, …).                      |
| DELETE  | `/api/v1/organizers/{id}`                           | organizers      | **admin**     | Удалить.                                         |
| POST    | `/api/v1/integration/events/sync`                   | integration     | X-API-Key     | Bulk-импорт событий.                             |
| GET     | `/api/v1/integration/health`                        | integration     | X-API-Key     | Пинг ключа.                                      |

## Интеграция с ИС вуза

`POST /api/v1/integration/events/sync` — system-to-system, заголовок
`X-API-Key`. Идемпотентно по `(source, external_id)`.

Для QA: `scripts/fetch_mirea_events.py` парсит `mirea.ru/eventspage/` и
шлёт в SUT этой же ручкой.

## Примеры

### Авторизация

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"organizer@mirea.ru","password":"********"}'
```

Ответ:

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 28800
}
```

### Создание мероприятия

```bash
TOKEN="eyJ0..."
curl -X POST http://localhost:8000/api/v1/events \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Мастер-класс «Введение в нейросети»",
       "description": "Двухчасовой практический воркшоп.",
       "event_type": "masterclass",
       "starts_at": "2026-05-20T14:00:00",
       "location": "ауд. 405, корп. Б",
       "capacity": 20
     }'
```

### Публикация

```bash
curl -X POST http://localhost:8000/api/v1/events/1/status \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"status":"published"}'
```

### Сканирование QR

```bash
curl -X POST http://localhost:8000/api/v1/scan \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"qr_token":"8f4a1c9d2e3b4f5a6c7d8e9f0a1b2c3d"}'
```

### Audit-log (admin)

```bash
curl "http://localhost:8000/api/v1/audit-logs?page=1&event_type=event.created" \
     -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Коды ошибок

| Код | Когда                                                                         |
|-----|-------------------------------------------------------------------------------|
| 200 | Успех.                                                                        |
| 201 | Создан ресурс.                                                                |
| 401 | Нет токена / токен не валиден / истёк.                                        |
| 403 | Нет прав (чужой event, не admin на `/stats`, …).                              |
| 404 | Ресурс не найден.                                                             |
| 422 | Невалидный ввод (Pydantic).                                                   |
| 503 | `/readyz` — БД недоступна.                                                    |

## Версионирование

Контракт `/api/v1/*` фиксируется. Несовместимые изменения — под `/api/v2/`.
