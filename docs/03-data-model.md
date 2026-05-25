# 3. Модель данных

ORM-модели — в `backend/app/models.py`. Схема намеренно простая: десять
таблиц (`users`, `organizers`, `events`, `event_slots`, `registrations`,
`broadcasts`, `reminders`, `consents`, `integration_keys`, `audit_log`),
никаких EAV и полиморфных ассоциаций. Все enum хранятся строками — это
делает auto-migration через `ALTER ADD COLUMN` и ручные правки в проде
безболезненными.

## Диаграмма связей

```
   ┌──────────────┐                                ┌─────────────────┐
   │  Organizer   │   1                       1    │      User       │
   │              │  ─────┐               ┌─────   │  (max_user_id)  │
   │  id (PK)     │       │               │        │                 │
   │  email       │       │ N           N │        │  chat_id, phone │
   │  password    │     ┌─▼───────────────▼──┐     │  notifications  │
   └──────────────┘     │       Event        │     └────────┬────────┘
                        │  id (PK)           │              │ N
                        │  status, capacity  │     ┌────────▼─────────┐
                        │  starts_at, ...    │  1  │  Registration    │
                        │  deeplink_payload  │ ◄───┤  status, qr_token│
                        └─────────┬──────────┘     │  waitlist_position│
                                  │ N              └────────┬─────────┘
                       ┌──────────▼─────────┐               │ 1
                       │     Broadcast      │      ┌────────▼─────────┐
                       │  segment, message  │      │     Reminder     │
                       │  delivered_count   │      │  remind_at, kind │
                       └────────────────────┘      │  sent            │
                                                   └──────────────────┘
```

## Таблицы

### `users` — абитуриенты / студенты

| Поле                    | Тип        | Назначение                                                    |
|-------------------------|------------|---------------------------------------------------------------|
| `max_user_id` (PK)      | BIGINT     | Идентификатор пользователя в МАКС.                            |
| `chat_id`               | BIGINT     | Чат с ботом — куда отправлять напоминания и waitlist.         |
| `name`                  | VARCHAR    | ФИО пользователя (запрашивается ботом после согласия, ФЗ-152). |
| `pending_deeplink_payload` | VARCHAR | Deeplink с афиши, если consent ещё не дан — применяется после ФИО. |
| `username`              | VARCHAR    | Username из профиля МАКС, если задан.                         |
| `phone`                 | VARCHAR    | Телефон (если пользователь поделился контактом).              |
| `notifications_enabled` | BOOL       | Уважаем эту галку: при `false` бот не пишет.                  |
| `first_seen`            | DATETIME   | Дата первого контакта с ботом.                                |
| `last_active`           | DATETIME   | Бамается при каждом обращении пользователя.                   |

### `organizers` — сотрудники РТУ МИРЭА (приёмная комиссия / факультеты / кафедры)

| Поле              | Тип        | Назначение                                                  |
|-------------------|------------|-------------------------------------------------------------|
| `id` (PK)         | INT        | Внутренний автоинкремент.                                   |
| `email`           | VARCHAR    | Логин в админке. Уникальный, индексированный.               |
| `password_hash`   | VARCHAR    | Bcrypt-хеш пароля (никогда не плейн).                       |
| `name`            | VARCHAR    | Имя для отображения.                                        |
| `department`      | VARCHAR    | Отдел / факультет.                                          |
| `role`            | VARCHAR    | `admin` — Stats/Audit/Organizers; `organizer` — только свои events. |
| `created_at`      | DATETIME   | —                                                           |

### `events` — мероприятия

| Поле                | Тип       | Назначение                                                      |
|---------------------|-----------|-----------------------------------------------------------------|
| `id` (PK)           | INT       | —                                                               |
| `title`             | VARCHAR   | Название.                                                       |
| `description`       | TEXT      | Полное описание (поддерживает обычный текст и базовый markdown).|
| `event_type`        | VARCHAR   | `open_day` / `masterclass` / `olympiad` / `tour` / `consultation` / `other`. |
| `starts_at`         | DATETIME  | Индексировано: бот фильтрует «ещё не прошедшие» по этой колонке.|
| `ends_at`           | DATETIME  | Опционально; для .ics берётся `+2 часа` от начала, если NULL.   |
| `location`          | VARCHAR   | Аудитория / адрес.                                              |
| `capacity`          | INT       | Лимит подтверждённых записей.                                   |
| `organizer_id`      | FK        | Кто создал.                                                     |
| `status`            | VARCHAR   | `draft` / `published` / `cancelled` / `finished`, индексировано.|
| `deeplink_payload`  | VARCHAR   | UUID-ный slug, который кладётся в QR и deeplink ссылку.         |
| `created_at` / `updated_at` | DATETIME | Технические таймстампы.                                  |

