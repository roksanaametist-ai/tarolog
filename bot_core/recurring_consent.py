"""Журнал согласий на автоматические списания (только дописывается).

Одна строка JSON на событие: согласие при оплате, отмена автопродления.
Требование Robokassa: хранить историю согласий (дата, время, тариф, сумма, редакция оферты).
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

CONSENT_TEXT = "Я согласен на автоматические списания согласно условиям оферты"

_lock = threading.Lock()


def _data_dir() -> Path:
    for key in ("BOT_DATA_DIR", "LANDING_DATA_DIR"):
        raw = (os.getenv(key) or "").strip()
        if raw and Path(raw).exists():
            return Path(raw).resolve()
    return Path(__file__).resolve().parent.parent


def log_path() -> Path:
    raw = (os.getenv("RECURRING_CONSENT_LOG") or "").strip()
    return Path(raw) if raw else _data_dir() / "recurring_consents.jsonl"


def offer_edition() -> str:
    return (os.getenv("OFFER_EDITION") or "11.11.2026").strip()


def offer_url() -> str:
    return (
        os.getenv("OFFER_SUBSCRIPTION_URL") or "https://followthefrensy.ru/oferta#subscription"
    ).strip()


def record(
    *,
    chat_id: int,
    action: str,
    plan_key: Optional[str] = None,
    amount_kopecks: Optional[int] = None,
    inv_id: Optional[int] = None,
    source: str = "telegram",
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """action: agree (поставил галочку и перешёл к оплате) / cancel (отключил автопродление)."""
    entry: dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ts_unix": int(time.time()),
        "chat_id": int(chat_id),
        "action": action,
        "plan_key": plan_key,
        "amount_rub": (int(amount_kopecks) / 100.0) if amount_kopecks is not None else None,
        "inv_id": int(inv_id) if inv_id is not None else None,
        "offer_edition": offer_edition(),
        "offer_url": offer_url(),
        "source": source,
    }
    if action == "agree":
        entry["consent_text"] = CONSENT_TEXT
    if extra:
        entry.update(extra)
    path = log_path()
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
    return entry


def history(chat_id: Optional[int] = None) -> list[dict[str, Any]]:
    path = log_path()
    out: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chat_id is None or item.get("chat_id") == int(chat_id):
                    out.append(item)
    except FileNotFoundError:
        pass
    return out
