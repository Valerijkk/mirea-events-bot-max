# Gap-анализ: ТЗ обещанное vs реализованное

Источник: `docs/case2-max.pdf`. Дата актуализации: 26.05.2026.

| # | Требование из ТЗ | Статус | Где реализовано |
|---|---|---|---|
| 1 | Дисклеймер «хакатон, не оф. функция» при первом запуске бота | ✅ | `backend/app/bot/handlers.py::on_bot_started` — отдельное сообщение DISCLAIMER |
| 2 | Дисклеймер на Login-странице admin UI | ✅ | `frontend/src/pages/LoginPage.tsx` — «Сервис разработан командой хакатона и не является официальной функцией платформы МАКС» |
| 3 | Согласие на обработку данных с версией документа и timestamp | ✅ | `backend/app/services/consent.py::grant_consent`; таблица `consents(user_id, doc_version, granted_at)`; `UniqueConstraint("user_id", "doc_version")` |
| 4 | Повторный запрос согласия при смене версии документа | ✅ | `backend/app/services/consent.py::has_active_consent` проверяет `doc_version == CONSENT_VERSION` |
| 5 | Сбор ФИО субъекта ПДн (ФЗ-152) после согласия | ✅ | `backend/app/bot/handlers.py::on_message` — режим ASK_NAME; валидация: 3 слова, каждое с заглавной; `User.name = ФИО` |
| 6 | Телефон в базовом сценарии не запрашивается | ✅ | `User.phone` в модели как точка расширения, но в боте не запрашивается |
| 7 | Каталог карточек: название, дата, длительность, формат (онлайн/очно), признак свободных мест | ✅ | `backend/app/bot/handlers.py` + `texts.py`; `Event.title`, `starts_at`, `duration_minutes`, `format`, `free_slots()` |
| 8 | Карточка без мест — кнопка «Записаться» недоступна, отдельная кнопка waitlist | ✅ | `backend/app/bot/keyboards.py::event_card_kb` — при `has_free_slots=False`: «🚫 Мест нет» (noop) + отдельная «⏳ Встать в очередь» |
| 9 | Кнопки «Подробнее» и «Записаться» внутри карточки | ✅ | `backend/app/bot/keyboards.py::event_card_kb` |
| 10 | «Подробнее» — расширенное описание, требования к участникам, адрес / ссылка на подключение, условия отмены | ✅ | `backend/app/bot/handlers.py::_show_event_details`; поля `requirements`, `cancellation_terms`, `location`, `meeting_url` |
| 11 | Слоты — выбор через inline-кнопки; нет слотов — сразу к подтверждению | ✅ | `backend/app/bot/handlers.py`; `backend/app/services/registration.py::sign_up(slot_id=...)` |
| 12 | Сводка перед подтверждением: мероприятие, дата, выбранный слот, формат + напоминание о возможности отмены | ✅ | `backend/app/bot/handlers.py::_show_signup_summary` |
| 13 | Код записи RG-XXXXXX выдаётся после подтверждения | ✅ | `backend/app/models.py::_generate_reg_code()` — алфавит 32 символа без 0/O/1/I |
| 14 | Отмена до начала — место возвращается в пул доступных | ✅ | `backend/app/services/registration.py` — cancel logic + `_shift_waitlist_positions` |
| 15 | После отмены — предложение записаться на другое мероприятие | ✅ | `backend/app/bot/handlers.py:765` — `CANCEL_DONE` с `attachments=[main_menu_kb()]`; `CANCEL_DONE_WITH_PROMOTION` тоже |
| 16 | Отмена после начала — DISALLOW или ALLOW_MARKED по правилу мероприятия | ✅ | `backend/app/services/registration.py` — `LateCancelPolicy.DISALLOW / ALLOW_MARKED` |
| 17 | При ALLOW_MARKED место НЕ возвращается в пул | ✅ | `RegStatus.LATE_CANCELLED`, `_shift_waitlist_positions` не вызывается |
| 18 | Per-event mute уведомлений — настройка внутри записи, не отписка от бота | ✅ | `Registration.notifications_enabled`; `backend/app/services/broadcast.py::get_recipients` фильтрует по нему |
| 19 | Per-event mute соблюдается при QR-скане («Спасибо, что пришли») | ✅ | `backend/app/services/scan.py:152-158` — проверяет оба флага: `user.notifications_enabled` AND `reg.notifications_enabled` перед отправкой |
| 20 | Допустимые типы уведомлений: напоминание 24ч, напоминание 1ч | ✅ | `backend/app/scheduler.py` — `day_before` / `hour_before` |
| 21 | Stale reminders: напоминания при перезапуске не уходят с опозданием | ✅ | `backend/app/scheduler.py:83-93` — staleness-check: если `now - remind_at > 300s` → `sent=True`, пропуск без отправки |
| 22 | Организатор видит только свои мероприятия | ✅ | `backend/app/api/deps.py::assert_event_owned`; `GET /events` фильтрует по `organizer_id` для non-admin |
| 23 | Поиск по коду RG-XXXXXX в меню организатора | ✅ | `frontend/src/pages/EventDetailPage.tsx`; фильтрация списка регистраций |
| 24 | Статусы записей: Подтверждена / Отменена пользователем / Отменена организатором | ✅ | `backend/app/models.py` — `RegStatus.CONFIRMED / CANCELLED / CANCELLED_BY_ORGANIZER / LATE_CANCELLED / WAITLIST / ATTENDED` |
| 25 | Учёт посещаемости через QR-сканер (отметить «пришёл») | ✅ | `frontend/src/pages/ScannerPage.tsx`; `POST /api/v1/scan`; `backend/app/services/scan.py`; `Registration.attended_at` |
| 26 | Закрытие регистрации — кнопка «Записаться» скрыта, бейдж «Регистрация закрыта» | ✅ | `Event.registration_open`; `backend/app/bot/keyboards.py::event_card_kb(registration_open=False)` |
| 27 | Рассылки только per-event, не общие | ✅ | `backend/app/services/broadcast.py` — всегда привязана к `event_id` |
| 28 | Роли реализованы технически (не договорённостями) | ✅ | `OrganizerRole.ADMIN / ORGANIZER`; `assert_event_owned` + `AdminOrganizer` dependency |
| 29 | Техадмин: доступ к ПДн в логах — минимальный | ✅ | В логах: `user_id`, действие. Email/phone не логируются. `audit_logs` — `backend/app/services/audit.py` |
| 30 | Audit-log действий организатора (ФЗ-149 + ТЗ §3) | ✅ | Таблица `audit_logs`, `backend/app/services/audit.py`, `GET /api/v1/audit-logs` (admin-only), страница `/audit` в SPA |
| 31 | Повторная отправка QR по запросу пользователя | ✅ | `backend/app/bot/handlers.py::_resend_qr`; кнопка «🎫 Получить QR» в «Мои записи» |
| 32 | Право на удаление персональных данных пользователя (ФЗ-152 ст.21) | ⚠️ | Вне скоупа хакатона. В проде требует `DELETE /api/v1/me` + команду бота `/delete_account`. Зафиксировано в `docs/10-compliance.md` |
| 33 | Срок хранения ПДн определён | ⚠️ | Вне скоупа хакатона. Нет политики retention. Зафиксировано в `docs/10-compliance.md` |

**Итог: 31 ✅ / 2 ⚠️ / 0 ❌**

Все технические требования ТЗ реализованы и проверены. Два ⚠️ — compliance-пробелы (право на удаление, срок хранения ПДн), вынесены за рамки хакатона в `docs/10-compliance.md` как приоритет для продовой инсталляции.