### `registrations` — записи пользователей

| Поле                  | Тип       | Назначение                                                    |
|-----------------------|-----------|---------------------------------------------------------------|
| `id` (PK)             | INT       | —                                                             |
| `event_id`            | FK        | На какое мероприятие. CASCADE при удалении мероприятия.       |
| `user_id`             | FK BIGINT | Кто записан.                                                  |
| `slot_id`             | FK NULL   | Если у Event есть слоты — на какой именно записан. NULL иначе.|
| `status`              | VARCHAR   | `confirmed` / `waitlist` / `cancelled` / `attended` / `no_show` / `late_cancelled`. |
| `qr_token`            | VARCHAR   | UUID-токен, который запекается в QR. Уникален.                |
| `code`                | VARCHAR   | Человекочитаемый код `RG-XXXXXX` (без 0/O/1/I).              |
| `waitlist_position`   | INT       | Позиция в очереди (1-индексирована). NULL для confirmed.      |
| `registered_at`       | DATETIME  | Время создания записи.                                        |
| `cancelled_at`        | DATETIME  | Время отмены (если статус cancelled).                         |
| `attended_at`         | DATETIME  | Время сканирования QR на входе.                               |
| `notifications_enabled` | BOOLEAN, default True | Включены ли уведомления по этой конкретной записи. False — пользователь нажал «🔕 Тише по этому». Фильтруется при broadcast и при отправке scan-сообщения. |

**Уникальный констрейнт:** `(event_id, user_id)` — один пользователь не
может иметь две активные записи на одно мероприятие. При повторной записи
после отмены строка переиспользуется с новым `qr_token`.

### `broadcasts` — рассылки организатора

| Поле                | Тип      | Назначение                                                  |
|---------------------|----------|-------------------------------------------------------------|
| `id` (PK)           | INT      | —                                                           |
| `event_id`          | FK       | По какому мероприятию.                                      |
| `organizer_id`      | FK       | Кто отправил.                                               |
| `segment`           | VARCHAR  | `all` / `confirmed` / `waitlist` / `attended` / `no_show`.  |
| `message_text`      | TEXT     | Что отправили.                                              |
| `scheduled_at`      | DATETIME | Задел под отложенные рассылки (пока не используется).       |
| `sent_at`           | DATETIME | Когда фактически отправилось.                               |
| `delivered_count`   | INT      | Сколько ушло успешно.                                       |
| `failed_count`      | INT      | Сколько не доставлено (бот заблокирован и т.п.).            |
| `created_at`        | DATETIME | —                                                           |

### `event_slots` — временные окна мероприятия

| Поле          | Тип       | Назначение                                                          |
|---------------|-----------|---------------------------------------------------------------------|
| `id` (PK)     | INT       | —                                                                   |
| `event_id`    | FK        | На какое мероприятие. CASCADE.                                      |
| `starts_at`   | DATETIME  | Начало слота.                                                       |
| `ends_at`     | DATETIME  | Конец (опционально).                                                |
| `capacity`    | INT       | Своя ёмкость у каждого слота.                                       |
| `label`       | VARCHAR   | Опциональный ярлык («Группа А», «11:00 — корпус А»).                |

Если у Event есть слоты — пользователь записывается на конкретный слот
(в `Registration.slot_id`), и `Event.capacity` игнорируется в пользу
`EventSlot.capacity`. Если слотов нет — `slot_id` у регистрации NULL,
капасити берётся с самого Event.

### `reminders` — отложенные напоминания

