"""Платная полная «Совместимость» без приглашения: 99 ₽ (Робокасса) / 69 ⭐.

Заказы — документ ``compat_orders`` в OperationalStore (bot_state.sqlite3):

    {"orders": {"rk:<InvId>" | "stars:<telegram_payment_charge_id>": {
        "key", "chat_id", "invite_id", "method": "robokassa|stars",
        "amount_kopecks", "amount_stars", "status": "paid|delivering|delivered|failed",
        "attempts", "created_at", "next_try_at", "started_at", "delivered_at"}}}

Ключ заказа = номер платежа, поэтому повторное уведомление об оплате второй
заказ не создаёт (защита от двойного начисления). Выдачу (генерацию расклада)
делает бот: заказ «занимается» атомарно, упавшая выдача повторяется позже.
Сайт (ResultURL Робокассы) только регистрирует заказ — генерировать он не умеет.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

DOC_NAME = "compat_orders"
PLAN_KEY = "compat_full"
INVOICE_KIND = "compat"
PRICE_KOPECKS = 9900
PRICE_STARS = 69
PRODUCT_TITLE = "Совместимость — полный расклад"
STARS_PAYLOAD_PREFIX = "compat:"
DELIVERING_STALE_SECONDS = 15 * 60  # бот упал посреди выдачи — заказ снова можно взять
RETRY_SECONDS = 5 * 60
MAX_ATTEMPTS = 12  # ~1 час попыток, потом — сигнал администратору


def stars_enabled() -> bool:
    """Оплата звёздами включается отдельно (переменная COMPAT_STARS_ENABLED=1)."""
    return (os.getenv("COMPAT_STARS_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on"}


def robokassa_key(inv_id: int) -> str:
    return f"rk:{int(inv_id)}"


def stars_key(charge_id: str) -> str:
    return f"stars:{str(charge_id).strip()}"


def stars_payload(invite_id: str) -> str:
    return f"{STARS_PAYLOAD_PREFIX}{invite_id}"


def parse_stars_payload(payload: Any) -> Optional[str]:
    raw = str(payload or "")
    if not raw.startswith(STARS_PAYLOAD_PREFIX):
        return None
    invite_id = raw[len(STARS_PAYLOAD_PREFIX):]
    return invite_id if 6 <= len(invite_id) <= 40 else None


def pay_screen_text(partner_name: str) -> str:
    partner = partner_name or "второй человек"
    return (
        "Полный расклад на пару: 5 карт — что вас связывает, что мешает и куда всё идёт. "
        f"Только для тебя, {partner} ничего не узнает.\n\n"
        "<i>Особый расклад, в безлимит не входит.</i>"
    )


def invite_button_text(partner_name: str) -> str:
    return f"📩 Позвать {partner_name or 'его(её)'} — полный расклад бесплатно"


def buy_button_text() -> str:
    return f"🔒 Узнать полный расклад сейчас — {PRICE_KOPECKS // 100} ₽"


class CompatOrderStore:
    def __init__(
        self,
        store: Any,
        *,
        doc_name: str = DOC_NAME,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.store = store
        self.doc_name = doc_name
        self.now = now

    @staticmethod
    def _norm(doc: Any) -> Dict[str, Any]:
        if not isinstance(doc, dict):
            doc = {}
        if not isinstance(doc.get("orders"), dict):
            doc["orders"] = {}
        return doc

    def _update(self, mutator: Callable[[Dict[str, Any]], Any]) -> Any:
        box: Dict[str, Any] = {}

        def _m(current: Any) -> Dict[str, Any]:
            doc = self._norm(current)
            box["result"] = mutator(doc)
            return doc

        self.store.update_document(self.doc_name, _m, default={})
        return box.get("result")

    def register(
        self,
        key: str,
        *,
        chat_id: int,
        invite_id: str,
        method: str,
        amount_kopecks: int = 0,
        amount_stars: int = 0,
    ) -> Tuple[bool, Dict[str, Any]]:
        """(создан_сейчас, заказ). Повтор того же платежа возвращает (False, прежний заказ)."""

        def _m(doc: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
            orders = doc["orders"]
            if key in orders and isinstance(orders[key], dict):
                return False, dict(orders[key])
            now = float(self.now())
            rec = {
                "key": key,
                "chat_id": int(chat_id),
                "invite_id": str(invite_id),
                "method": method,
                "amount_kopecks": int(amount_kopecks),
                "amount_stars": int(amount_stars),
                "status": "paid",
                "attempts": 0,
                "created_at": now,
                "next_try_at": now,
            }
            orders[key] = rec
            return True, dict(rec)

        return self._update(_m)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._update(
            lambda doc: dict(doc["orders"][key]) if isinstance(doc["orders"].get(key), dict) else None
        )

    def _takeable(self, rec: Dict[str, Any], now: float) -> bool:
        status = rec.get("status")
        if status == "paid":
            return float(rec.get("next_try_at") or 0) <= now
        if status == "delivering":
            return now - float(rec.get("started_at") or 0) > DELIVERING_STALE_SECONDS
        return False

    def begin_delivery(self, key: str, *, force: bool = False) -> Optional[Dict[str, Any]]:
        """Атомарно занять заказ под выдачу. None — уже выдан / выдаётся / ещё рано.

        force=True — не ждать паузы между попытками (оплата только что пришла).
        """

        def _m(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            rec = doc["orders"].get(key)
            if not isinstance(rec, dict):
                return None
            now = float(self.now())
            if not self._takeable(rec, now) and not (force and rec.get("status") == "paid"):
                return None
            rec["status"] = "delivering"
            rec["started_at"] = now
            rec["attempts"] = int(rec.get("attempts") or 0) + 1
            return dict(rec)

        return self._update(_m)

    def finish(self, key: str, *, replay: bool = False) -> None:
        def _m(doc: Dict[str, Any]) -> None:
            rec = doc["orders"].get(key)
            if isinstance(rec, dict):
                rec["status"] = "delivered"
                rec["delivered_at"] = float(self.now())
                if replay:
                    rec["replay"] = True

        self._update(_m)

    def fail(self, key: str) -> Optional[Dict[str, Any]]:
        """Выдача не удалась. Вернёт заказ; status=failed — попытки кончились."""

        def _m(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            rec = doc["orders"].get(key)
            if not isinstance(rec, dict):
                return None
            if int(rec.get("attempts") or 0) >= MAX_ATTEMPTS:
                rec["status"] = "failed"
            else:
                rec["status"] = "paid"
                rec["next_try_at"] = float(self.now()) + RETRY_SECONDS
            return dict(rec)

        return self._update(_m)

    def due(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Оплаченные, но не выданные заказы, которые пора (пере)выдать."""

        def _m(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
            now = float(self.now())
            out = [dict(r) for r in doc["orders"].values() if isinstance(r, dict) and self._takeable(r, now)]
            out.sort(key=lambda r: float(r.get("created_at") or 0))
            return out[: max(1, int(limit))]

        return self._update(_m)

    def for_invite(self, invite_id: str) -> List[Dict[str, Any]]:
        return self._update(
            lambda doc: [
                dict(r)
                for r in doc["orders"].values()
                if isinstance(r, dict) and r.get("invite_id") == invite_id
            ]
        )
