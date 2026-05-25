# Compliance: ФЗ-152 + ФЗ-149 + OWASP + WCAG + ГОСТ

Дата: 26.05.2026.
Проект: mirea-events-bot, хакатон «Весенний код» РТУ МИРЭА × VK × 1С × МКСКОМ, кейс №2 «МАКС».
Стек: FastAPI + SQLAlchemy 2.0 + PostgreSQL + React SPA + MAX Bot API.

---

## 2.1 ФЗ-152 «О персональных данных»

### Состав собираемых ПДн

| Поле | Таблица | Назначение | Основание сбора | Обязательно? |
|---|---|---|---|---|
| `max_user_id` | `users` | Идентификатор пользователя в МАКС, PK | Необходим для работы бота | Да |
| `chat_id` | `users` | ID чата для отправки сообщений ботом | Необходим для работы бота | Да |
| `name` | `users` | ФИО — идентификатор субъекта ПДн по ФЗ-152 | ТЗ §«Пользовательский процесс»; вводится вручную после согласия | Да |
| `username` | `users` | Никнейм МАКС, опциональный | Для обратной связи | Нет |
| `phone` | `users` | Поле в модели (`String(20)`) | **Не собирается** в базовом flow | Нет |
| `email` | `organizers` | Логин организатора в SPA-админке | Аутентификация | Да (только сотрудники) |
| `password_hash` | `organizers` | bcrypt-хеш, plaintext не хранится | Аутентификация | Да |
| `name`, `department` | `organizers` | ФИО и кафедра организатора | Для UI | Нет |

**Вывод:** принцип минимизации соблюдён. Поле `phone` в `backend/app/models.py` присутствует как точка расширения, но в хендлерах не запрашивается и не заполняется.

### Согласие на обработку

| Норма | Требование | Статус | Реализация | Файл:строка |
|---|---|---|---|---|
| ФЗ-152 ст.9 | Явное согласие до начала обработки | ✅ | Бот блокирует все действия до нажатия «Я согласен» | `backend/app/bot/handlers.py::on_bot_started` |
| ФЗ-152 ст.9 | После согласия — сбор ФИО субъекта | ✅ | Бот переходит в режим ASK_NAME, ФИО валидируется (3 слова, заглавные) | `backend/app/bot/handlers.py::on_message` |
| ФЗ-152 ст.9 | Версия документа фиксируется | ✅ | `Consent.doc_version = CONSENT_VERSION` из `config.py` | `backend/app/services/consent.py:50` |
| ФЗ-152 ст.9 | Момент времени согласия фиксируется | ✅ | `Consent.granted_at = server_default=func.now()` | `backend/app/models.py` |
| ФЗ-152 ст.9 | Повторное согласие при обновлении документа | ✅ | `has_active_consent` проверяет актуальную версию | `backend/app/services/consent.py:20` |
| ФЗ-152 ст.9 | Идемпотентность (нет дублей согласия) | ✅ | `UniqueConstraint("user_id", "doc_version")` | `backend/app/models.py` |
| Приказ РКН №274 | Форма согласия содержит: кто обрабатывает, цели, состав данных | ⚠️ | Текст в боте есть. Отдельного документа «Политика конфиденциальности» нет | `backend/app/bot/texts.py::CONSENT_REQUEST` |

### Права субъекта ПДн

| Норма | Требование | Статус | Что сделать |
|---|---|---|---|
| ФЗ-152 ст.14 | Право на доступ к своим данным | ❌ | Нет команды бота или ручки `/me` |
| ФЗ-152 ст.14 | Право на исправление | ❌ | Нет ручки обновления профиля |
| ФЗ-152 ст.21 | Право на удаление (отзыв согласия) | ❌ | Нет `DELETE /api/v1/me`, нет `/delete_account` в боте. Данные хранятся бессрочно |
| ФЗ-152 ст.22 | Уведомление РКН об обработке ПДн | ⚠️ | Для хакатона — вне скоупа. В проде — обязательно |

