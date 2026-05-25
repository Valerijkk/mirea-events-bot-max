# 4. Сценарии бота

Все хендлеры — в `backend/app/bot/handlers.py`. Тексты сообщений — в
`backend/app/bot/texts.py` (чтобы менять их без правки логики). Клавиатуры —
в `backend/app/bot/keyboards.py`.

## 1. Старт, дисклеймер, согласие и ФИО

Из ТЗ: при первом запуске бот показывает описание сервиса, границы
функциональности и дисклеймер о том, что сервис разработан командой
хакатона и не является официальной функцией платформы. Согласие на
обработку данных фиксируется с версией документа и моментом времени.
После согласия бот запрашивает **ФИО** — это субъект персональных данных
по ФЗ-152, а не имя из профиля МАКС.

```
Пользователь → Нажал «Начать» в МАКС
         ↓
on_bot_started():
  ├─ upsert_user()
  ├─ Если consent отсутствует:
  │    ├─ Если был deeplink event_xxx — сохраняем его в
  │    │  User.pending_deeplink_payload (применим после ФИО)
  │    ├─ Шлём CONSENT_REQUEST (описание + дисклеймер + кнопка «✅ Я согласен»)
  │    └─ (отдельный DISCLAIMER — по /about)
  └─ Если consent уже есть и ФИО сохранено:
       └─ deeplink → карточка / без deeplink → главное меню
```

Callback `consent` → `grant_consent(user_id)` → запись в `consents`
с текущей `consent_doc_version`. Бот **не** открывает афишу сразу —
переводит пользователя в режим ожидания ФИО (`ASK_NAME`).

```
Пользователь вводит текст (не команда):
  ├─ Валидация ФИО: три слова, каждое с заглавной
  ├─ user.name = ФИО
  ├─ pending_deeplink_payload сбрасывается после применения
  ├─ NAME_SAVED + главное меню
  └─ Если был deeplink — карточка мероприятия, иначе — афиша
```

**Версионирование документа.** При обновлении формулировок в
`CONSENT_REQUEST` меняем `consent_doc_version` в `app/config.py` — бот
заново попросит согласие. Старые согласия в БД сохраняются (audit-trail).

**Команда `/about`** — вывод DISCLAIMER в любой момент.

## 2. Callback ACK (убрать spinner)

На каждый `message_callback` бот вызывает `client.answer_callback(callback_id)`
**до** обработки payload. Без ACK платформа МАКС показывает бесконечный
spinner на inline-кнопке.

## 3. Афиша → карточка мероприятия

```
Пользователь нажимает «📅 Афиша»
         ↓
_show_events_list():
  └─ get_active_events() — published, starts_at > now → список inline-кнопок
         ↓
Нажатие на event:<id> → _send_event_card():
  └─ Карточка с:
       ├─ Типом мероприятия (🏛/🛠/🏆/🚶/💬/🎓)
       ├─ Названием, описанием
       ├─ Датой + длительностью + форматом (онлайн/очно)
       ├─ Свободно мест X из Y
       └─ Кнопками: «✅ Записаться» (если есть места) или «⏳ В лист ожидания»,
          «Подробнее», «⬅️ В меню».

Если event.registration_open=False — кнопки записи скрыты, в тексте
добавляется «🚫 Регистрация закрыта».
```

## 4. «Подробнее»

```
Callback details:<id> → _show_event_details():
  └─ _send_event_card(show_details=True):
       └─ К базовой карточке добавляются блоки:
            ├─ 📋 Требования к участникам (event.requirements)
            └─ 🔄 Условия отмены (event.cancellation_terms)
```

## 5. Запись на мероприятие

### Без слотов

```
«✅ Записаться» (signup:<id>) → _start_signup_flow():
  └─ event.has_slots()=False → _show_signup_summary(slot_id=None):
       └─ Сообщение SIGNUP_SUMMARY со сводкой
          + кнопка «✅ Подтверждаю» (confirm:<id>)
         ↓
Callback confirm:<id> → _do_signup(slot_id=None):
  ├─ sign_up() (capacity по event.capacity)
  ├─ Confirmed → REG_CONFIRMED (с кодом RG-XXXXXX) + QR
  ├─ Waitlist  → REG_WAITLIST с позицией в очереди
  └─ schedule_reminders_for_registration() — за 24ч и 1ч до старта
```

### Со слотами

