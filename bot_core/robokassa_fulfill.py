"""Grant subscription after Robokassa ResultURL (used by landing Flask)."""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import shared_wallet

from bot_core import compat_paid, robokassa_store

logger = logging.getLogger(__name__)

PLAN_DAYS = {
    "sub_m_111": 31,
    "sub_m_555": 31,
    "sub_m_999": 31,
    # legacy keys (if old pending somehow)
    "sub_7d_399": 31,
    "sub_14d_499": 93,
    "sub_30d_699": 365,
}

PLAN_LABELS = {
    "sub_m_111": "Месяц безлимит — 111 ₽",
    "sub_m_555": "Месяц безлимит — 555 ₽",
    "sub_m_999": "Месяц безлимит — 999 ₽",
}


def _data_dir() -> Path:
    for key in ("BOT_DATA_DIR", "LANDING_DATA_DIR"):
        raw = (os.getenv(key) or "").strip()
        if not raw:
            continue
        configured = Path(raw)
        if configured.exists():
            return configured.resolve()
    return Path(__file__).resolve().parent.parent


def _user_data_path() -> Path:
    return _data_dir() / "user_data.json"


def _payment_stats_path() -> Path:
    return _data_dir() / "payment_data.json"


def _nurture_path() -> Path:
    return _data_dir() / "payment_nurture.json"


def _stack_subscription_end(current: Optional[str], days: int) -> str:
    now = datetime.now()
    base = now
    if current:
        try:
            end = datetime.strptime(current, "%Y-%m-%d %H:%M:%S")
            if end > now:
                base = end
        except ValueError:
            pass
    return (base + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")



def _patch_users_store(chat_id: int, changes: dict[str, Any]) -> None:
    """Write grant into SQLite operational store so the live bot sees it."""
    try:
        from bot_core.operational_store import OperationalStore
    except Exception as exc:
        logger.warning("operational_store import failed: %s", exc)
        _patch_user_data(chat_id, changes)
        return

    store = OperationalStore(_data_dir() / "bot_state.sqlite3")
    key = str(int(chat_id))

    def mutator(disk: Any) -> Any:
        data = disk if isinstance(disk, dict) else {}
        rec = data.get(key)
        if not isinstance(rec, dict):
            rec = {"questions": 5, "username": None}
            data[key] = rec
        for field, value in changes.items():
            rec[field] = value
        data[key] = rec
        return data

    try:
        store.update_document(
            "users",
            mutator,
            legacy_path=_user_data_path(),
            source="robokassa_fulfill",
            default={},
        )
    except Exception as exc:
        logger.warning("store update failed, fallback json: %s", exc)
        _patch_user_data(chat_id, changes)


def _patch_user_data(chat_id: int, changes: dict[str, Any]) -> None:
    path = _user_data_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    key = str(int(chat_id))
    rec = data.get(key)
    if not isinstance(rec, dict):
        rec = {"questions": 5, "username": None}
        data[key] = rec
    for field, value in changes.items():
        rec[field] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _bump_payment_stats(amount_kopecks: int, plan_key: str) -> None:
    path = _payment_stats_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data["total_rub"] = float(data.get("total_rub") or 0) + amount_kopecks / 100.0
    data["count"] = int(data.get("count") or 0) + 1
    by_plan = data.setdefault("by_plan", {})
    if isinstance(by_plan, dict):
        by_plan[plan_key] = int(by_plan.get(plan_key) or 0) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _mark_nurture_done(chat_id: int) -> None:
    path = _nurture_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    rec = data.get(str(int(chat_id)))
    if isinstance(rec, dict):
        rec["completed"] = True
        rec["stage"] = "done"
        data[str(int(chat_id))] = rec
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)


