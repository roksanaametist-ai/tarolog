"""Thin MAX Bot API client (platform-api2.max.ru)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import certifi
import httpx

from . import config

_CERTS = Path(__file__).resolve().parent / "certs"
_RUSSIAN_CA = _CERTS / "russian_trusted.pem"


def _ca_bundle() -> str:
    """certifi plus the Russian Trusted CA used by platform-api2.max.ru."""
    if not _RUSSIAN_CA.is_file():
        return certifi.where()
    target = _CERTS / "ca_bundle.pem"
    merged = Path(certifi.where()).read_bytes() + b"\n" + _RUSSIAN_CA.read_bytes()
    if not target.is_file() or target.read_bytes() != merged:
        target.write_bytes(merged)
    return str(target)

logger = logging.getLogger(__name__)


class MaxClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.token = (token or config.MAX_BOT_TOKEN).strip()
        self.base_url = (base_url or config.MAX_API_BASE).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=45.0,
                verify=_ca_bundle(),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any = None,
    ) -> Any:
        if not self.token:
            raise RuntimeError("MAX_BOT_TOKEN не задан")
        client = await self._get_client()
        resp = await client.request(method, path, params=params, json=json)
        if resp.status_code >= 400:
            logger.error(
                "MAX API %s %s -> %s %s",
                method,
                path,
                resp.status_code,
                resp.text[:500],
            )
            resp.raise_for_status()
        if not resp.content:
            return {}
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    async def send_message(
        self,
        *,
        text: str,
        user_id: int | None = None,
        chat_id: int | None = None,
        attachments: list | None = None,
        format: str | None = "html",
        notify: bool = True,
    ) -> Any:
        if user_id is None and chat_id is None:
            raise ValueError("user_id или chat_id обязателен")
        params: dict[str, Any] = {}
        if user_id is not None:
            params["user_id"] = int(user_id)
        if chat_id is not None:
            params["chat_id"] = int(chat_id)
        body: dict[str, Any] = {"text": text[:4000], "notify": notify}
        if attachments is not None:
            body["attachments"] = attachments
        if format:
            body["format"] = format
        return await self.request("POST", "/messages", params=params, json=body)

    async def answer_callback(
        self,
        callback_id: str,
        *,
        notification: str = "",
    ) -> Any:
        if not callback_id:
            return {}
        body: dict[str, Any] = {}
        if notification:
            body["notification"] = notification
        return await self.request(
            "POST",
            "/answers",
            params={"callback_id": callback_id},
            json=body,
        )

    async def upload_media(self, path: str, kind: str = "image") -> Optional[str]:
        if not path or not os.path.isfile(path):
            return None
        meta = await self.request("POST", "/uploads", params={"type": kind})
        upload_url = meta.get("url") if isinstance(meta, dict) else None
        if not upload_url:
            return None
        async with httpx.AsyncClient(timeout=60.0) as uploader:
            with open(path, "rb") as handle:
                resp = await uploader.post(
                    upload_url,
                    files={"data": (os.path.basename(path), handle)},
                )
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, dict):
            return None
        if data.get("token"):
            return str(data["token"])
        photos = data.get("photos") or data.get("videos") or {}
        if isinstance(photos, dict):
            for item in photos.values():
                if isinstance(item, dict) and item.get("token"):
                    return str(item["token"])
        return None

    async def get_me(self) -> Any:
        return await self.request("GET", "/me")

    async def subscribe_webhook(
        self,
        url: str,
        *,
        secret: str = "",
        update_types: list[str] | None = None,
    ) -> Any:
        body: dict[str, Any] = {
            "url": url,
            "update_types": update_types
            or [
                "message_created",
                "message_callback",
                "bot_started",
            ],
        }
        if secret:
            body["secret"] = secret
        return await self.request("POST", "/subscriptions", json=body)

    async def list_subscriptions(self) -> Any:
        return await self.request("GET", "/subscriptions")


api = MaxClient()
