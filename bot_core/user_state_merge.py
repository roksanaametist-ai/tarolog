"""Merge running-bot RAM with sqlite so external grants are not wiped.

Broadcasts and repair scripts write `questions` / `subscription_end` to the
store. The bot used to dump its whole in-memory snapshot on any save
(last_activity, a single spend, …) and roll those grants back.

[CURSOR-FIX 1] Дельты вместо абсолютных значений
------------------------------------------------
Было: если юзер «dirty» (потратил вопрос), то при сохранении RAM-значение
`questions` целиком перетирало диск. Окно гонки: бот прочитал диск → скрипт
рассылки начислил +30 → бот сохранил «старое − 1» → +30 пропали.

Стало: бот копит не «новое значение», а ИЗМЕНЕНИЕ (delta: −1, +10 …).
При записи берём то, что СЕЙЧАС на диске, и прибавляем delta.
Начисление скрипта и трата бота складываются, а не затирают друг друга.

`dirty_questions` оставлен только для явной установки значения
(админский /grant «поставить ровно N», set_user_questions) — там
абсолютное значение по смыслу правильно.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, MutableMapping, Optional


def merge_user_documents(
    disk: Any,
    ram: Mapping[str, Any],
    *,
    dirty_questions: Iterable[str] = (),
    dirty_subscription: Iterable[str] = (),
    question_deltas: Optional[Mapping[str, int]] = None,
) -> dict[str, Any]:
    """Keep disk-only users; overlay RAM; preserve disk wallet unless dirty.

    Приоритет для `questions`:
      1. юзер в `dirty_questions`  → значение из RAM (явный set)
      2. юзер в `question_deltas`  → disk + delta (не ниже 0)
      3. иначе                     → значение с диска
    """
    out: dict[str, Any] = dict(disk) if isinstance(disk, dict) else {}
    dirty_q = {str(x) for x in dirty_questions}
    dirty_s = {str(x) for x in dirty_subscription}
    deltas = {str(k): int(v) for k, v in (question_deltas or {}).items() if int(v) != 0}
    for key, ram_u in ram.items():
        if not isinstance(ram_u, dict):
            continue
        key = str(key)
        disk_u = out.get(key) if isinstance(out.get(key), dict) else {}
        merged: dict[str, Any] = {**disk_u, **ram_u}
        if "questions" in disk_u and key not in dirty_q:
            if key in deltas:
                base = int(disk_u.get("questions") or 0)
                merged["questions"] = max(0, base + deltas[key])
            else:
                merged["questions"] = disk_u["questions"]
        # (юзера нет на диске → берём RAM как есть: это новый юзер)
        if key not in dirty_s and "subscription_end" in disk_u:
            merged["subscription_end"] = disk_u["subscription_end"]
        out[key] = merged
    return out


def overlay_wallet_from_disk(
    ram: MutableMapping[str, Any],
    disk: Mapping[str, Any],
    *,
    dirty_questions: Iterable[str] = (),
    dirty_subscription: Iterable[str] = (),
    question_deltas: Optional[Mapping[str, int]] = None,
) -> None:
    """Update in-memory users with newer disk wallet fields (non-destructive).

    [CURSOR-FIX 1] Если у юзера есть несохранённая delta, в RAM кладём
    disk + delta, чтобы экран баланса показывал правду ещё до записи.
    """
    dirty_q = {str(x) for x in dirty_questions}
    dirty_s = {str(x) for x in dirty_subscription}
    deltas = {str(k): int(v) for k, v in (question_deltas or {}).items() if int(v) != 0}
    for key, disk_u in disk.items():
        if not isinstance(disk_u, dict):
            continue
        key = str(key)
        ram_u = ram.get(key)
        if ram_u is None or not isinstance(ram_u, dict):
            ram[key] = dict(disk_u)
            continue
        if "questions" in disk_u and key not in dirty_q:
            if key in deltas:
                ram_u["questions"] = max(0, int(disk_u.get("questions") or 0) + deltas[key])
            else:
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