def notify_telegram(chat_id: int, text: str) -> bool:
    token = (os.getenv("TELEGRAM_TOKEN") or "").strip()
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode(
        {"chat_id": int(chat_id), "text": text}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:
        logger.warning("telegram notify failed chat_id=%s: %s", chat_id, exc)
        return False


GRANTED_KEEP = 50


def _later_end(*values: Optional[str]) -> Optional[str]:
    best: Optional[datetime] = None
    best_raw: Optional[str] = None
    for raw in values:
        if not raw:
            continue
        try:
            dt = datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if best is None or dt > best:
            best, best_raw = dt, str(raw)
    return best_raw


def apply_grant(
    rec: dict[str, Any],
    *,
    inv_id: int,
    invoice: dict[str, Any],
    wallet_end: Optional[str] = None,
    now: Optional[datetime] = None,
) -> tuple[bool, dict[str, Any]]:
    """Чистая логика выдачи для одной записи пользователя (внутри атомарной записи sqlite).

    Возвращает (granted_now, changes). granted_now=False — этот счёт уже выдан (P-3).
    """
    granted: list[int] = []
    for x in rec.get("granted_inv_ids") or []:
        try:
            granted.append(int(x))
        except (TypeError, ValueError):
            continue
    if int(inv_id) in granted:
        return False, {}

    plan_key = str(invoice.get("plan_key") or "")
    amount_kopecks = int(invoice.get("amount_kopecks") or 0)
    days = int(PLAN_DAYS.get(plan_key, 31))
    kind = str(invoice.get("kind") or "parent")

    # P-1: база — запись sqlite (или более поздняя дата из shared_wallet)
    now = now or datetime.now()
    start = now
    base = _later_end(rec.get("subscription_end"), wallet_end)
    if base:
        dt = datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
        if dt > now:
            start = dt
    new_end = (start + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    changes: dict[str, Any] = {
        "subscription_end": new_end,
        "subscription_plan_key": plan_key,
        "subscription_price": amount_kopecks,
        "last_robokassa_inv_id": int(inv_id),
        "payment_provider": "robokassa",
        "renew_fail_count": 0,
        "next_renew_at": None,
        "renew_pending_inv_id": None,
        "renew_pending_since": None,
        "renew_not_before": None,
        "granted_inv_ids": (granted + [int(inv_id)])[-GRANTED_KEEP:],
    }
    if kind == "parent":
        consent = invoice.get("consent") if isinstance(invoice.get("consent"), dict) else None
        recurring = bool(invoice.get("recurring")) and consent is not None
        # автопродление — только при согласии (галочка) и рекуррентном счёте
        changes["auto_renew"] = recurring
        changes["auto_renew_consent"] = consent if recurring else None
        changes["renew_reminded_for_end"] = None
        changes["renew_charged_for_end"] = None
        if recurring:
            changes["robokassa_prev_invoice_id"] = int(inv_id)
    else:
        # дочернее списание: auto_renew заново не включаем (вдруг отменили, пока шёл платёж)
        if not rec.get("robokassa_prev_invoice_id") and invoice.get("parent_inv_id"):
            changes["robokassa_prev_invoice_id"] = int(invoice["parent_inv_id"])
    return True, changes


def _grant_in_store(
    chat_id: int, inv_id: int, invoice: dict[str, Any], wallet_end: Optional[str]
) -> tuple[bool, dict[str, Any]]:
    """Атомарно (sqlite BEGIN IMMEDIATE) применяет выдачу. Возвращает (granted_now, запись)."""
    from bot_core.operational_store import OperationalStore

    store = OperationalStore(_data_dir() / "bot_state.sqlite3")
    key = str(int(chat_id))
    result: dict[str, Any] = {"granted": False, "rec": {}}

    def mutator(disk: Any) -> Any:
        data = disk if isinstance(disk, dict) else {}
        rec = data.get(key)
        if not isinstance(rec, dict):
            rec = {"questions": 5, "username": None}
        granted_now, changes = apply_grant(rec, inv_id=inv_id, invoice=invoice, wallet_end=wallet_end)
        rec.update(changes)
        data[key] = rec
        result["granted"] = granted_now
        result["rec"] = dict(rec)
        return data

    store.update_document(
        "users",
        mutator,
        legacy_path=_user_data_path(),
        source="robokassa_fulfill",
        default={},
    )
    return bool(result["granted"]), result["rec"]


def _mark_fulfilled(inv_id: int) -> None:
    path = robokassa_store.store_path()
    with robokassa_store._FileLock(path):
        data = robokassa_store._load(path)
        rec = data["invoices"].get(str(int(inv_id)))
        if isinstance(rec, dict):
            rec["fulfilled"] = True
            data["invoices"][str(int(inv_id))] = rec
            robokassa_store._save(path, data)


def _track_payment_succeeded(
    inv_id: int,
    chat_id: int,
    plan_key: str,
    amount_kopecks: int,
    kind: str,
    seed: Optional[dict],
    *,
    occurred_at: Any = None,
) -> bool:
    """Write payment_succeeded to analytics.sqlite3 (admin dashboard). Never raises."""
    try:
        from analytics.store import AnalyticsStore

        u = seed if isinstance(seed, dict) else {}
        store = AnalyticsStore(_data_dir() / "analytics.sqlite3")
        return store.track(
            "payment_succeeded",
            user_id=int(chat_id),
            properties={
                "payment_id": f"robokassa:{inv_id}",
                "provider": "robokassa",
                "plan": plan_key or "unknown",
                "amount_kopecks": int(amount_kopecks),
                "recurring": kind == "child",
                "source": str(u.get("acquisition_source") or "unknown"),
                "partner": str(u.get("partner_code") or ""),
                "campaign": str(u.get("campaign_code") or ""),
            },
            occurred_at=occurred_at,
            dedupe_key=f"payment-success:robokassa:{inv_id}",
        )
    except Exception as exc:
        logger.warning("analytics payment_succeeded failed inv_id=%s: %s", inv_id, exc)
        return False


def _fulfill_compat(
    inv_id: int, paid: dict[str, Any], seed: Optional[dict], *, out_sum: Optional[str] = None
) -> dict[str, Any]:
    """Оплачен полный расклад «Совместимость»: записать заказ (один на InvId) и сообщить человеку."""
    from bot_core.operational_store import OperationalStore

    chat_id = int(paid["chat_id"])
    amount_kopecks = int(paid.get("amount_kopecks") or 0)
    invite_id = str(paid.get("invite_id") or "")
    if not invite_id:
        logger.error("compat invoice without invite_id inv_id=%s", inv_id)
        return {"ok": False, "error": "compat invoice without invite", "inv_id": inv_id}
    try:
        orders = compat_paid.CompatOrderStore(OperationalStore(_data_dir() / "bot_state.sqlite3"))
        created, _order = orders.register(
            compat_paid.robokassa_key(inv_id),
            chat_id=chat_id,
            invite_id=invite_id,
            method="robokassa",
            amount_kopecks=amount_kopecks,
        )
    except Exception as exc:
        # без ACK Робокасса повторит уведомление — заказ запишется со второй попытки
        logger.error("compat order register failed inv_id=%s: %s", inv_id, exc)
        return {"ok": False, "error": "compat order", "inv_id": inv_id}
    if created:
        try:
            _bump_payment_stats(amount_kopecks, compat_paid.PLAN_KEY)
        except OSError:
            pass
        _track_payment_succeeded(inv_id, chat_id, compat_paid.PLAN_KEY, amount_kopecks, "compat", seed)
    _mark_fulfilled(inv_id)
    notified = False
    if not paid.get("notify_sent"):
        notified = notify_telegram(
            chat_id, "Оплата прошла ✨ Раскладываю 5 карт — полный расклад придёт через минуту."
        )
        if notified:
            robokassa_store.mark_notify_sent(inv_id)
    return {
        "ok": True,
        "already": not created,
        "chat_id": chat_id,
        "plan_key": compat_paid.PLAN_KEY,
        "kind": compat_paid.INVOICE_KIND,
        "notified": notified,
        "out_sum": out_sum,
    }


def fulfill_invoice(inv_id: int, *, out_sum: Optional[str] = None) -> dict[str, Any]:
    """
    Idempotent grant for paid InvId.
    Returns dict with keys: ok, already, chat_id, plan_key, message
    """
    existing = robokassa_store.get_invoice(inv_id)
    if not existing:
        # Fallback: Shp params should have created pending; without it we cannot grant safely
        return {"ok": False, "error": "unknown invoice", "inv_id": inv_id}

    already = existing.get("status") == "paid" and existing.get("fulfilled")
    if already:
        return {
            "ok": True,
            "already": True,
            "chat_id": existing.get("chat_id"),
            "plan_key": existing.get("plan_key"),
        }

    paid = robokassa_store.mark_paid(inv_id)
    if not paid:
        return {"ok": False, "error": "mark_paid failed", "inv_id": inv_id}

    chat_id = int(paid["chat_id"])
    plan_key = str(paid.get("plan_key") or "")
    amount_kopecks = int(paid.get("amount_kopecks") or 0)
    kind = str(paid.get("kind") or "parent")

    seed = None
    try:
        with open(_user_data_path(), "r", encoding="utf-8") as handle:
            ud = json.load(handle)
        if isinstance(ud, dict) and isinstance(ud.get(str(chat_id)), dict):
            seed = ud[str(chat_id)]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        seed = None

    if kind == compat_paid.INVOICE_KIND:
        # платная «Совместимость»: подписку НЕ выдаём, только заказ — расклад делает бот
        return _fulfill_compat(int(inv_id), paid, seed, out_sum=out_sum)

    wallet_end = None
    try:
        wallet_end = shared_wallet.view("tg", chat_id, seed).get("subscription_end")
    except Exception as exc:
        logger.warning("shared_wallet view failed chat_id=%s: %s", chat_id, exc)

    granted_now, rec = _grant_in_store(chat_id, int(inv_id), paid, wallet_end)
    if not granted_now:
        # этот счёт уже выдан (повторный ResultURL / параллельный вызов) — второй раз не даём
        _mark_fulfilled(inv_id)
        return {"ok": True, "already": True, "chat_id": chat_id, "plan_key": plan_key}

    new_end = str(rec.get("subscription_end"))
    try:
        shared_wallet.update(
            "tg", chat_id, seed, {k: rec.get(k) for k in shared_wallet.WALLET_FIELDS if k in rec}
        )
    except Exception as exc:
        logger.warning("shared_wallet update failed chat_id=%s: %s", chat_id, exc)
    try:
        _bump_payment_stats(amount_kopecks, plan_key)
    except OSError:
        pass
    _track_payment_succeeded(inv_id, chat_id, plan_key, amount_kopecks, kind, seed)
    _mark_nurture_done(chat_id)
    _mark_fulfilled(inv_id)

    end_human = datetime.strptime(new_end, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
    price_rub = amount_kopecks // 100
    if kind == "parent":
        if rec.get("auto_renew"):
            renew = (
                f"Автопродление включено: каждые 31 день спишется {price_rub} ₽, "
                "за 3 дня до списания придёт напоминание. "
                "Отменить — в меню «💳 Оформить подписку»."
            )
        else:
            renew = "Это разовая оплата, автопродления нет."
        text = (
            "Оплата прошла успешно ✨\n"
            f"Месяц безлимит, {price_rub} ₽.\n"
            f"Безлимит до {end_human}.\n" + renew
        )
    else:
        text = f"Подписка продлена до {end_human}. Списано {price_rub} ₽."

    notified = False
    if not paid.get("notify_sent"):
        notified = notify_telegram(chat_id, text)
        if notified:
            robokassa_store.mark_notify_sent(inv_id)

    return {
        "ok": True,
        "already": False,
        "chat_id": chat_id,
        "plan_key": plan_key,
        "subscription_end": new_end,
        "notified": notified,
        "out_sum": out_sum,
    }
