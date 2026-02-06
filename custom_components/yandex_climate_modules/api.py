from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import YANDEX_IOT_BASE


class YandexIoTApiError(Exception):
    """Raised for Yandex IoT API errors."""


class YandexIoTAuthError(YandexIoTApiError):
    """401 Unauthorized."""


class YandexIoTPermissionError(YandexIoTApiError):
    """403 Forbidden (missing scope / permission)."""

    """Raised for Yandex IoT API errors."""


@dataclass(frozen=True)
class YandexDevice:
    id: str
    name: str
    room: str | None
    properties: list[dict[str, Any]]


def _normalize_token(token: str) -> str:
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        token = token.split(None, 1)[1].strip()
    return token


class YandexIoTClient:
    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self._session = session
        self._token = _normalize_token(token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{YANDEX_IOT_BASE}{path}"
        async with self._session.get(
            url,
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            text = await resp.text()
            if resp.status == 401:
                raise YandexIoTAuthError(f"HTTP 401 Unauthorized: {text[:300]}")
            if resp.status == 403:
                raise YandexIoTPermissionError(f"HTTP 403 Forbidden: {text[:300]}")
            if resp.status >= 400:
                raise YandexIoTApiError(f"HTTP {resp.status}: {text[:300]}")
            try:
                return await resp.json()
            except Exception as e:  # noqa: BLE001
                raise YandexIoTApiError(f"Bad JSON: {e}. Body: {text[:300]}") from e

    async def get_user_info(self) -> dict[str, Any]:
        data = await self._get_json("/user/info")
        if data.get("status") != "ok":
            raise YandexIoTApiError(f"Unexpected response: {data}")
        return data

    async def validate_token(self) -> None:
        await self.get_user_info()

    async def list_device_ids(self) -> list[str]:
        """Return all device IDs visible to the user.

        NOTE: Smart Home REST API does not provide a public list-devices endpoint.
        Device IDs are obtained from /user/info.
        """
        data = await self.get_user_info()
        ids: list[str] = []
        # Newer payloads include a flat devices list
        for d in (data.get("devices") or []):
            did = d.get("id")
            if did:
                ids.append(did)
        # Some payloads include room -> devices mapping (ids)
        for r in (data.get("rooms") or []):
            for did in (r.get("devices") or []):
                if did:
                    ids.append(did)
        # unique, preserve order
        seen: set[str] = set()
        out: list[str] = []
        for did in ids:
            if did not in seen:
                seen.add(did)
                out.append(did)
        return out

    async def get_device(self, device_id: str) -> YandexDevice:
        data = await self._get_json(f"/devices/{device_id}")
        if data.get("status") != "ok":
            raise YandexIoTApiError(f"Unexpected response: {data}")
        return YandexDevice(
            id=data["id"],
            name=data.get("name") or device_id,
            room=data.get("room"),
            properties=data.get("properties") or [],
        )
