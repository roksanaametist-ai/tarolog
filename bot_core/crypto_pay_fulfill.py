"""Grant a month of access after a paid Crypto Pay invoice. No auto-renew."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

import shared_wallet

from bot_core import crypto_pay, crypto_pay_store
from bot_core.crypto_services import SERVICE_PRODUCTS
from bot_core.robokassa_fulfill import (
    PLAN_DAYS,
    PLAN_LABELS,
    _bump_payment_stats,
    _mark_nurture_done,
    _patch_user_data,
    _stack_subscription_end,
    _user_data_path,
    notify_telegram,
)

logger = logging.getLogger(__name__)


def _amount_matches(remote: dict[str, Any], amount_kopecks: int) -> bool:
    if str(remote.get("fiat") or "").upper() not in {"", "RUB"}:
        return False
    if str(remote.get("currency_type") or "fiat") != "fiat":
        return False
    raw = str(remote.get("amount") or "").replace(",", ".").strip()
    try:
        got = int(round(float(raw) * 100))
    except ValueError:
        return False
    return got == int(amount_kopecks)


def _admin_ids() -> list[int]:
    ids: set[int] = set()
    for key in ("ADMIN_IDS", "BOT_ADMIN_IDS", "CONSULTATION_NOTIFY_IDS"):
        for part in (os.getenv(key) or "").split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
    if not ids:
        ids.add(491482483)
    return sorted(ids)


def _user_seed(chat_id: int) -> Optional[dict[str, Any]]:
    try:
        with open(_user_data_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    rec = data.get(str(int(chat_id))) if isinstance(data, dict) else None
    return rec if isinstance(rec, dict) else None


def _fulfill_service(
    *,
    invoice_id: int,
    chat_id: int,
    plan_key: str,
    amount_kopecks: int,
    claimed: dict[str, Any],
) -> dict[str, Any]:
    """Personal reading or consultation. Does not grant bot access."""
    product = SERVICE_PRODUCTS.get(plan_key) or {}
    label = str(product.get("label") or "Заказ")
    buyer_text = str(product.get("buyer") or f"Оплата прошла ✨\n{label}")
    try:
        _bump_payment_stats(amount_kopecks, plan_key)
    except OSError:
        pass
    _mark_nurture_done(chat_id)
    crypto_pay_store.mark_fulfilled(invoice_id)

    seed = _user_seed(chat_id) or {}
    username = str(seed.get("username") or "").lstrip("@")
    who = f"@{username}" if username else "без username"
    admin_text = (
        f"Оплачено криптой: {label}\n"
        f"Клиент: {who}\n"
        f"Telegram id: {chat_id}\n"
        f"Счёт Crypto Pay: {invoice_id}"
    )

    notified = False
    if not claimed.get("notify_sent"):
        notified = notify_telegram(chat_id, buyer_text)
        for admin_id in _admin_ids():
            if admin_id == chat_id:
                continue
            notify_telegram(admin_id, admin_text)
        if notified:
            crypto_pay_store.mark_notify_sent(invoice_id)

    return {
        "ok": True,
        "already": False,
        "chat_id": chat_id,
        "plan_key": plan_key,
        "kind": "service",
        "notified": notified,
    }


def fulfill_invoice(remote: dict[str, Any]) -> dict[str, Any]:
    """Idempotent grant. Does not enable card auto-renew or replace the card provider."""
    if str(remote.get("status") or "") != "paid":
        return {"ok": False, "error": "not paid"}
    try:
        invoice_id = int(remote.get("invoice_id") or 0)
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad invoice"}
    if not invoice_id:
        return {"ok": False, "error": "no invoice"}

    existing = crypto_pay_store.get_invoice(invoice_id)
    if not existing:
        return {"ok": False, "error": "unknown invoice", "invoice_id": invoice_id}
    if not _amount_matches(remote, int(existing.get("amount_kopecks") or 0)):
        logger.warning("crypto amount mismatch invoice_id=%s", invoice_id)
        return {"ok": False, "error": "amount mismatch", "invoice_id": invoice_id}

    claimed = crypto_pay_store.claim_paid(invoice_id)
    if not claimed:
        return {"ok": False, "error": "claim failed", "invoice_id": invoice_id}
    if claimed.get("already"):
        return {
            "ok": True,
            "already": True,
            "chat_id": claimed.get("chat_id"),
            "plan_key": claimed.get("plan_key"),
            "notified": bool(claimed.get("notify_sent")),
        }

    chat_id = int(claimed["chat_id"])
    plan_key = str(claimed.get("plan_key") or "")
    amount_kopecks = int(claimed.get("amount_kopecks") or 0)
    if str(claimed.get("kind") or "subscription") == "service" or plan_key in SERVICE_PRODUCTS:
        return _fulfill_service(
            invoice_id=invoice_id,
            chat_id=chat_id,
            plan_key=plan_key,
            amount_kopecks=amount_kopecks,
            claimed=claimed,
        )

    days = int(PLAN_DAYS.get(plan_key, 31))

    seed = None
    try:
        with open(_user_data_path(), "r", encoding="utf-8") as handle:
            ud = json.load(handle)
        if isinstance(ud, dict) and isinstance(ud.get(str(chat_id)), dict):
            seed = ud[str(chat_id)]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        seed = None

    current = shared_wallet.view("tg", chat_id, seed)
    new_end = _stack_subscription_end(current.get("subscription_end"), days)
    changes: dict[str, Any] = {
        "subscription_end": new_end,
        "subscription_plan_key": plan_key,
        "subscription_price": amount_kopecks,
        "last_crypto_invoice_id": invoice_id,
    }
    if not current.get("payment_provider"):
        changes["payment_provider"] = "crypto"

    wallet = shared_wallet.update("tg", chat_id, seed, changes)
    _patch_user_data(chat_id, {k: wallet.get(k) for k in changes})
    try:
        _bump_payment_stats(amount_kopecks, plan_key)
    except OSError:
        pass
    _mark_nurture_done(chat_id)
    crypto_pay_store.mark_fulfilled(invoice_id)

    label = PLAN_LABELS.get(plan_key, "Подписка")
    end_human = datetime.strptime(new_end, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
    text = (
        f"Оплата криптой прошла ✨\n"
        f"Тариф: {label}\n"
        f"Безлимит до {end_human}.\n"
        f"Это разовая оплата: следующий месяц сам не спишется."
    )
    if current.get("auto_renew"):
        text += (
            "\nАвтопродление картой по-прежнему включено. "
            "Отменить — в меню «💳 Оформить подписку»."
        )

    notified = False
    if not claimed.get("notify_sent"):
        notified = notify_telegram(chat_id, text)
        if notified:
            crypto_pay_store.mark_notify_sent(invoice_id)

    return {
        "ok": True,
        "already": False,
        "chat_id": chat_id,
        "plan_key": plan_key,
        "subscription_end": new_end,
        "notified": notified,
    }


def fulfill_if_paid(invoice_id: int) -> dict[str, Any]:
    remote = crypto_pay.get_invoice(int(invoice_id))
    if not remote:
        return {"ok": False, "error": "not found", "invoice_id": invoice_id}
    if str(remote.get("status") or "") != "paid":
        return {"ok": False, "error": "not paid", "invoice_id": invoice_id, "status": remote.get("status")}
    return fulfill_invoice(remote)
