"""Pending / paid Crypto Pay invoices (shared by bot and landing)."""

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
    return _data_dir() / "crypto_invoices.json"


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
    invoice_id: int,
    *,
    chat_id: int,
    plan_key: str,
    amount_kopecks: int,
    payload: str,
    kind: str = "subscription",
) -> dict[str, Any]:
    path = store_path()
    record = {
        "invoice_id": int(invoice_id),
        "chat_id": int(chat_id),
        "plan_key": plan_key,
        "amount_kopecks": int(amount_kopecks),
        "payload": payload,
        "kind": kind if kind in {"subscription", "service"} else "subscription",
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "paid_at": None,
        "fulfilled": False,
        "notify_sent": False,
    }
    with _FileLock(path):
        data = _load(path)
        data["invoices"][str(int(invoice_id))] = record
        _save(path, data)
    return record


def get_invoice(invoice_id: int) -> Optional[dict[str, Any]]:
    path = store_path()
    with _FileLock(path):
        data = _load(path)
        rec = data["invoices"].get(str(int(invoice_id)))
        return dict(rec) if isinstance(rec, dict) else None


def claim_paid(invoice_id: int) -> Optional[dict[str, Any]]:
    """One worker grants. already=True if fulfilled or another grant is in progress."""
    path = store_path()
    with _FileLock(path):
        data = _load(path)
        rec = data["invoices"].get(str(int(invoice_id)))
        if not isinstance(rec, dict):
            return None
        if rec.get("fulfilled"):
            out = dict(rec)
            out["already"] = True
            return out
        if rec.get("status") == "granting":
            started = float(rec.get("granting_at") or 0)
            if started and time.time() - started < 60:
                out = dict(rec)
                out["already"] = True
                return out
        rec["status"] = "granting"
        rec["granting_at"] = time.time()
        rec["paid_at"] = rec.get("paid_at") or time.strftime("%Y-%m-%d %H:%M:%S")
        data["invoices"][str(int(invoice_id))] = rec
        _save(path, data)
        out = dict(rec)
        out["already"] = False
        return out


def mark_fulfilled(invoice_id: int) -> None:
    path = store_path()
    with _FileLock(path):
        data = _load(path)
        rec = data["invoices"].get(str(int(invoice_id)))
        if isinstance(rec, dict):
            rec["fulfilled"] = True
            rec["status"] = "paid"
            data["invoices"][str(int(invoice_id))] = rec
            _save(path, data)


def mark_notify_sent(invoice_id: int) -> None:
    path = store_path()
    with _FileLock(path):
        data = _load(path)
        rec = data["invoices"].get(str(int(invoice_id)))
        if isinstance(rec, dict):
            rec["notify_sent"] = True
            data["invoices"][str(int(invoice_id))] = rec
            _save(path, data)
