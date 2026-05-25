"""ORM-модели всех таблиц БД.

Принципы:
* одна таблица — один класс;
* все колонки типизированы `Mapped[type]` (нативный SQLAlchemy 2.0 typing);
* индексы — только на тех колонках, по которым реально фильтруем (event_id,
  user_id, status, starts_at, remind_at);
* enum-подобные поля храним как строки — это делает миграции и ручные
  правки в БД безболезненными.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Перечисления храним как классы со строковыми константами, а не как enum:
# в БД пишется обычный VARCHAR, поэтому добавить/переименовать статус можно
# без миграции схемы.

class EventStatus:
    DRAFT = "draft"            # черновик, в боте не виден
    PUBLISHED = "published"    # опубликовано, доступно для записи
    CANCELLED = "cancelled"    # отменено
    FINISHED = "finished"      # уже прошло (можно ставить вручную или через крон)


class EventType:
    OPEN_DAY = "open_day"           # день открытых дверей
    MASTERCLASS = "masterclass"     # мастер-класс
    OLYMPIAD = "olympiad"           # олимпиада
    TOUR = "tour"                   # экскурсия
    CONSULTATION = "consultation"   # консультация
    OTHER = "other"


class RegStatus:
    """Статусы записи. Соответствуют ТЗ §«Меню организатора»: подтверждена,
    отменена пользователем, отменена организатором, поздняя отмена, посетил."""
    CONFIRMED = "confirmed"                          # подтверждена, место занято
    WAITLIST = "waitlist"                            # в очереди ожидания
    CANCELLED = "cancelled"                          # пользователь сам отменил
    LATE_CANCELLED = "late_cancelled"                # пользователь отменил уже после старта
    CANCELLED_BY_ORGANIZER = "cancelled_by_organizer"  # организатор вычеркнул вручную (ТЗ §«Меню организатора»)
    ATTENDED = "attended"                            # пришёл — отметили QR-сканером или вручную
    NO_SHOW = "no_show"                              # не пришёл (для аналитики, ставится вручную)


class EventFormat:
    """Где проходит мероприятие. Влияет на UX карточки и список полей."""
    ONLINE = "online"
    ONSITE = "onsite"


class LateCancelPolicy:
    """Что делать, если пользователь хочет отменить запись после старта.

    Из ТЗ §«Пользовательский процесс»: команда фиксирует политику в правилах
    мероприятия. Один из двух режимов — disallow или allow_marked.
    """
    DISALLOW = "disallow"            # запретить отмену, оставить как было
    ALLOW_MARKED = "allow_marked"    # разрешить, но статус LATE_CANCELLED


class OrganizerRole:
    """Роли админ-системы. Реализуются технически (см. ТЗ §3)."""
    ADMIN = "admin"          # выдаёт роли, видит всё
    ORGANIZER = "organizer"  # работает только со своими мероприятиями


class BroadcastSegment:
    ALL = "all"                 # confirmed + waitlist
    CONFIRMED = "confirmed"
    WAITLIST = "waitlist"
    NO_SHOW = "no_show"
    ATTENDED = "attended"


class User(Base):
    """Пользователь МАКС (абитуриент / студент).

    PK — `max_user_id`. Внутренний автоинкрементный id не вводим: внешние
    источники (deeplink, callback'и от MAX) оперируют только max_user_id.
    """

    __tablename__ = "users"

    max_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Если юзер пришёл по deeplink event_xxx, но ещё не дал согласия —
    # сохраняем payload здесь и применяем после клика «Я согласен».
    # Без этого новый пользователь, переходящий с афиши, после консента попал
    # бы в главное меню вместо нужной карточки (худшая точка конверсии).
    pending_deeplink_payload: Mapped[str | None] = mapped_column(String(64))
    first_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    last_active: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    registrations: Mapped[list[Registration]] = relationship(back_populates="user")


class Organizer(Base):
    """Сотрудник вуза, ведущий мероприятия в админке."""

    __tablename__ = "organizers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(255))
    # role — оставлено как точка расширения (например, `admin` vs `moderator`).
    role: Mapped[str] = mapped_column(String(20), default=OrganizerRole.ORGANIZER, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    events: Mapped[list[Event]] = relationship(back_populates="organizer")


class Event(Base):
    """Мероприятие вуза.

    Допускает два режима capacity:

    * **Без слотов** — `event.capacity` это лимит на всё мероприятие. Записи
      хранят `slot_id IS NULL`.
    * **Со слотами** — реальная вместимость лежит на каждом `EventSlot.capacity`,
      `event.capacity` тогда работает как агрегат «всего мест по слотам» и
      используется только для отображения. Записи ссылаются на конкретный
      `slot_id`.

    Признак «есть слоты» — это просто `bool(event.slots)`.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(50), default=EventType.OTHER, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(String(255))
    cover_url: Mapped[str | None] = mapped_column(String(512))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    organizer_id: Mapped[int | None] = mapped_column(ForeignKey("organizers.id"))
    status: Mapped[str] = mapped_column(
        String(20), default=EventStatus.DRAFT, nullable=False, index=True
    )

    # --- ТЗ-обязательные поля ---
    # Длительность в минутах для карточки. Считаем из ends_at-starts_at,
    # если организатор не задал явно.
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    # Формат: online | onsite. Влияет на отображение и набор обязательных полей
    # (для online — обязательна meeting_url; для onsite — location).
    format: Mapped[str] = mapped_column(
        String(20), default=EventFormat.ONSITE, nullable=False
    )
    # Дополнительный текст для кнопки «Подробнее» в боте.
    requirements: Mapped[str | None] = mapped_column(Text)
    cancellation_terms: Mapped[str | None] = mapped_column(Text)
    # Ссылка на zoom/meet/jitsi для online-мероприятий.
    meeting_url: Mapped[str | None] = mapped_column(String(512))
    # Закрыли запись вручную (capacity ещё не исчерпан, но организатор
    # хочет остановить новые регистрации). Бот скрывает «Записаться»,
    # отображает «Регистрация закрыта» (ТЗ §«Пользовательский процесс»).
    registration_open: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    # Политика поздней отмены — disallow | allow_marked (см. LateCancelPolicy).
    late_cancel_policy: Mapped[str] = mapped_column(
        String(20), default=LateCancelPolicy.DISALLOW, nullable=False
    )
    # Сколько раз один пропуск можно пронести через сканер. По умолчанию 1
    # (классический «однократный вход»). Значение 0 — безлимит (например,
    # сезонный абонемент или многодневное мероприятие). 2+ — конкретное число
    # проходов (день открытых дверей с двумя сессиями: утро + вечер).
    max_entries: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # --- Интеграция: events, пришедшие из внешней системы (priem.mirea.ru, ИС вуза) ---
    # external_source — идентификатор системы-источника ("mirea_priem", "mirea_main", "1c_iss").
    # external_id    — ID события в этой системе. Уникальная пара (source, external_id)
    #                  → идемпотентный upsert через POST /api/v1/integration/events/sync.
    # external_url   — обратная ссылка на оригинал (для аудита и кнопки «открыть оригинал»).
    external_source: Mapped[str | None] = mapped_column(String(64), index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), index=True)
    external_url: Mapped[str | None] = mapped_column(String(512))

    deeplink_payload: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        default=lambda: f"event_{uuid.uuid4().hex[:12]}",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    organizer: Mapped[Organizer | None] = relationship(back_populates="events")
    registrations: Mapped[list[Registration]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    slots: Mapped[list[EventSlot]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventSlot.starts_at",
    )

    def has_slots(self) -> bool:
        """True, если у мероприятия есть хотя бы один слот."""
        return len(self.slots) > 0

    def confirmed_count(self) -> int:
        """Сколько участников реально занимают место (CONFIRMED + ATTENDED оба занимают слот)."""
        return sum(
            1 for r in self.registrations
            if r.status in (RegStatus.CONFIRMED, RegStatus.ATTENDED)
        )

    def total_capacity(self) -> int:
        """Реальная вместимость — сумма по слотам или event.capacity."""
        if self.has_slots():
            return sum(s.capacity for s in self.slots)
        return self.capacity

    def free_slots(self) -> int:
        """Свободных мест всего по мероприятию. Никогда не отрицательное.

        Возвращает 0 если регистрация закрыта (registration_open=False),
        чтобы UI не показывал «есть места» при закрытой записи.
        """
        if not self.registration_open:
            return 0
        return max(0, self.total_capacity() - self.confirmed_count())

    def can_accept_registrations(self) -> bool:
        """Можно ли сейчас записаться. Не учитывает capacity (это отдельно)."""
        return (
            self.status == EventStatus.PUBLISHED
            and self.registration_open
            and self.starts_at > datetime.now(UTC).replace(tzinfo=None)
        )


# Генератор человеко-читаемого reg-кода. Алфавит без 0/O/1/I — чтоб не путать
# на распечатке. 6 символов из 32 = 32^6 ≈ 1 млрд комбинаций. Коллизий мало,
# но всё равно проверяем в sign_up через уникальный constraint.
_REG_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_reg_code() -> str:
    """RG-XXXXXX, где X — символ из 32-символьного алфавита без двусмысленностей."""
    return "RG-" + "".join(secrets.choice(_REG_CODE_ALPHABET) for _ in range(6))


class EventSlot(Base):
    """Временное окно у мероприятия.

    Один Event может иметь несколько слотов (ТЗ §«Пользовательский процесс»:
    «несколько временных окон»). У каждого слота своя `capacity` — это
    основное «место», на которое записывается пользователь. Если у Event
    слотов нет, записываются на сам Event (slot_id NULL у Registration).
    """

    __tablename__ = "event_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Опциональный человеко-читаемый ярлык, если организатор хочет назвать слот
    # (например, «Группа А», «11:00 — экскурсия по корпусу А»).
    label: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    event: Mapped[Event] = relationship(back_populates="slots")
    registrations: Mapped[list[Registration]] = relationship(
        back_populates="slot",
        # ON DELETE для слота не каскадно сносим записи: если слот удалили,
        # запись остаётся, но slot_id обнуляется (организатор сам решит).
        passive_deletes=True,
    )

    def confirmed_count(self) -> int:
        return sum(
            1 for r in self.registrations
            if r.status in (RegStatus.CONFIRMED, RegStatus.ATTENDED)
        )

    def free_slots(self) -> int:
        return max(0, self.capacity - self.confirmed_count())


class Registration(Base):
    """Запись пользователя на мероприятие.

    Уникальная пара `(event_id, user_id)` — один пользователь не получит две
    записи на одно мероприятие (даже если у мероприятия слоты — выбирать слот
    можно только один). При повторной попытке после отмены мы переиспользуем
    запись (см. `services.registration.sign_up`).

    `code` — человекочитаемый идентификатор записи для поиска админом на
    входе (ТЗ §«Пользовательский процесс»). `qr_token` остался — это
    непредсказуемый секрет для QR-картинки, а `code` — короткий и
    «диктуемый по телефону» (~RG-AB12CD).

    `notifications_enabled` per-event (ТЗ §«Пользовательский процесс»:
    «настройка внутри записи, а не отписка от бота в целом»).
    """

    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_reg_event_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_slots.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.max_user_id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # qr_token — секрет в QR, 32 hex.
    qr_token: Mapped[str] = mapped_column(
        String(64), unique=True, default=lambda: uuid.uuid4().hex, nullable=False
    )
    # code — публичный «код записи» (RG-XXXXXX) для поиска админом на входе.
    code: Mapped[str] = mapped_column(
        String(16), unique=True, default=_generate_reg_code, nullable=False, index=True
    )
    waitlist_position: Mapped[int | None] = mapped_column(Integer)
    # Per-event переключатель уведомлений. По умолчанию включено.
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    registered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    attended_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Счётчик использований пропуска. Растёт при каждом успешном скане.
    # Лимит хранится на `event.max_entries`. attended_at — это время ПЕРВОГО
    # скана (для аудита), last_entry_at — последнего (для UX «когда был в
    # последний раз»).
    entries_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_entry_at: Mapped[datetime | None] = mapped_column(DateTime)

    event: Mapped[Event] = relationship(back_populates="registrations")
    user: Mapped[User] = relationship(back_populates="registrations")
    slot: Mapped[EventSlot | None] = relationship(back_populates="registrations")


class Broadcast(Base):
    """Рассылка организатора по сегменту участников мероприятия."""

    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    organizer_id: Mapped[int | None] = mapped_column(ForeignKey("organizers.id"))
    segment: Mapped[str] = mapped_column(String(20), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    # scheduled_at — пока не используется; задел под «отложенные рассылки».
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Consent(Base):
    """Согласие пользователя на обработку данных.

    Из ТЗ §«Пользовательский процесс»: «Согласие должно фиксироваться в
    хранилище вместе с версией документов и моментом времени, чтобы на
    защите команда могла показать воспроизводимость и аудит.»

    Версия — это произвольный строковый ключ (например, дата принятия
    редакции, `2026-05-15`). При обновлении документа меняем `CONSENT_VERSION`
    в `app/bot/texts.py` — пользователю снова покажется экран согласия.
    """

    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint("user_id", "doc_version", name="uq_consent_user_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.max_user_id", ondelete="CASCADE"), index=True
    )
    doc_version: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class Reminder(Base):
    """Запланированное напоминание абитуриенту.

    Планировщик каждую минуту выбирает строки с `sent=False` и `remind_at<=now()`,
    отправляет сообщение и помечает `sent=True`.
    """

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), index=True
    )
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    # kind — `day_before` / `hour_before` / `custom` (на будущее).
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)


