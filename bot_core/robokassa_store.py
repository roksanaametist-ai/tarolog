"""Pending / paid Robokassa invoices (shared by bot and landing)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional


def _data_dir() -> Path:
    for key in ("BOT_DATA_DIR", "LANDING_DATA_DIR"):
        raw = (os.getenv(key) or "").strip()
        if not raw:
            continue
        configured = Path(raw)
        if configured.exists():
            return configured.resolve()
    return Path(__file__).resolve().parent.parent


def store_path() -> Path:
    return _data_dir() / "robokassa_invoices.json"


class _FileLock:
    def __init__(self, path: Path) -> None:
        self.lock_path = path.with_suffix(path.suffix + ".lock")

    def __enter__(self) -> "_FileLock":
        for _ in range(80):
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.lock_path.stat().st_mtime > 30:
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                time.sleep(0.05)
        raise TimeoutError(f"lock {self.lock_path}")

    def __exit__(self, *_) -> None:
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _load(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    raw.setdefault("invoices", {})
    return raw


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def put_pending(
    inv_id: int,
    *,
    chat_id: int,
    plan_key: str,
    amount_kopecks: int,
    kind: str = "parent",
    parent_inv_id: Optional[int] = None,
) -> dict[str, Any]:
    path = store_path()
    record = {
        "inv_id": int(inv_id),
        "chat_id": int(chat_id),
        "plan_key": plan_key,
        "amount_kopecks": int(amount_kopecks),
        "kind": kind,
        "parent_inv_id": int(parent_inv_id) if parent_inv_id else None,
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "paid_at": None,
        "notify_sent": False,
    }
    with _FileLock(path):
        data = _load(path)
        data["invoices"][str(int(inv_id))] = record
        _save(path, data)
    return record


def get_invoice(inv_id: int) -> Optional[dict[str, Any]]:
    path = store_path()
    with _FileLock(path):
        data = _load(path)
        rec = data["invoices"].get(str(int(inv_id)))
        return dict(rec) if isinstance(rec, dict) else None


def mark_paid(inv_id: int) -> Optional[dict[str, Any]]:
    path = store_path()
    with _FileLock(path):
        data = _load(path)
        rec = data["invoices"].get(str(int(inv_id)))
        if not isinstance(rec, dict):
            return None
        if rec.get("status") == "paid":
            return dict(rec)
        rec["status"] = "paid"
        rec["paid_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        data["invoices"][str(int(inv_id))] = rec
        _save(path, data)
        return dict(rec)


def mark_notify_sent(inv_id: int) -> None:
    path = store_path()
    with _FileLock(path):
        data = _load(path)
        rec = data["invoices"].get(str(int(inv_id)))
        if isinstance(rec, dict):
            rec["notify_sent"] = True
            data["invoices"][str(int(inv_id))] = rec
            _save(path, data)