| Поле               | Тип      | Назначение                                                |
|--------------------|----------|-----------------------------------------------------------|
| `id` (PK)          | INT      | —                                                         |
| `registration_id`  | FK       | На какую запись напомнить. CASCADE.                       |
| `remind_at`        | DATETIME | Когда напомнить. Индексировано.                           |
| `kind`             | VARCHAR  | `day_before` / `hour_before` / `custom`.                  |
| `sent`             | BOOL     | True — уже отправлено, повторно не уйдёт. Индексировано.  |
| `sent_at`          | DATETIME | Когда отправилось.                                        |

### `consents` — версионированное согласие на обработку данных

| Поле               | Тип      | Назначение                                                |
|--------------------|----------|-----------------------------------------------------------|
| `id` (PK)          | INT      | —                                                         |
| `user_id`          | FK BIGINT| Чей consent.                                              |
| `version`          | VARCHAR  | Версия документа на момент согласия (`CONSENT_VERSION`).  |
| `granted_at`       | DATETIME | Когда нажал «Я согласен».                                 |
| `revoked_at`       | DATETIME | Когда отозвал (NULL если активен).                        |

Если меняется `CONSENT_VERSION` в `app/config.py` — старые consent'ы
становятся неактивными, бот заново попросит согласиться с новой
редакцией.

### `integration_keys` — API-ключи внешних систем

| Поле                | Тип      | Назначение                                                  |
|---------------------|----------|-------------------------------------------------------------|
| `id` (PK)           | INT      | —                                                           |
| `name`              | VARCHAR  | Человеко-читаемое имя ключа (для аудита).                   |
| `source`            | VARCHAR  | Источник: `mirea_main`, `mirea_priem`, `1c_iss`, `qa`, ...  |
| `key_hash`          | VARCHAR  | bcrypt-хеш ключа. Plaintext выдаётся **один раз** на создании.|
| `organizer_id`      | FK       | Кому принадлежат события, пришедшие через этот ключ.        |
| `active`            | BOOL     | False — ключ отозван, запросы отклоняются.                  |
| `auto_publish`      | BOOL     | True — новые события сразу `published`, иначе `draft`.      |
| `created_at`        | DATETIME | —                                                           |

Используется ручкой `POST /api/v1/integration/events/sync` для bulk-импорта
событий из внешних систем; multi-tenant сохраняется — events принадлежат
организатору-владельцу ключа.

### `audit_log` — журнал действий (только просмотр admin)

| Поле                | Тип      | Назначение                                                  |
|---------------------|----------|-------------------------------------------------------------|
| `id` (PK)           | INT      | —                                                           |
| `created_at`        | DATETIME | Когда произошло действие.                                   |
| `actor_type`        | VARCHAR  | `organizer` / `user` / `system`.                            |
| `organizer_id`      | INT NULL | Кто из админки (если применимо).                            |
| `user_id`           | BIGINT NULL | Кто из бота (если применимо).                            |
| `actor_display`     | VARCHAR  | Короткое имя для UI (email или display_name, без лишних ПДн). |
| `event_type`        | VARCHAR  | Тип события (`event.created`, `registration.attended`, …).  |
| `entity_type`       | VARCHAR  | `event` / `registration` / `organizer` / …                  |
| `entity_id`         | INT NULL | ID сущности.                                                |
| `payload`           | JSON     | Контекст действия (без email/phone — см. `services/audit.py`). |
| `ip_address`        | VARCHAR  | IP REST-запроса (если есть).                                |
| `user_agent`        | VARCHAR  | User-Agent (если есть).                                     |

REST: `GET /api/v1/audit-logs` (admin-only). SPA: страница `/audit`.

## Инварианты

* **Уникальная пара `(event_id, user_id)`**. Поддерживается БД.
* **`confirmed_count <= capacity`**. Поддерживается логикой `sign_up`.
* **Сумма позиций в waitlist — арифметическая прогрессия 1..N**, без дыр.
  При отмене из waitlist `_shift_waitlist_positions` сдвигает остальные.
* **`qr_token` уникальный.** Поддерживается БД. Это гарантирует, что
  невозможно «прийти на чужой пропуск».
* **`attended` — только из `confirmed`.** Контролируется `mark_attended`.