class IntegrationKey(Base):
    """API-ключ для system-to-system интеграции с внешними системами вуза.

    Зачем отдельная сущность, а не env-переменная: ключи могут жить и
    отзываться независимо от деплоя, у каждого ключа свой источник и
    свой организатор-владелец (события, импортированные этим ключом,
    будут принадлежать ему — multi-tenant сохраняется).

    `key_hash` — хеш ключа (bcrypt); plaintext выдаётся **один раз**
    при создании в `app/cli/init_project.py`. Если потерян —
    отзовите старый и сгенерируйте новый.

    `source` — короткое имя системы-источника: "mirea_priem",
    "mirea_main", "1c_iss". Уникальная пара (source, external_id)
    идентифицирует события внутри нашей БД (см. Event.external_*).
    """

    __tablename__ = "integration_keys"
    __table_args__ = (
        UniqueConstraint("source", name="uq_integration_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    organizer_id: Mapped[int] = mapped_column(
        ForeignKey("organizers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    # Auto-publish: если True — события из этой системы сразу published.
    # Если False — приходят как draft и ждут проверки оператором.
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Аудит использования — счётчик событий, импортированных этим ключом.
    total_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AuditActorType:
    ADMIN = "admin"
    ORGANIZER = "organizer"
    USER = "user"
    SYSTEM = "system"


class AuditEntityType:
    EVENT = "event"
    REGISTRATION = "registration"
    ORGANIZER = "organizer"
    SLOT = "slot"
    BROADCAST = "broadcast"
    API_KEY = "api_key"
    USER = "user"
    SYSTEM = "system"


class AuditEvent:
    ADMIN_LOGIN = "admin.login"
    ADMIN_LOGIN_FAILED = "admin.login_failed"
    EVENT_CREATED = "event.created"
    EVENT_UPDATED = "event.updated"
    EVENT_DELETED = "event.deleted"
    EVENT_PUBLISHED = "event.published"
    EVENT_CANCELLED = "event.cancelled"
    EVENT_FINISHED = "event.finished"
    REGISTRATION_OPEN_TOGGLED = "event.registration_open_toggled"
    SLOT_CREATED = "slot.created"
    SLOT_UPDATED = "slot.updated"
    SLOT_DELETED = "slot.deleted"
    CAPACITY_CHANGED = "event.capacity_changed"
    ORGANIZER_CREATED = "organizer.created"
    ORGANIZER_UPDATED = "organizer.updated"
    ORGANIZER_DELETED = "organizer.deleted"
    BROADCAST_SENT = "broadcast.sent"
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    USER_CONSENT_GIVEN = "user.consent_given"
    REGISTRATION_CREATED = "registration.created"
    REGISTRATION_CANCELLED = "registration.cancelled"
    REGISTRATION_ATTENDED = "registration.attended"
    WAITLIST_JOINED = "waitlist.joined"
    WAITLIST_PROMOTED = "waitlist.promoted"
    NOTIFICATIONS_MUTED = "notifications.muted"
    NOTIFICATIONS_UNMUTED = "notifications.unmuted"
    REMINDER_SENT = "reminder.sent"
    REMINDER_STALE_SKIPPED = "reminder.stale_skipped"
    EVENT_AUTO_FINISHED = "event.auto_finished"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    organizer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_display: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