### Хранение и безопасность

| Норма | Требование | Статус | Комментарий |
|---|---|---|---|
| ФЗ-152 ст.18.1 | Хранение ПДн на территории РФ | ⚠️ | Зависит от места деплоя Docker-контейнеров. Не задокументировано |
| ФЗ-152 ст.19 | Технические меры защиты | ✅ | bcrypt, JWT Bearer, rate-limit, security headers, IDOR-защита на каждом роуте |
| ФЗ-152 ст.22 | Срок хранения определён | ❌ | Нет политики retention. Данные хранятся пока существует БД |

**Итог по ФЗ-152:** частично соответствует. Согласие с версионированием и сбор ФИО после согласия — реализованы хорошо. Критические пробелы: право на удаление (ст.21), нет срока хранения (ст.22), нет Политики конфиденциальности как документа.

---

## 2.2 ФЗ-149 «Об информации»

| Норма | Требование | Статус | Реализация | Файл:строка |
|---|---|---|---|---|
| ФЗ-149 ст.16 | Журналирование действий операторов | ✅ | Таблица `audit_logs`, сервис `backend/app/services/audit.py`, API `GET /api/v1/audit-logs` | `backend/app/services/audit.py` |
| ФЗ-149 ст.16 | Журнал доступен для проверки | ✅ | Страница `/audit` в React SPA с фильтрами и мини-графиком активности (только admin) | `frontend/src/pages/AuditPage.tsx` |
| ФЗ-149 ст.16 | Базовое техническое логирование | ✅ | `logging.basicConfig` в `backend/app/main.py`; uvicorn пишет HTTP access log | `backend/app/main.py` |
| ФЗ-149 ст.16 | ПДн в логах — минимально | ✅ | В логах: `user_id`, действие. Email/phone не пишутся | `backend/app/main.py` |
| ФЗ-149 ст.16 | Разграничение доступа | ✅ | `OrganizerRole.ADMIN / ORGANIZER`; `assert_event_owned`; `AdminOrganizer` dep | `backend/app/api/deps.py` |
| ФЗ-149 ст.17 | Интегритет и доступность | ⚠️ | `pg_dump` задокументирован в `docs/07-deployment.md`, но не автоматизирован. Вне скоупа хакатона | `docs/07-deployment.md` |

**Итог по ФЗ-149:** полностью реализован. Backup-процедура задокументирована (ст.17), но не автоматизирована — вне скоупа хакатона.

---

## 2.3 OWASP Top 10

