# 6. Панель администратора (React SPA)

Административная панель — React SPA. В prod за nginx на `http://localhost/`,
в dev — Vite на `:5173` с proxy `/api` → backend `:8000`.

## Стек

| Слой | Технология |
|------|------------|
| Сборка | Vite |
| UI | React 18 + TypeScript |
| Стили | Tailwind CSS (локальный билд) |
| Серверное состояние | TanStack Query |
| Клиентское состояние | Zustand (auth, тосты) |
| Графики | recharts (Stats, Audit) |
| Маршрутизация | React Router v6 |

## Авторизация

* Вход через `/login` (email + пароль).
* JWT хранится в `localStorage` (`mirea-auth`), в API уходит как `Authorization: Bearer …`.
* При 401 axios-interceptor редиректит на `/login`.
* CSRF не нужен — только JSON REST, без HTML-форм.

## Роли

| Возможность | `organizer` | `admin` |
|-------------|:-----------:|:-------:|
| Свои мероприятия (CRUD, слоты, записи, рассылки, сканер) | ✅ | ✅ (все events) |
| `GET /events/{id}` чужого мероприятия | ❌ 403 | ✅ |
| `/stats` — глобальная статистика | ❌ | ✅ |
| `/audit` — журнал действий | ❌ | ✅ |
| `/organizers` — управление учётками | ❌ | ✅ |

Multi-tenant на backend: `assert_event_owned` / `OwnedEvent`. Admin обходит
проверку владельца.

## Страницы

| Маршрут | Компонент | Доступ |
|---------|-----------|--------|
| `/login` | LoginPage | Публичный (дисклеймер хакатона на форме) |
| `/events` | EventsPage | organizer, admin |
| `/events/:id` | EventDetailPage | organizer (своё), admin |
| `/events/:id/slots` | SlotsPage | organizer (своё), admin |
| `/events/:id/scanner` | ScannerPage | organizer (своё), admin |
| `/events/:id/broadcasts` | BroadcastsPage | organizer (своё), admin |
| `/stats` | StatsPage | **только admin** — recharts: воронка, регистрации по дням |
| `/audit` | AuditPage | **только admin** — таблица + фильтры + мини-график активности |
| `/organizers` | OrganizersPage | **только admin** |

Страница «стена явки» (`/events/:id/wall`) **удалена** — явку смотрят в
карточке мероприятия и через сканер.

Навигация: боковое меню в `Layout`. Пункты Stats / Audit / Organizers
рендерятся только при `role=admin` (`AdminRoute` + условие в `Layout`).

## API документация

Swagger UI: `/docs` (через nginx проксируется на backend). Напрямую к
uvicorn в dev: `http://localhost:8000/docs`.

## Сборка

```bash
cd frontend
npm install
npm run build   # dist/ → nginx или backend/static в dev
npm run dev     # :5173, proxy /api → :8000
```

Docker: образ `frontend` — nginx + статика из `dist/`, см. `docs/07-deployment.md`.
