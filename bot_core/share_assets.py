from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .operational_store import OperationalStore


class ShareAssetStore:
    def __init__(
        self,
        operational_store: OperationalStore,
        legacy_path: str | Path,
        *,
        ttl_days: int = 7,
    ) -> None:
        self.operational_store = operational_store
        self.legacy_path = Path(legacy_path)
        self.ttl_days = max(1, int(ttl_days))
        self.data: dict[str, dict[str, Any]] = self._load()
        self.prune()

    def _load(self) -> dict[str, dict[str, Any]]:
        raw = self.operational_store.load_document(
            "share_assets",
            legacy_path=self.legacy_path,
            default={},
        )
        return (
            {str(key): value for key, value in raw.items() if isinstance(value, dict)}
            if isinstance(raw, dict)
            else {}
        )

    def _save(self) -> None:
        self.operational_store.save_document(
            "share_assets",
            self.data,
            legacy_path=self.legacy_path,
        )

    def create(
        self,
        *,
        owner_id: int,
        photo_file_id: str,
        body: str,
        deep_link: str,
        template: str,
    ) -> str:
        token = secrets.token_urlsafe(9)
        now = datetime.now(timezone.utc)
        self.data[token] = {
            "owner_id": int(owner_id),
            "photo_file_id": str(photo_file_id),
            "body": str(body)[:1024],
            "deep_link": str(deep_link)[:500],
            "template": str(template or "situation")[:32],
            "created_at": now.isoformat(timespec="seconds"),
            "expires_at": (now + timedelta(days=self.ttl_days)).isoformat(
                timespec="seconds"
            ),
        }
        self._save()
        return token

    def get(self, token: str, *, owner_id: int | None = None) -> Optional[dict[str, Any]]:
        asset = self.data.get(str(token))
        if not asset:
            return None
        if owner_id is not None and int(asset.get("owner_id") or 0) != int(owner_id):
            return None
        try:
            expires_at = datetime.fromisoformat(str(asset.get("expires_at") or ""))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                self.data.pop(str(token), None)
                self._save()
                return None
        except ValueError:
            return None
        return dict(asset)

    def prune(self) -> int:
        now = datetime.now(timezone.utc)
        removed = 0
        for token, asset in list(self.data.items()):
            try:
                expires_at = datetime.fromisoformat(str(asset.get("expires_at") or ""))
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
            except ValueError:
                expires_at = now - timedelta(seconds=1)
            if expires_at <= now:
                self.data.pop(token, None)
                removed += 1
        if removed:
            self._save()
        return removed
