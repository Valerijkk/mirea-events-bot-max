"""Демо-сид для показа: чистит мероприятия и создаёт 10 событий РТУ МИРЭА.

Запуск (локально в Docker):
    docker compose exec backend python -m app.cli.seed_demo_events

Что делает:
    1. Полная очистка events, slots, registrations, broadcasts (CASCADE).
    2. Создаёт 10 опубликованных мероприятий с обложками — старты от +7 до +70
       дней от сегодня. Привязаны к организатору ИПТИП (iptip@mirea.ru).
       Если ИПТИП-а нет — падает с понятной ошибкой (запусти init_project).
    3. Аудит/лог-таблицы не трогает (это история).

Темы и обложки — реальные форматы мероприятий РТУ МИРЭА для абитуриентов
(Дни открытых дверей, мастер-классы, олимпиады, экскурсии, консультации).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.db import session_scope
from app.models import (
    Broadcast,
    Event,
    EventFormat,
    EventSlot,
    EventStatus,
    EventType,
    Organizer,
    Registration,
)


def _wipe_events(session) -> int:
    """Снести всё что связано с мероприятиями. Возвращает кол-во удалённых events."""
    # Считаем «до».
    n_events = session.scalar(select(func.count()).select_from(Event))
    n_regs = session.scalar(select(func.count()).select_from(Registration))
    n_slots = session.scalar(select(func.count()).select_from(EventSlot))
    n_broadcasts = session.scalar(select(func.count()).select_from(Broadcast))

    # CASCADE на FK снесёт регистрации/слоты/рассылки, но в SQLite каскады
    # на уровне ORM. Чистим явно от листьев к корню — единственный надёжный
    # способ для обеих БД.
    session.execute(delete(Registration))
    session.execute(delete(EventSlot))
    session.execute(delete(Broadcast))
    session.execute(delete(Event))
    session.flush()

    print(f"[wipe] events={n_events}, slots={n_slots}, regs={n_regs}, broadcasts={n_broadcasts}")
    return n_events


def _at(days: int, hour: int = 12, minute: int = 0) -> datetime:
    """Дата = сегодня + N дней, в указанное время (UTC)."""
    base = datetime.now(UTC).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base + timedelta(days=days)


# 10 мероприятий — РТУ МИРЭА, типовые для приёмной кампании.
# Обложки: тематические фото с Unsplash (бесплатные, прямой CDN — фронт сразу
# отрендерит без проксирования). Заголовки/описания взяты из реальных
# форматов сайта priem.mirea.ru и mirea.ru/news.
DEMO_EVENTS: list[dict] = [
    {
        "title": "День открытых дверей всех образовательных программ",
        "description": (
            "Главное событие приёмной кампании РТУ МИРЭА. Презентации всех "
            "институтов, выступление приёмной комиссии, экскурсии по "
            "лабораториям, профориентационное тестирование. Узнайте всё про "
            "поступление в 2026 году."
        ),
        "event_type": EventType.OPEN_DAY,
        "format": EventFormat.ONSITE,
        "location": "Москва, проспект Вернадского, 78, главный корпус",
        "cover_url": "https://images.unsplash.com/photo-1523580494863-6f3031224c94?w=1200&q=80",
        "capacity": 500,
        "days_from_now": 7,
        "hour": 10,
        "duration_minutes": 360,
        "requirements": "Студенческий или паспорт. Регистрация обязательна.",
    },
    {
        "title": "Мастер-класс: Программирование на Python для школьников",
        "description": (
            "Практический мастер-класс от преподавателей Института "
            "информационных технологий. От первой программы до простой игры — "
            "за 2 часа. Уровень: с нуля."
        ),
        "event_type": EventType.MASTERCLASS,
        "format": EventFormat.ONSITE,
        "location": "Корпус А, ауд. А-326, проспект Вернадского, 78",
        "cover_url": "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=1200&q=80",
        "capacity": 30,
        "days_from_now": 11,
        "hour": 16,
        "duration_minutes": 120,
        "requirements": "Ноутбук с Python 3.11+. Установку проверим в начале.",
    },
    {
        "title": "Олимпиада «Технология» — отборочный тур",
        "description": (
            "Предметная олимпиада РТУ МИРЭА для 9–11 классов. Победители и "
            "призёры получают льготы при поступлении: до 100 баллов ЕГЭ и "
            "БВИ на профильные направления."
        ),
        "event_type": EventType.OLYMPIAD,
        "format": EventFormat.ONSITE,
        "location": "Корпус Б, актовый зал, проспект Вернадского, 86",
        "cover_url": "https://images.unsplash.com/photo-1488998427799-e3362cec87c3?w=1200&q=80",
        "capacity": 200,
        "days_from_now": 18,
        "hour": 11,
        "duration_minutes": 180,
        "requirements": "Паспорт, ручка. Калькуляторы запрещены.",
    },
    {
        "title": "Экскурсия в Институт искусственного интеллекта",
        "description": (
            "Мегалаборатории, демонстрация наработок студентов и аспирантов: "
            "нейросети для медицины, компьютерное зрение, генеративный ИИ. "
            "Можно потрогать оборудование и задать вопросы преподавателям."
        ),
        "event_type": EventType.TOUR,
        "format": EventFormat.ONSITE,
        "location": "Институт ИИ, проспект Вернадского, 78, корпус Г",
        "cover_url": "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=1200&q=80",
        "capacity": 25,
        "days_from_now": 23,
        "hour": 14,
        "duration_minutes": 90,
        "requirements": "Закрытая обувь обязательна (требование лаборатории).",
    },
    {
        "title": "Онлайн-консультация для абитуриентов: приём 2026",
        "description": (
            "Прямой эфир с приёмной комиссией. Минимальные баллы, целевое "
            "обучение, индивидуальные достижения, общежитие, оплата. Ответим "
            "на любые вопросы в чате."
        ),
        "event_type": EventType.CONSULTATION,
        "format": EventFormat.ONLINE,
        "location": None,
        "meeting_url": "https://my.mts-link.ru/j/mirea-priem-2026",
        "cover_url": "https://images.unsplash.com/photo-1610484826917-0f101a7a8b15?w=1200&q=80",
        "capacity": 1000,
        "days_from_now": 30,
        "hour": 18,
        "duration_minutes": 90,
        "requirements": "Подключение к интернету. Камера и микрофон не обязательны.",
    },
    {
        "title": "Профориентационное тестирование «Альтаир»",
        "description": (
            "Бесплатное тестирование от Детского технопарка «Альтаир» РТУ "
            "МИРЭА. По результатам — индивидуальная консультация и рекомендации "
            "по направлениям подготовки. Подходит для 9–11 классов и СПО."
        ),
        "event_type": EventType.OTHER,
        "format": EventFormat.ONSITE,
        "location": "Детский технопарк «Альтаир», проспект Вернадского, 78",
        "cover_url": "https://images.unsplash.com/photo-1606326608606-aa0b62935f2b?w=1200&q=80",
        "capacity": 60,
        "days_from_now": 37,
        "hour": 13,
        "duration_minutes": 150,
        "requirements": "Возьмите блокнот и ручку.",
    },
    {
        "title": "День открытых дверей Колледжа программирования и кибербезопасности",
        "description": (
            "Специально для тех, кто планирует поступать после 9 класса. "
            "Презентация программ СПО, экскурсия по колледжу, встреча с "
            "преподавателями и выпускниками."
        ),
        "event_type": EventType.OPEN_DAY,
        "format": EventFormat.ONSITE,
        "location": "Колледж РТУ МИРЭА, 1-й Щипковский переулок, 3",
        "cover_url": "https://images.unsplash.com/photo-1573166364524-d9dbfd8bdf73?w=1200&q=80",
        "capacity": 200,
        "days_from_now": 44,
        "hour": 15,
        "duration_minutes": 180,
        "requirements": "Паспорт. Школьникам — в сопровождении родителя.",
    },
    {
        "title": "Хакатон «Цифровая трансформация» для абитуриентов",
        "description": (
            "Однодневный хакатон от Института перспективных технологий и "
            "индустриального программирования. Командное соревнование, "
            "менторство преподавателей, призовой фонд 300 000 ₽. "
            "Победители получают рекомендацию в приёмную комиссию."
        ),
        "event_type": EventType.OTHER,
        "format": EventFormat.ONSITE,
        "location": "Коворкинг ИПТИП, проспект Вернадского, 78, корпус Д",
        "cover_url": "https://images.unsplash.com/photo-1551434678-e076c223a692?w=1200&q=80",
        "capacity": 80,
        "days_from_now": 51,
        "hour": 9,
        "duration_minutes": 600,
        "requirements": "Ноутбук. Команда 2–4 человека или индивидуально.",
    },
    {
        "title": "Мастер-класс: AR/VR в образовании",
        "description": (
            "Дополненная и виртуальная реальность — практика на оборудовании "
            "лаборатории Института радиоэлектроники и информатики. Каждый "
            "участник наденет VR-шлем и поработает в редакторе."
        ),
        "event_type": EventType.MASTERCLASS,
        "format": EventFormat.ONSITE,
        "location": "Лаборатория AR/VR, проспект Вернадского, 78, корпус Е",
        "cover_url": "https://images.unsplash.com/photo-1593508512255-86ab42a8e620?w=1200&q=80",
        "capacity": 20,
        "days_from_now": 58,
        "hour": 17,
        "duration_minutes": 120,
        "requirements": "Без линз/очков по возможности. Закрытая обувь.",
    },
    {
        "title": "Лекция онлайн: Кибербезопасность будущего",
        "description": (
            "Открытая лекция Института кибербезопасности и цифровых "
            "технологий. Темы: пост-квантовая криптография, ИИ в защите "
            "инфраструктуры, карьера белого хакера. Запись доступна "
            "зарегистрированным."
        ),
        "event_type": EventType.MASTERCLASS,
        "format": EventFormat.ONLINE,
        "location": None,
        "meeting_url": "https://my.mts-link.ru/j/mirea-cybersec",
        "cover_url": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1200&q=80",
        "capacity": 500,
        "days_from_now": 65,
        "hour": 19,
        "duration_minutes": 75,
        "requirements": "Никаких — приходите с вопросами.",
    },
]


def _seed_events(session, organizer: Organizer) -> int:
    """Вставляет DEMO_EVENTS, возвращает кол-во созданных."""
    created = 0
    for tpl in DEMO_EVENTS:
        starts_at = _at(tpl["days_from_now"], tpl["hour"])
        ends_at = starts_at + timedelta(minutes=tpl["duration_minutes"])
        event = Event(
            title=tpl["title"],
            description=tpl["description"],
            event_type=tpl["event_type"],
            format=tpl["format"],
            starts_at=starts_at,
            ends_at=ends_at,
            location=tpl.get("location"),
            meeting_url=tpl.get("meeting_url"),
            cover_url=tpl["cover_url"],
            capacity=tpl["capacity"],
            duration_minutes=tpl["duration_minutes"],
            organizer_id=organizer.id,
            status=EventStatus.PUBLISHED,
            requirements=tpl.get("requirements"),
            registration_open=True,
        )
        session.add(event)
        session.flush()
        created += 1
        print(f"[+] {starts_at:%d.%m.%Y %H:%M}  {event.title[:60]}")
    return created


def main() -> int:
    print("=" * 70)
    print("  Демо-сид: 10 мероприятий РТУ МИРЭА")
    print("=" * 70)

    with session_scope() as session:
        organizer = session.scalar(
            select(Organizer).where(Organizer.email == "iptip@mirea.ru")
        )
        if organizer is None:
            print("[!] Организатор iptip@mirea.ru не найден.")
            print("    Сначала: docker compose exec backend python -m app.cli.init_project")
            return 1

        _wipe_events(session)
        n = _seed_events(session, organizer)

    print()
    print(f"[OK] Создано {n} опубликованных мероприятий, владелец — {organizer.email}.")
    print("     Открывай админку → /events.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
