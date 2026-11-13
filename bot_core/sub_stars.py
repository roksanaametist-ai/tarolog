"""Подписка за звёзды Telegram (XTR): разовая покупка 31 дня безлимита, без автопродления.

Цены в звёздах выше, чем картой (решение Роксаны 13.11.2026): цифры те же, что в рублях.
Включается тем же флагом, что звёзды в «Совместимости» (COMPAT_STARS_ENABLED=1).

Защита от двойного начисления — документ ``sub_stars_payments`` в OperationalStore:
    {"payments": {"<telegram_payment_charge_id>": {"chat_id", "plan_key", "stars", "at"}}}
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, Tuple

DOC_NAME = "sub_stars_payments"
PAYLOAD_PREFIX = "substars:"
DAYS = 31

PLAN_STARS: Dict[str, int] = {
    "sub_m_111": 111,
    "sub_m_555": 555,
    "sub_m_999": 999,
}


def payload(plan_key: str) -> str:
    return f"{PAYLOAD_PREFIX}{plan_key}"


def parse_payload(raw: Any) -> Optional[str]:
    text = str(raw or "")
    if not text.startswith(PAYLOAD_PREFIX):
        return None
    plan_key = text[len(PAYLOAD_PREFIX):]
    return plan_key if plan_key in PLAN_STARS else None


def is_valid_checkout(raw_payload: Any, currency: str, total_amount: int) -> bool:
    plan_key = parse_payload(raw_payload)
    return bool(plan_key and currency == "XTR" and int(total_amount) == PLAN_STARS[plan_key])


class SubStarsPayments:
    def __init__(self, store: Any, *, doc_name: str = DOC_NAME, now: Callable[[], float] = time.time) -> None:
        self.store = store
        self.doc_name = doc_name
        self.now = now

    def register(self, charge_id: str, *, chat_id: int, plan_key: str, stars: int) -> Tuple[bool, Dict[str, Any]]:
        """True — платёж новый (надо выдать подписку); False — уже засчитан."""
        charge_id = str(charge_id).strip()
        box: Dict[str, Any] = {}

        def _m(current: Any) -> Dict[str, Any]:
            doc = current if isinstance(current, dict) else {}
            payments = doc.get("payments") if isinstance(doc.get("payments"), dict) else {}
            doc["payments"] = payments
            if charge_id in payments:
                box["created"], box["rec"] = False, payments[charge_id]
                return doc
            rec = {"chat_id": int(chat_id), "plan_key": plan_key, "stars": int(stars), "at": self.now()}
            payments[charge_id] = rec
            box["created"], box["rec"] = True, rec
            return doc

        self.store.update_document(self.doc_name, _m, default={})
        return bool(box["created"]), dict(box["rec"])
