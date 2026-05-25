"""HTTP-клиент SUT поверх httpx с инжектом JWT / X-API-Key."""
from __future__ import annotations

from typing import Any

import httpx

from config.urls import path_login
from core.exceptions import ApiError
from core.logger import get_logger, mask_secrets

_log = get_logger("qa.api")


class ApiClient:
    # Хранит JWT и/или X-API-Key. Не валидирует схему ответа — это задача Steps/тестов.

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        token: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            follow_redirects=False,
        )

    @property
    def token(self) -> str | None:
        return self._token

    @property
    def base_url(self) -> str:
        return self._base_url

    def authenticate(self, email: str, password: str) -> str:
        # POST /api/v1/auth/login. Сохраняет access_token в self._token.
        resp = self._client.post(path_login(), json={"email": email, "password": password})
        if resp.status_code != 200:
            raise ApiError(resp, f"login failed for {email}: {resp.status_code}")
        token = resp.json()["access_token"]
        self._token = token
        return token

    # Возвращаем новые экземпляры — копию с правкой одного поля.
    def with_token(self, token: str) -> ApiClient:
        return ApiClient(
            base_url=self._base_url,
            timeout=self._client.timeout.read or 15.0,
            token=token,
            api_key=self._api_key,
        )

    def with_api_key(self, api_key: str) -> ApiClient:
        return ApiClient(
            base_url=self._base_url,
            timeout=self._client.timeout.read or 15.0,
            token=self._token,
            api_key=api_key,
        )

    def _merge_headers(self, extra: dict[str, str] | None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        if extra:
            # Внешний заголовок переопределяет (важно для negative-тестов без auth).
            headers.update(extra)
            # "X-API-Key": None — намеренный сигнал "не отправлять ключ вообще".
            for key, value in list(extra.items()):
                if value is None:
                    headers.pop(key, None)
        return headers

    def _log_request(self, method: str, path: str, headers: dict[str, str], **kw: Any) -> None:
        _log.debug("→ %s %s headers=%s body=%s", method, path, mask_secrets(headers),
                   mask_secrets(kw.get("json")))

    def _log_response(self, method: str, path: str, resp: httpx.Response) -> None:
        _log.info("← %s %s %d (%.0fms)", method, path, resp.status_code,
                  resp.elapsed.total_seconds() * 1000)

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        merged = self._merge_headers(headers)
        self._log_request("GET", path, merged, params=params)
        resp = self._client.get(path, params=params, headers=merged)
        self._log_response("GET", path, resp)
        return resp

    def post_json(
        self,
        path: str,
        *,
        json: dict[str, Any] | list[Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        merged = self._merge_headers(headers)
        self._log_request("POST", path, merged, json=json)
        resp = self._client.post(path, json=json, headers=merged)
        self._log_response("POST", path, resp)
        return resp

    def patch_json(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        merged = self._merge_headers(headers)
        self._log_request("PATCH", path, merged, json=json)
        resp = self._client.patch(path, json=json, headers=merged)
        self._log_response("PATCH", path, resp)
        return resp

    def put_json(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        merged = self._merge_headers(headers)
        self._log_request("PUT", path, merged, json=json)
        resp = self._client.put(path, json=json, headers=merged)
        self._log_response("PUT", path, resp)
        return resp

    def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        merged = self._merge_headers(headers)
        self._log_request("DELETE", path, merged)
        resp = self._client.delete(path, headers=merged)
        self._log_response("DELETE", path, resp)
        return resp

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        # Универсальный метод нужен для нестандартных кейсов (например, POST /healthz → 405).
        merged = self._merge_headers(headers)
        self._log_request(method, path, merged, json=json, params=params)
        resp = self._client.request(method, path, json=json, params=params, headers=merged)
        self._log_response(method, path, resp)
        return resp

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
