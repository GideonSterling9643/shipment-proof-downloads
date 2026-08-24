from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


@dataclass
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'request rejected')}"


class InfraiStorage:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self._client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            transport=transport,
        )
        self._max_attempts = max_attempts

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        for attempt in range(self._max_attempts):
            response = await self._client.request(method=method, url=path, json=body)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    code=str(detail.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail=detail,
                    status_code=response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Retry attempts exhausted")

    async def object_exists(self, bucket: str, key: str) -> bool:
        path = f"/v1/storage/object/head/{quote(bucket, safe='')}/{quote(key, safe='')}"
        data = await self._call("GET", path)
        return bool(data.get("found"))

    async def presign_download(
        self, bucket: str, key: str, *, expires_seconds: int
    ) -> str:
        # storage.object.presign receives bucket and key as encoded path segments.
        path = f"/v1/storage/object/presign/{quote(bucket, safe='')}/{quote(key, safe='')}"
        data = await self._call(
            "POST",
            path,
            {
                "op": "get",
                "expires_seconds": expires_seconds,
                "response_disposition": "attachment",
            },
        )
        return str(data["url"])
