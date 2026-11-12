"""Когда напоминать и когда списывать автопродление (чистые функции, без I/O).

Правила (задача 013, оферта п. 11):
- за 3 дня до списания пользователю приходит напоминание;
- списание не раньше чем через 3 дня после напоминания и не раньше чем за 1 день до конца;
- за один и тот же период (subscription_end) списываем не больше одного раза (P-2);
- пока дочерний счёт ждёт подтверждения — новых списаний нет.

Поля пользователя:
- renew_reminded_for_end — для какого subscription_end уже отправлено напоминание;
- renew_not_before — раньше этого времени не списывать;
- renew_charged_for_end — для какого subscription_end списание уже принято Robokassa;
- renew_pending_inv_id / renew_pending_since — дочерний счёт, ждём ResultURL;
- next_renew_at — повтор после неудачи (12 ч / 24 ч).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

FMT = "%Y-%m-%d %H:%M:%S"

NOTICE_DAYS = 3            # напоминание минимум за 3 дня до списания
CHARGE_BEFORE_END = timedelta(days=1)
REMIND_BEFORE_END = timedelta(days=NOTICE_DAYS) + CHARGE_BEFORE_END
PENDING_CHECK_AFTER = timedelta(minutes=30)

NONE = "none"
REMIND = "remind"
CHARGE = "charge"
PENDING = "pending"

RENEWAL_FIELDS = (
    "renew_reminded_for_end",
    "renew_not_before",
    "renew_charged_for_end",
    "renew_pending_inv_id",
    "renew_pending_since",
)


def parse(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw), FMT)
    except ValueError:
        return None


def fmt(value: Optional[datetime]) -> Optional[str]:
    return value.strftime(FMT) if value else None


def has_billing(u: Mapping[str, Any], default_provider: str = "") -> bool:
    if not u.get("auto_renew"):
        return False
    if not u.get("subscription_price") or not u.get("subscription_plan_key"):
        return False
    provider = str(u.get("payment_provider") or default_provider or "").lower()
    has_robo = bool(u.get("robokassa_prev_invoice_id"))
    has_method = bool(u.get("yookassa_payment_method_id"))
    if provider == "robokassa" or (has_robo and not has_method):
        # Robokassa: только с записанным согласием (галочка перед оплатой)
        return has_robo and bool(u.get("auto_renew_consent"))
    return has_method


def charge_not_before(end: datetime, reminded_at: datetime) -> datetime:
    return max(end - CHARGE_BEFORE_END, reminded_at + timedelta(days=NOTICE_DAYS))


def next_action(u: Mapping[str, Any], now: datetime, default_provider: str = "") -> str:
    """Что делать с пользователем сейчас: none / remind / charge / pending."""
    if not has_billing(u, default_provider):
        return NONE
    end_raw = u.get("subscription_end")
    end = parse(end_raw)
    if end is None:
        return NONE
    if u.get("renew_pending_inv_id"):
        return PENDING
    if u.get("renew_charged_for_end") and u.get("renew_charged_for_end") == end_raw:
        # списание за этот период уже принято — ждём выдачу, повторно не списываем
        return NONE
    if u.get("renew_reminded_for_end") != end_raw:
        return REMIND if now >= end - REMIND_BEFORE_END else NONE
    retry = parse(u.get("next_renew_at"))
    if retry is not None:
        return CHARGE if now >= retry else NONE
    not_before = parse(u.get("renew_not_before")) or (end - CHARGE_BEFORE_END)
    return CHARGE if now >= not_before else NONE


def reminder_changes(u: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    end = parse(u.get("subscription_end"))
    if end is None:
        return {}
    return {
        "renew_reminded_for_end": u.get("subscription_end"),
        "renew_not_before": fmt(charge_not_before(end, now)),
    }


def pending_changes(u: Mapping[str, Any], inv_id: int, now: datetime) -> dict[str, Any]:
    """После ответа OK от Robokassa: не списывать снова за этот период (P-2)."""
    return {
        "renew_charged_for_end": u.get("subscription_end"),
        "renew_pending_inv_id": int(inv_id),
        "renew_pending_since": fmt(now),
        "next_renew_at": None,
        "renew_fail_count": 0,
    }


def cleared_after_grant() -> dict[str, Any]:
    return {
        "renew_pending_inv_id": None,
        "renew_pending_since": None,
        "renew_not_before": None,
        "next_renew_at": None,
        "renew_fail_count": 0,
    }


def pending_due_for_check(u: Mapping[str, Any], now: datetime) -> bool:
    since = parse(u.get("renew_pending_since"))
    return since is None or now - since >= PENDING_CHECK_AFTER