```
«✅ Записаться» (signup:<id>) → _start_signup_flow():
  └─ event.has_slots()=True → клавиатура слотов:
       ├─ slot:<event>:<slot1> — «12:00 — свободно 3»
       ├─ slot:<event>:<slot2> — «14:00 — свободно 0 (waitlist)»
       └─ slot:<event>:<slot3> — «16:00 — свободно 5»
         ↓
Callback slot:<event>:<slot> → _show_signup_summary(slot_id):
  └─ Сводка с конкретным слотом + «✅ Подтверждаю»
         ↓
Callback confirm:<event>:<slot> → _do_signup(slot_id):
  └─ sign_up(slot_id=...) — capacity по slot.capacity, waitlist per-slot
```

**Время реальной записи** = `slot.starts_at` (если слот есть), иначе
`event.starts_at`. От этого зависят напоминания, «🎟 Мои записи» и архив.

## 6. Код записи + QR

При confirmed-записи пользователь получает два сообщения:

1. **Код записи** `RG-XXXXXX` в тексте `REG_CONFIRMED`.
2. **QR-картинка** с зашитым `qr_token` (32 hex).

Зачем два идентификатора: код — публичный; qr_token — секретный для сканера.

## 7. Мои записи + отмена + повтор QR

```
«🎟 Мои записи» → _show_my_registrations():
  └─ Для каждой активной записи — карточка с кнопками:
       ├─ «❌ Отменить запись»
       ├─ «🎫 Получить QR»  ← повторная отправка QR-пропуска
       ├─ «📅 В календарь»
       └─ «🔕 Тише по этому» / «🔔 Снова с уведомлениями»
     Архив (cancelled/late_cancelled/cancelled_by_organizer/attended) —
     одним сообщением.
         ↓
Callback qr:<reg> → _resend_qr():
  └─ Только для confirmed/waitlist; генерирует QR из qr_token и шлёт фото
```

> После подтверждения отмены бот отправляет подтверждение и показывает
> главное меню с кнопкой «📅 Афиша» — чтобы пользователь мог сразу
> записаться на другое мероприятие.

**Поздняя отмена** (после `event.starts_at`):

| `event.late_cancel_policy` | Поведение                                                |
|----------------------------|----------------------------------------------------------|
| `disallow`                 | `cancelled=False, forbidden_late=True`. Статус не меняется. |
| `allow_marked`             | `status=LATE_CANCELLED, cancelled_at=now`, без promote.   |

## 8. Per-event отключение уведомлений

```
«🔕 Тише по этому» (notif_off:<reg>) → Reg.notifications_enabled = False
«🔔 Снова с уведомлениями» (notif_on:<reg>) → enabled=True
```

Уважают флаг: `scheduler.py`, `broadcast.py`, `notify_event_cancelled`.

Это **не** заменяет глобальный `/notify_off` (отписка от бота целиком).

## 9. Напоминания

```
APScheduler tick (каждую минуту) → process_due_reminders():
  └─ Reminder с remind_at<=now(), sent=False → send_text (day_before / hour_before)
     Пропускаем: отменённые записи, cancelled event, notifications_enabled=False
```

## 10. Рассылка от организатора

Только в рамках выбранного мероприятия (ТЗ: «не модуль массовых рассылок»).

```
Организатор в SPA /events/{id}/broadcasts →
  POST /api/v1/events/{id}/broadcasts → send_broadcast():
    └─ get_recipients(event_id, segment) + rate-limit 50 мс/сообщение
```

## 11. Отмена мероприятия организатором

```
POST /api/v1/events/{id}/status  {"status":"cancelled"}:
  ├─ event.status = CANCELLED
  └─ notify_event_cancelled() → confirmed+waitlist с учётом notifications_enabled
```

## 12. Команды бота

| Команда       | Что делает                                          |
|---------------|-----------------------------------------------------|
| `/start`      | Главное меню (или consent+ФИО у новичка)            |
| `/start <event_xxx>` | Открыть карточку по deeplink                 |
| `/help`       | Краткая справка                                     |
| `/about`      | DISCLAIMER (кто разработчик, юр. статус)            |
| `/notify_off` | Глобально выключить напоминания и рассылки          |
| `/notify_on`  | Снова включить                                      |

## 13. Любой неизвестный текст

Бот отвечает `UNKNOWN` («не понял команду, нажми кнопку в меню или /help»).
NLU намеренно не делаем — это не часть кейса.