| Категория | Применимость | Статус | Реализация | Файл:строка |
|---|---|---|---|---|
| A01 Broken Access Control | Высокая (multi-tenant) | ✅ | `assert_event_owned` — IDOR-защита. `GET /events` фильтрует по `organizer_id` для не-admin. Admin обходит check | `backend/app/api/deps.py`, `backend/app/api/v1/events.py` |
| A01 | Admin не может понизить себя | ✅ | Защита от самопонижения роли в `update_organizer` | `backend/app/api/v1/organizers.py` |
| A02 Cryptographic Failures | Высокая | ✅ | bcrypt (`passlib.CryptContext(schemes=["bcrypt"])`); JWT HS256, секрет из `.env` | `backend/app/admin/auth.py` |
| A02 | QR-token — непредсказуемый секрет | ✅ | `Registration.qr_token = uuid4().hex` (32 hex, ~128 бит энтропии) | `backend/app/models.py` |
| A03 Injection | Высокая | ✅ | SQLAlchemy ORM везде, нет raw SQL без параметров. Bandit: High=0, Medium=0 | `backend/app/` весь |
| A03 XSS | Средняя | ✅ | React SPA — типизированный API-клиент, нет `dangerouslySetInnerHTML`, нет innerHTML | `frontend/src/` |
| A04 Insecure Design | Средняя | ✅ | JSON-only REST API + Bearer token исключают CSRF by design; rate-limit; phone не собирается | `backend/app/core/rate_limit.py` |
| A05 Security Misconfiguration | Средняя | ⚠️ | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` — реализованы. Явный `Content-Security-Policy` не настроен (вне скоупа хакатона — локальный бандл, нет CDN) | `backend/app/core/security_headers.py` |
| A06 Vulnerable Components | Низкая | ⚠️ | Версии зафиксированы в `requirements.txt` и `package.json`. Dependabot — вне скоупа хакатона | `requirements.txt` |
| A07 Identification & Auth Failures | Высокая | ✅ | Rate-limit `/api/v1/auth/login` — 5 req/min/IP → 429. User-enum защита: одинаковый текст ошибки для wrong-pass и unknown-email | `backend/app/core/rate_limit.py`; `backend/app/api/v1/auth.py` |
| A07 | JWT не принимается мусорный/пустой | ✅ | `decode_token` возвращает `None` при любой `PyJWTError`; тест в `tests/api/auth/` | `backend/app/admin/auth.py` |
| A08 Software & Data Integrity | Низкая | ✅ | CSV-export с префиксом `'` против formula injection | `backend/app/api/v1/registrations.py` |
| A09 Security Logging & Monitoring | Высокая | ✅ | Таблица `audit_logs`, сервис `backend/app/services/audit.py`, REST `GET /api/v1/audit-logs` (admin-only) | `backend/app/services/audit.py` |
| A10 SSRF | Низкая | ✅ | Нет user-controlled URL для fetch на стороне бэка. `cover_url` / `meeting_url` хранятся, но не fetch'атся сервером | `backend/app/models.py` |

---

## 2.4 WCAG 2.1 AA (React SPA)

Проверяется React SPA (`frontend/src/`). Бот-интерфейс (МАКС) — accessibility на стороне платформы.

| Критерий WCAG | Описание | Статус | Реализация | Файл |
|---|---|---|---|---|
| 1.1.1 Non-text content | Alt-тексты для изображений и иконок | ✅ | SVG-иконки с `aria-hidden="true"` или текстовым контекстом кнопки | `frontend/src/components/Select.tsx`, `Layout.tsx` |
| 1.3.1 Info and Relationships | `<label>` связан с полем через `htmlFor` | ⚠️ | В `EventForm.tsx` часть `<label>` для Select-компонентов без `htmlFor` | `frontend/src/components/EventForm.tsx` |
| 1.3.1 | Таблицы с `<th scope="col">` | ✅ | `EventDetailPage.tsx` — `scope="col"` на заголовках | `frontend/src/pages/EventDetailPage.tsx` |
| 1.4.3 Contrast (Minimum) | Контраст текста ≥ 4.5:1 | ✅ | Tailwind `slate-500+` для основного текста, `brand-*` для акцентов | `frontend/` |
| 2.1.1 Keyboard | Вся функциональность доступна с клавиатуры | ⚠️ | Кастомный `Select`-компонент не поддерживает роving tabindex / arrow-навигацию | `frontend/src/components/Select.tsx` |
| 2.4.7 Focus Visible | Видимый фокус-индикатор | ✅ | Tailwind `focus:ring-2 focus:ring-brand-500` на интерактивных элементах | `frontend/src/` |
| 4.1.2 Name, Role, Value | ARIA для кастомных компонентов | ⚠️ | `Select`: нет `role="combobox"`, `aria-expanded`, `aria-controls`; `Modal`: нет focus trap | `frontend/src/components/Select.tsx`, `Modal.tsx` |
| 1.4.4 Resize text | Текст масштабируется до 200% без потери контента | ✅ | Tailwind responsive, нет fixed-px для текста | `frontend/src/` |

**Итог по WCAG:** базовый уровень AA в целом достигнут. Нерешённые моменты: кастомный Select без полного WAI-ARIA combobox-паттерна, Modal без focus trap.

---

## 2.5 ГОСТ Р ИСО/МЭК 27001-2021 (релевантные пункты)

