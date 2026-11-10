from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .operational_store import OperationalStore


PAYMENT_SUB_KEYS = ("10", "31d", "93d", "365d")
PAYMENT_KEY_MIGRATE = {
    "7d": "31d",
    "14d": "93d",
    "30d": "365d",
    "30": "31d",
    "31": "31d",
    "93": "93d",
    "365": "365d",
}


def normalize_payment_data(raw: Mapping[str, Any] | None = None) -> dict:
    source = dict(raw or {})
    result = {
        "total_amount": int(source.get("total_amount", 0) or 0),
        "subscriptions": {key: 0 for key in PAYMENT_SUB_KEYS},
    }
    subscriptions = source.get("subscriptions") or {}
    if isinstance(subscriptions, Mapping):
        for key, value in subscriptions.items():
            canonical = PAYMENT_KEY_MIGRATE.get(str(key), str(key))
            if canonical not in result["subscriptions"]:
                continue
            try:
                result["subscriptions"][canonical] += int(value or 0)
            except (TypeError, ValueError):
                continue
    return result


class PaymentStatsStore:
    def __init__(
        self,
        operational_store: OperationalStore,
        legacy_path: str | Path,
    ) -> None:
        self.operational_store = operational_store
        self.legacy_path = Path(legacy_path)

    def load(self) -> dict:
        raw = self.operational_store.load_document(
            "payment_totals",
            legacy_path=self.legacy_path,
            default={},
        )
        return normalize_payment_data(raw if isinstance(raw, Mapping) else None)

    def save(self, data: Mapping[str, Any]) -> None:
        self.operational_store.save_document(
            "payment_totals",
            normalize_payment_data(data),
            legacy_path=self.legacy_path,
        )

    def initialize(self) -> None:
        self.save(self.load())

    def add_payment(self, amount_kopecks: int, subscription_type: str) -> dict:
        data = self.load()
        data["total_amount"] += int(amount_kopecks or 0)
        canonical = PAYMENT_KEY_MIGRATE.get(
            str(subscription_type), str(subscription_type)
        )
        if canonical in data["subscriptions"]:
            data["subscriptions"][canonical] += 1
        self.save(data)
        return data
