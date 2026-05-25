"""Тесты `app/bot/client.py` — клиент к MAX Bot API через `httpx.MockTransport`."""
from __future__ import annotations

import json

import httpx
import pytest

from app.bot.client import (
    MaxApiError,
    MaxClient,
    _extract_photo_payload,
    get_bot_started_payload,
    get_callback_payload,
    get_chat_id,
    get_message_text,
    get_update_type,
    get_user_id,
    get_user_name,
    get_user_username,
)

# ---------------------------------------------------------------------------
# Хелперы — moc-транспорт + клиент, использующий его
# ---------------------------------------------------------------------------

def _make_client(handler) -> MaxClient:
    """MaxClient с MockTransport — иначе клиент пошёл бы в platform-api.max.ru."""
    client = MaxClient(token="test-token", base_url="http://test.max")
    transport = httpx.MockTransport(handler)
    client._client = httpx.AsyncClient(
        base_url=client._base_url,
        headers={"Authorization": "test-token"},
        transport=transport,
    )
    return client


@pytest.fixture
def mock_max():
    """Список захваченных запросов + очередь подготовленных ответов."""
    captured: list[httpx.Request] = []
    responses: list[httpx.Response] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        if responses:
            return responses.pop(0)
        return httpx.Response(200, json={"ok": True})

    return captured, responses, handler


# ---------------------------------------------------------------------------
# MaxClient — базовая работа
# ---------------------------------------------------------------------------

def test_client_requires_token():
    """Пустой токен — отказ на старте, а не в первом запросе."""
    with pytest.raises(ValueError, match="token"):
        MaxClient(token="")


@pytest.mark.asyncio
async def test_get_me_calls_correct_endpoint(mock_max):
    captured, responses, handler = mock_max
    responses.append(httpx.Response(200, json={"user_id": 42, "username": "test_bot"}))
    client = _make_client(handler)

    result = await client.get_me()

    assert result["user_id"] == 42
    assert captured[0].method == "GET"
    assert captured[0].url.path == "/me"
    assert captured[0].headers["authorization"] == "test-token"
    await client.close()


@pytest.mark.asyncio
async def test_send_message_to_user_id(mock_max):
    captured, responses, handler = mock_max
    client = _make_client(handler)

    await client.send_message(text="привет", user_id=111)

    req = captured[0]
    assert req.method == "POST"
    assert req.url.path == "/messages"
    assert req.url.params["user_id"] == "111"
    body = json.loads(req.content)
    assert body == {"text": "привет"}
    await client.close()


@pytest.mark.asyncio
async def test_send_message_with_attachments(mock_max):
    captured, _, handler = mock_max
    client = _make_client(handler)

    kb = {"type": "inline_keyboard", "payload": {"buttons": []}}
    await client.send_message(text="hi", user_id=1, attachments=[kb])

    body = json.loads(captured[0].content)
    assert body["attachments"] == [kb]
    await client.close()


@pytest.mark.asyncio
async def test_send_message_rejects_both_user_and_chat(mock_max):
    """Ровно один из user_id/chat_id: иначе адресат неоднозначен."""
    _, _, handler = mock_max
    client = _make_client(handler)
    with pytest.raises(ValueError, match="exactly one"):
        await client.send_message(text="x", user_id=1, chat_id=2)
    with pytest.raises(ValueError, match="exactly one"):
        await client.send_message(text="x")
    await client.close()


@pytest.mark.asyncio
async def test_get_updates_passes_marker_and_types(mock_max):
    captured, _, handler = mock_max
    client = _make_client(handler)

    await client.get_updates(marker=12345, types=["bot_started", "message_created"])

    req = captured[0]
    assert req.url.path == "/updates"
    assert req.url.params["marker"] == "12345"
    assert req.url.params["types"] == "bot_started,message_created"
    await client.close()


@pytest.mark.asyncio
async def test_set_webhook_with_secret(mock_max):
    captured, _, handler = mock_max
    client = _make_client(handler)

    await client.set_webhook(url="https://example.org/webhook", secret="s3cret")

    body = json.loads(captured[0].content)
    assert body == {"url": "https://example.org/webhook", "secret": "s3cret"}
    assert captured[0].method == "POST"
    await client.close()


@pytest.mark.asyncio
async def test_set_webhook_without_secret_omits_field(mock_max):
    captured, _, handler = mock_max
    client = _make_client(handler)
    await client.set_webhook(url="https://x.example", secret=None)
    body = json.loads(captured[0].content)
    assert "secret" not in body
    await client.close()