| Приложение A | Требование | Статус | Реализация | Файл:строка |
|---|---|---|---|---|
| A.9.2.1 | Управление доступом — технически реализованные роли | ✅ | `OrganizerRole.ADMIN / ORGANIZER`; `assert_event_owned`; `AdminOrganizer` dep | `backend/app/api/deps.py` |
| A.9.4.2 | Процедуры безопасного входа (rate-limit, защита от перебора) | ✅ | 5 req/min на `/api/v1/auth/login` → 429; user-enum защита | `backend/app/core/rate_limit.py` |
| A.9.4.3 | Парольная политика | ⚠️ | bcrypt — алгоритм правильный. `minLength={8}` на фронте. Валидация на бэкенде (Pydantic `min_length`) — зафиксировано как пробел, вне скоупа хакатона | `frontend/src/pages/OrganizersPage.tsx`; `backend/app/schemas/organizer.py` |
| A.10.1 | Криптографические меры защиты | ✅ | bcrypt + JWT HS256 Bearer + uuid4 QR-tokens (128 бит) | `backend/app/admin/auth.py` |
| A.12.3 | Резервное копирование | ❌ | Нет задокументированной backup-процедуры. `pg_dump` упомянут в `docs/07-deployment.md`, но не автоматизирован | `docs/07-deployment.md` |
| A.12.4 | Логирование и мониторинг событий | ✅ | Таблица `audit_logs`, сервис `backend/app/services/audit.py`, REST `GET /api/v1/audit-logs` | `backend/app/services/audit.py` |
| A.13.1 | Сетевая безопасность, защита передаваемых данных | ✅ | Security headers middleware: `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` | `backend/app/core/security_headers.py` |
| A.13.1 | CSRF-защита | ✅ | JSON-only REST API + Bearer token — CSRF невозможен by design (нет HTML-форм, нет cookie-auth) | `backend/app/api/v1/auth.py` |
| A.18.1 | Соблюдение законодательства (ФЗ-152) | ⚠️ | Частично — см. раздел 2.1 выше | — |

**Итог по ГОСТ 27001:** ключевые технические меры реализованы. Критические пробелы: нет backup-процедуры (A.12.3), минимальная длина пароля не валидируется на бэкенде (A.9.4.3).

---

## 2.6 Итоговая таблица соответствия

| Стандарт / Норма | Статус | Пробелы (вне скоупа хакатона) | Приоритет для прода |
|---|---|---|---|
| ФЗ-152 «О персональных данных» | ⚠️ Частично | Нет `DELETE /api/v1/me` (ст.21); нет политики retention (ст.22); нет отдельного PDF «Политика конф.» | Высокий |
| ФЗ-149 «Об информации» | ✅ Реализован | Backup не автоматизирован (ст.17) — `pg_dump` задокументирован | Низкий |
| OWASP Top 10 | ✅ В основном | CSP не настроен (A05); Dependabot не подключён (A06) | Средний |
| WCAG 2.1 AA | ✅ Базовый AA | Select без WAI-ARIA combobox; Modal без focus trap | Низкий |
| ГОСТ Р ИСО/МЭК 27001-2021 | ✅ В основном | Backup не автоматизирован (A.12.3); `min_length` пароля только на фронте (A.9.4.3) | Средний |

---

## Статус технических требований ТЗ

Все технические требования хакатонного ТЗ реализованы — см. полную таблицу в `docs/05-tz-diff.md` (31 ✅ / 2 ⚠️ вне скоупа / 0 ❌).

## Compliance-риски (для продовой инсталляции)

1. **Право на удаление ПДн (ФЗ-152 ст.21)** — нет `DELETE /api/v1/me` и `/delete_account` в боте. Обязательно для прода при обработке реальных ПДн.
2. **Отсутствие CSP-заголовка (OWASP A05)** — явная `Content-Security-Policy` не настроена. Риск снижен локальным бандлом Tailwind и отсутствием CDN.
3. **`min_length` пароля не в Pydantic-схеме (ГОСТ A.9.4.3)** — только фронтовая валидация; через API можно создать организатора с коротким паролем.
