# 9. FAQ и устранение неполадок

## Запуск

**Q: `ModuleNotFoundError: No module named 'maxapi'`**
A: Зависимости не установлены. `pip install -r backend/requirements.txt`.

**Q: При старте: `pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings — bot_token`**
A: Не заполнен `BOT_TOKEN` в `.env`. Возьмите токен у @MasterBot в МАКС.

**Q: Где взять `BOT_USERNAME`?**
A: Это username бота без `@`, выдаётся при создании бота в МАКС.
Используется для генерации deeplink-ссылок (`https://max.me/<username>?start=...`).

**Q: Запустил `make dev` — не открывается админка.**
A: `make dev` запускает backend на `:8000` и фронт на `:5173` (или `docker compose up`
для nginx на `:80`). Открой `http://localhost:5173/login` или `http://localhost/login`.
Если не пускает — не создан администратор: `make bootstrap`.

## Бот

**Q: Бот молчит на `/start`.**
A: Проверьте логи: `LOG_LEVEL=DEBUG make dev`. Самое частое — неверный
`BOT_TOKEN` или бот не «активирован» в МАКС у @MasterBot.

**Q: При записи QR-код не приходит, только текст.**
A: Скорее всего, упал `send_photo` (формат файла, размер). См. логи —
`Не удалось отправить фото в чат ...`. Проверьте, что `qrcode[pil]`
установился полностью и `Pillow` импортируется.

**Q: Сообщение приходит дважды.**
A: Чаще всего — приложение запущено дважды. Убедитесь, что нет старого
процесса: `ps aux | grep uvicorn`. На Windows проверьте Диспетчер задач.

**Q: Напоминания не приходят.**
A: APScheduler работает в том же процессе. Если процесс перезапускался —
напоминания, чьё время уже прошло, не отправятся повторно (`sent=True`).
Дальнейшие напоминания будут идти каждую минуту.

## Webhook

**Q: Перевёл в webhook, но сообщения не приходят.**
A: Проверьте по очереди:
1. `WEBHOOK_URL` действительно отдаёт HTTPS-ответ (curl с улицы).
2. В логе при старте есть `Webhook endpoint mounted at /webhook`.
3. На сервере открыт порт, на который смотрит обратный прокси.
4. В МАКС подписка зарегистрировалась — повторите старт.

**Q: `maxapi.webhook.fastapi не установлен`**
A: Установите экстра: `pip install 'maxapi[fastapi]'`.

## Админка (React SPA)

**Q: 401 при обращении к API — что делать?**
A: Проверьте JWT-токен. В SPA он лежит в `localStorage` (`mirea-auth`).
При 401 фронт редиректит на `/login` — залогиньтесь заново.

**Q: Не отправляется рассылка из админки.**
A: Откройте `Network` в DevTools — должен быть POST на
`POST /api/v1/events/<id>/broadcasts`. Если 401 — переавторизуйтесь. Если 500 —
смотрите логи uvicorn.

**Q: Хочу поправить UI карточек участников.**
A: Компоненты в `frontend/src/pages/EventDetailPage.tsx` и `frontend/src/components/`.

## REST API

**Q: 401 на любую ручку, кроме `/auth/login`.**
A: Не передаёте `Authorization: Bearer <token>` или токен истёк.
Получите свежий через `POST /api/v1/auth/login`.

**Q: 422 при создании мероприятия.**
A: Ответ содержит точное поле и причину. Самое частое — `starts_at`
прислан строкой неверного формата (нужен ISO 8601: `2026-05-20T14:00:00`).

**Q: Можно ли создать организатора через API?**
A: Да — `POST /api/v1/organizers` (только admin). Альтернатива:
`python -m app.cli.init_project` при bootstrap.

## Данные

**Q: Где лежит БД?**
A: По умолчанию PostgreSQL (`DATABASE_URL` в `.env`). В docker-compose —
volume `pgdata`. Локально без Docker — свой инстанс Postgres на `:5432`.

**Q: Перезапустил compose — потерял данные.**
A: Проверь, что volume `pgdata` не удалён (`docker volume ls`). `docker compose down -v` сносит данные намеренно.

**Q: CI использует SQLite?**
A: Да, только в GitHub Actions для job `api-and-smoke` — один файл БД
на весь прогон. Prod и локальный dev — Postgres.

## Прочее

**Q: Где править тексты сообщений в боте?**
A: `backend/app/bot/texts.py`. Никакой логики там нет — только строки.

**Q: Хочу добавить тип мероприятия `webinar`.**
A: См. `docs/08-development.md` → «Как добавить новый тип мероприятия».

**Q: Кейс хакатона расширили, нужно ещё одно поле в мероприятии.**
A: 1) Добавить колонку в `backend/app/models.py`. 2) Добавить поле в схемы
`backend/app/schemas/event.py`. 3) Добавить инпут в форму на
`frontend/src/pages/EventDetailPage.tsx` (или форму создания). 4) `python -m app.db_init`
(или Alembic-миграция, если уже на проде).
