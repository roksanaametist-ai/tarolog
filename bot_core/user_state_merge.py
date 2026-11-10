"""Merge running-bot RAM with sqlite so external grants are not wiped.

Broadcasts and repair scripts write `questions` / `subscription_end` to the
store. The bot used to dump its whole in-memory snapshot on any save
(last_activity, a single spend, …) and roll those grants back.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, MutableMapping, Optional


def merge_user_documents(
    disk: Any,
    ram: Mapping[str, Any],
    *,
    dirty_questions: Iterable[str] = (),
    dirty_subscription: Iterable[str] = (),
) -> dict[str, Any]:
    """Keep disk-only users; overlay RAM; preserve disk wallet unless dirty."""
    out: dict[str, Any] = dict(disk) if isinstance(disk, dict) else {}
    dirty_q = {str(x) for x in dirty_questions}
    dirty_s = {str(x) for x in dirty_subscription}
    for key, ram_u in ram.items():
        if not isinstance(ram_u, dict):
            continue
        disk_u = out.get(key) if isinstance(out.get(key), dict) else {}
        merged: dict[str, Any] = {**disk_u, **ram_u}
        if key not in dirty_q and "questions" in disk_u:
            merged["questions"] = disk_u["questions"]
        if key not in dirty_s and "subscription_end" in disk_u:
            merged["subscription_end"] = disk_u["subscription_end"]
        out[str(key)] = merged
    return out


def overlay_wallet_from_disk(
    ram: MutableMapping[str, Any],
    disk: Mapping[str, Any],
    *,
    dirty_questions: Iterable[str] = (),
    dirty_subscription: Iterable[str] = (),
) -> None:
    """Update in-memory users with newer disk wallet fields (non-destructive)."""
    dirty_q = {str(x) for x in dirty_questions}
    dirty_s = {str(x) for x in dirty_subscription}
    for key, disk_u in disk.items():
        if not isinstance(disk_u, dict):
            continue
        ram_u = ram.get(key)
        if ram_u is None or not isinstance(ram_u, dict):
            ram[key] = dict(disk_u)
            continue
        if key not in dirty_q and "questions" in disk_u:
            ram_u["questions"] = disk_u["questions"]
        if key not in dirty_s and "subscription_end" in disk_u:
            ram_u["subscription_end"] = disk_u["subscription_end"]
        if key not in dirty_s:
            for field in (
                "subscription_plan_key",
                "subscription_price",
                "auto_renew",
                "payment_provider",
                "robokassa_prev_invoice_id",
                "last_robokassa_inv_id",
                "renew_fail_count",
                "next_renew_at",
            ):
                if field in disk_u:
                    ram_u[field] = disk_u[field]
