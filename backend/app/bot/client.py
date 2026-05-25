"""Тонкий HTTP-клиент к MAX Bot API на базе httpx.

`maxapi` оказалась несовместима с реальным API (по Postman-коллекции
организаторов), поэтому собственная обёртка.

Документация: https://dev.max.ru/docs-api
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Подменяется в тестах.
MAX_API_BASE_URL = "https://platform-api.max.ru"

# MAX держит /updates открытым до `timeout` секунд, ожидая события.
DEFAULT_LONG_POLL_TIMEOUT = 30


class MaxApiError(Exception):
    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"MAX API error {status_code}: {body!r}")
        self.status_code = status_code
        self.body = body


class MaxClient:
    """Один экземпляр на процесс: внутри httpx AsyncClient с пулом соединений.

    Закрытие — через `await client.close()` в lifespan FastAPI.
    """

    def __init__(self, token: str, base_url: str = MAX_API_BASE_URL) -> None:
        if not token:
            raise ValueError("MAX bot token is required")
        self._token = token
        self._base_url = base_url.rstrip("/")
        # MAX ждёт `Authorization: <token>` БЕЗ префикса «Bearer».
        # read=60 потому что long polling имеет собственный таймаут до 30+10.
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": self._token},
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        timeout: float | None = None,
    ) -> Any:
        try:
            response = await self._client.request(
                method,
                path,
                params=params,
                json=json,
                timeout=timeout if timeout is not None else self._client.timeout,
            )
        except httpx.HTTPError as exc:
            # Решение о ретрае оставляем вызывающему коду.
            logger.warning("MAX %s %s: %s", method, path, exc)
            raise

        try:
            payload = response.json()
        except ValueError:
            payload = response.text

        if response.status_code >= 400:
            raise MaxApiError(response.status_code, payload)
        return payload

    async def get_me(self) -> dict:
        return await self._request("GET", "/me")

    async def get_subscriptions(self) -> dict:
        return await self._request("GET", "/subscriptions")

    async def set_webhook(self, url: str, secret: str | None = None) -> dict:
        """MAX не любит пустые опциональные поля — кладём только заданные."""
        body: dict[str, Any] = {"url": url}
        if secret:
            body["secret"] = secret
        return await self._request("POST", "/subscriptions", json=body)

    async def delete_webhook(self, url: str) -> dict:
        return await self._request("DELETE", "/subscriptions", params={"url": url})

    async def get_updates(
        self,
        *,
        marker: int | None = None,
        limit: int = 50,
        timeout: int = DEFAULT_LONG_POLL_TIMEOUT,
        types: list[str] | None = None,
    ) -> dict:
        """`marker` передаём в следующий вызов, чтобы получать только новые события."""
        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if marker is not None:
            params["marker"] = marker
        if types:
            params["types"] = ",".join(types)
        # HTTP-таймаут должен быть строго больше серверного, иначе httpx
        # оборвёт соединение раньше, чем сервер вернёт ответ.
        return await self._request(
            "GET", "/updates", params=params, timeout=timeout + 10
        )

    async def send_message(
        self,
        text: str,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        """Ровно один из (`user_id`, `chat_id`) должен быть указан."""
        if (user_id is None) == (chat_id is None):
            raise ValueError("Specify exactly one of user_id or chat_id")
        params: dict[str, int] = (
            {"user_id": user_id} if user_id is not None else {"chat_id": chat_id}  # type: ignore[dict-item]
        )
        body: dict[str, Any] = {"text": text}
        if attachments:
            body["attachments"] = attachments
        return await self._request("POST", "/messages", params=params, json=body)

    async def send_photo_url(
        self,
        photo_url: str,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        caption: str | None = None,
    ) -> dict:
        """Картинка по публичному URL. Для локального файла — `send_local_photo`."""
        if (user_id is None) == (chat_id is None):
            raise ValueError("Specify exactly one of user_id or chat_id")
        params: dict[str, int] = (
            {"user_id": user_id} if user_id is not None else {"chat_id": chat_id}  # type: ignore[dict-item]
        )
        body: dict[str, Any] = {
            "attachments": [{"type": "image", "payload": {"url": photo_url}}],
        }
        if caption:
            body["text"] = caption
        return await self._request("POST", "/messages", params=params, json=body)

    async def send_local_photo(
        self,
        file_path: str,
        *,
        user_id: int | None = None,
        chat_id: int | None = None,
        caption: str | None = None,
    ) -> dict:
        """Трёхшаговый upload по docs MAX:
          1) `POST /uploads?type=image` → upload-URL;
          2) `POST <upload-URL>` multipart/form-data полем `data` → метаданные;
          3) `POST /messages` с image attachment'ом.

        Толерантный путь: формат ответа /uploads и attachment-payload менялся
        три раза за год — поэтому JSON-as-string парсим повторно и пробуем
        все известные варианты payload (см. `_photo_payload_candidates`).
        """
        if (user_id is None) == (chat_id is None):
            raise ValueError("Specify exactly one of user_id or chat_id")

        # MAX иногда возвращает /uploads как JSON-as-string (double encoding).
        upload_meta = await self._request("POST", "/uploads", params={"type": "image"})
        if isinstance(upload_meta, str):
            import json as _json
            try:
                upload_meta = _json.loads(upload_meta)
            except ValueError:
                pass
        if not isinstance(upload_meta, dict):
            raise MaxApiError(0, f"Bad /uploads response (not dict): {upload_meta!r}")
        upload_url = upload_meta.get("url")
        if not upload_url:
            raise MaxApiError(0, f"Bad /uploads response: {upload_meta!r}")

        # multipart с полем "data" — формат свежей версии API; raw content,
        # работавший раньше, в 2025 отвалился.
        from pathlib import Path as _Path
        fname = _Path(file_path).name
        with open(file_path, "rb") as f:
            data = f.read()
        async with httpx.AsyncClient(timeout=30.0) as up:
            up_resp = await up.post(
                upload_url,
                files={"data": (fname, data, "image/png")},
            )
            up_resp.raise_for_status()
            try:
                up_body = up_resp.json()
            except ValueError:
                up_body = {}

        # Та же история с double encoding.
        if isinstance(up_body, str):
            import json as _json
            try:
                up_body = _json.loads(up_body)
            except ValueError:
                up_body = {}

        logger.info("Upload response from MAX: meta=%s body=%s", upload_meta, up_body)

        params: dict[str, int] = (
            {"user_id": user_id} if user_id is not None else {"chat_id": chat_id}  # type: ignore[dict-item]
        )

        candidates = _photo_payload_candidates(up_body, upload_meta)
        if not candidates:
            raise MaxApiError(0, f"No usable photo identifier in upload response: {up_body!r}")

        last_error: MaxApiError | None = None
        for payload in candidates:
            body: dict[str, Any] = {
                "attachments": [{"type": "image", "payload": payload}],
            }
            if caption:
                body["text"] = caption
            try:
                return await self._request("POST", "/messages", params=params, json=body)
            except MaxApiError as exc:
                # 4xx — формат не подошёл, пробуем следующий. 5xx — реальная
                # серверная проблема, пробрасываем без перебора.
                if 400 <= exc.status_code < 500:
                    logger.info(
                        "Photo payload %s отклонён МАКС'ом (%s) — пробуем следующий",
                        payload, exc.status_code,
                    )
                    last_error = exc
                    continue
                raise

        raise last_error or MaxApiError(0, "All photo payload variants rejected")

    async def edit_message(
        self,
        message_id: str,
        *,
        text: str | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        """Используется при навигации внутри одного «диалога», чтобы не плодить сообщения."""
        params = {"message_id": message_id}
        body: dict[str, Any] = {}
        if text is not None:
            body["text"] = text
        if attachments is not None:
            body["attachments"] = attachments
        return await self._request("PUT", "/messages", params=params, json=body)

    async def answer_callback(
        self,
        callback_id: str,
        *,
        text: str | None = None,
        notification: bool = False,
    ) -> dict:
        """ACK на callback от кнопки. MAX требует подтверждения, иначе показывает диалог ввода.

        MAX API: POST /answers?callback_id=... — тело опционально (message, notification).
        """
        params = {"callback_id": callback_id}
        body: dict[str, Any] = {}
        if text is not None:
            body["message"] = {"text": text}
        if notification:
            body["notification"] = text or ""
        return await self._request(
            "POST",
            "/answers",
            params=params,
            json=body if body else None,
        )


def _photo_payload_candidates(upload_body: Any, upload_meta: dict) -> list[dict]:
    """Известные форматы attachment-payload, в порядке убывания вероятности.

    MAX менял формат несколько раз — `{"token": ...}`, `{"photo_id": ...}`,
    `{"photos": {...}}`, прямой url. `send_local_photo` перебирает варианты.

    `upload_body` намеренно `Any`: реальный ответ /uploads может оказаться не dict
    (список, строка, None) — guard ниже превращает любой мусор в `{}`.
    """
    if not isinstance(upload_body, dict):
        upload_body = {}
    candidates: list[dict] = []
    seen: set[str] = set()

    def _add(payload: dict) -> None:
        key = repr(sorted(payload.items()))
        if key not in seen and payload:
            seen.add(key)
            candidates.append(payload)

    for key in ("token", "photo_id", "fileId", "file_id"):
        for src in (upload_body, upload_meta):
            if src.get(key):
                _add({key: src[key]})

    # photos как словарь: {"<photo_id>": {"token": "..."}}
    for src in (upload_body, upload_meta):
        photos = src.get("photos")
        if isinstance(photos, dict) and photos:
            first_id = next(iter(photos.keys()))
            meta = photos[first_id] or {}
            if isinstance(meta, dict) and meta.get("token"):
                _add({"token": meta["token"]})
            _add({"photo_id": first_id})

    # photos как список
    for src in (upload_body, upload_meta):
        photos = src.get("photos")
        if isinstance(photos, list) and photos and isinstance(photos[0], dict):
            first = photos[0]
            for k in ("token", "photo_id", "id"):
                if first.get(k):
                    _add({k: first[k]})

    for src in (upload_body, upload_meta):
        url = src.get("url") or src.get("link") or src.get("photo_url")
        if url:
            _add({"url": url})

    return candidates


# Backward compatibility для старых тестов.
def _extract_photo_payload(upload_body: Any, upload_meta: dict) -> dict | None:
    if not isinstance(upload_body, dict):
        upload_body = {}

    for key in ("token", "photo_id", "fileId", "file_id"):
        if key in upload_body and upload_body[key]:
            return {key: upload_body[key]}
        if key in upload_meta and upload_meta[key]:
            return {key: upload_meta[key]}

    photos = upload_body.get("photos") or upload_meta.get("photos")
    if isinstance(photos, dict) and photos:
        first_id = next(iter(photos.keys()))
        meta = photos[first_id] or {}
        if isinstance(meta, dict) and meta.get("token"):
            return {"token": meta["token"]}
        return {"photo_id": first_id}

    url = upload_body.get("url") or upload_body.get("link")
    if url:
        return {"url": url}

    return None


# =============================================================================
# Хелперы парсинга event'ов MAX (древовидный JSON, поля плавают по версиям).
# =============================================================================

def get_update_type(update: dict) -> str | None:
    """В разных версиях API: либо корневое `update_type`, либо ключ верхнего уровня."""
    if isinstance(update, dict):
        if "update_type" in update:
            return update["update_type"]
        keys = [k for k in update if k not in {"timestamp", "marker"}]
        if len(keys) == 1:
            return keys[0]
    return None


def get_chat_id(update: dict) -> int | None:
    """Для прямого чата с ботом MAX часто возвращает `chat_id=0` — это не
    валидный id, отправлять надо по `user_id`. Поэтому 0 отфильтровываем.
    """
    for path in (
        ("chat_id",),
        ("message", "recipient", "chat_id"),
        ("message", "chat_id"),
        ("recipient", "chat_id"),
        ("callback", "message", "recipient", "chat_id"),
    ):
        value = _dig(update, path)
        if value is not None and value != 0:
            return value
    return None


def get_user_id(update: dict) -> int | None:
    """Порядок критичен: в `message_callback` поле `message.sender` — это БОТ
    (отправитель сообщения с кнопкой), реальный нажавший — в
    `callback.user.user_id`. Поэтому callback-пути идут первыми.
    """
    for path in (
        ("callback", "user", "user_id"),       # message_callback: кто нажал
        ("user", "user_id"),                    # bot_started
        ("message", "sender", "user_id"),       # message_created
        ("sender", "user_id"),
        ("user_id",),
    ):
        value = _dig(update, path)
        if value is not None:
            return value
    return None


def get_message_text(update: dict) -> str | None:
    for path in (
        ("message", "body", "text"),
        ("message", "text"),
        ("text",),
    ):
        value = _dig(update, path)
        if isinstance(value, str):
            return value
    return None


def get_callback_payload(update: dict) -> str | None:
    for path in (
        ("callback", "payload"),
        ("payload",),
    ):
        value = _dig(update, path)
        if isinstance(value, str):
            return value
    return None


def get_callback_id(update: dict) -> str | None:
    for path in (
        ("callback", "callback_id"),
        ("callback_id",),
    ):
        value = _dig(update, path)
        if isinstance(value, str) and value:
            return value
    return None


def get_bot_started_payload(update: dict) -> str | None:
    for path in (
        ("payload",),
        ("bot_started", "payload"),
    ):
        value = _dig(update, path)
        if isinstance(value, str):
            return value
    return None


def get_user_name(update: dict) -> str | None:
    for path in (
        ("user", "name"),
        ("user", "first_name"),
        ("sender", "name"),
        ("message", "sender", "name"),
        ("callback", "user", "name"),
    ):
        value = _dig(update, path)
        if isinstance(value, str):
            return value
    return None


def get_user_username(update: dict) -> str | None:
    for path in (
        ("user", "username"),
        ("sender", "username"),
        ("message", "sender", "username"),
        ("callback", "user", "username"),
    ):
        value = _dig(update, path)
        if isinstance(value, str):
            return value
    return None


def _dig(obj: Any, path: tuple[str, ...]) -> Any:
    current: Any = obj
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current