@pytest.mark.asyncio
async def test_delete_webhook(mock_max):
    captured, _, handler = mock_max
    client = _make_client(handler)
    await client.delete_webhook("https://x.example")
    assert captured[0].method == "DELETE"
    assert captured[0].url.params["url"] == "https://x.example"
    await client.close()


@pytest.mark.asyncio
async def test_4xx_raises_max_api_error(mock_max):
    """4xx поднимается как MaxApiError со статусом и телом."""
    captured, responses, handler = mock_max
    responses.append(httpx.Response(404, json={"error": "not found"}))
    client = _make_client(handler)

    with pytest.raises(MaxApiError) as exc:
        await client.get_me()
    assert exc.value.status_code == 404
    assert exc.value.body == {"error": "not found"}
    await client.close()


@pytest.mark.asyncio
async def test_edit_message_passes_message_id_in_params(mock_max):
    captured, _, handler = mock_max
    client = _make_client(handler)
    await client.edit_message("msg-1", text="новый текст")
    req = captured[0]
    assert req.method == "PUT"
    assert req.url.params["message_id"] == "msg-1"
    await client.close()


# ---------------------------------------------------------------------------
# Хелперы извлечения полей из update
# ---------------------------------------------------------------------------

class TestUpdateExtractors:
    def test_get_update_type_explicit_field(self):
        assert get_update_type({"update_type": "message_created"}) == "message_created"

    def test_get_update_type_single_root_key(self):
        # MAX иногда отдаёт `{"bot_started": {...}, "timestamp": ...}`.
        assert get_update_type({"bot_started": {}, "timestamp": 1}) == "bot_started"

    def test_get_update_type_none_for_unknown(self):
        assert get_update_type({}) is None
        assert get_update_type({"a": 1, "b": 2, "timestamp": 1}) is None

    def test_get_chat_id_skips_zero(self):
        # chat_id=0 от MAX для прямого чата — невалидно.
        assert get_chat_id({"chat_id": 0}) is None
        assert get_chat_id({"chat_id": 123}) == 123

    def test_get_chat_id_from_nested_paths(self):
        upd = {"message": {"recipient": {"chat_id": 77}}}
        assert get_chat_id(upd) == 77

    def test_get_user_id_various_paths(self):
        assert get_user_id({"user": {"user_id": 5}}) == 5
        assert get_user_id({"message": {"sender": {"user_id": 6}}}) == 6
        assert get_user_id({}) is None

    def test_get_user_name_prefers_name_field(self):
        # `user.name` имеет приоритет над `first_name`.
        upd = {"user": {"name": "Сергей"}}
        assert get_user_name(upd) == "Сергей"

    def test_get_user_name_falls_back_to_first_name(self):
        upd = {"user": {"first_name": "Иван"}}
        assert get_user_name(upd) == "Иван"

    def test_get_user_username(self):
        assert get_user_username({"user": {"username": "abc"}}) == "abc"
        assert get_user_username({}) is None

    def test_get_message_text(self):
        upd = {"message": {"body": {"text": "привет"}}}
        assert get_message_text(upd) == "привет"

    def test_get_callback_payload(self):
        upd = {"callback": {"payload": "event:42"}}
        assert get_callback_payload(upd) == "event:42"

    def test_get_bot_started_payload(self):
        upd = {"payload": "event_xxx"}
        assert get_bot_started_payload(upd) == "event_xxx"


# ---------------------------------------------------------------------------
# _extract_photo_payload — толерантный парсер ответа /uploads
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "upload_body, upload_meta, expected",
    [
        ({"token": "TOK"}, {}, {"token": "TOK"}),
        ({}, {"photo_id": "PID"}, {"photo_id": "PID"}),
        ({"fileId": "FID"}, {}, {"fileId": "FID"}),
        # photos: {"id123": {"token": "T"}}
        ({"photos": {"id123": {"token": "T"}}}, {}, {"token": "T"}),
        # photos с пустым meta → возвращаем photo_id
        ({"photos": {"id999": {}}}, {}, {"photo_id": "id999"}),
        # fallback на url
        ({"url": "https://cdn/img"}, {}, {"url": "https://cdn/img"}),
        # ничего нет
        ({}, {}, None),
    ],
    ids=[
        "token-body", "photo_id-meta", "fileId-body",
        "photos-with-token", "photos-without-token", "url-fallback", "empty",
    ],
)
def test_extract_photo_payload_known_formats(upload_body, upload_meta, expected):
    """Парсер должен переварить любой из известных форматов ответа MAX."""
    assert _extract_photo_payload(upload_body, upload_meta) == expected
