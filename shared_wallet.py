"""One questions/subscription wallet for Telegram and MAX.

Platform ids differ, so the wallets stay separate until a person sends
/link CODE from the other messenger. After that both bots read and write
the same record.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

WALLET_FIELDS = (
    "questions",
    "subscription_end",
    "email",
    "last_refill_at",
    "yookassa_payment_method_id",
    "subscription_plan_key",
    "subscription_price",
    "auto_renew",
    "renew_fail_count",
    "next_renew_at",
    "last_yookassa_payment_id",
    "refill_notice_on",
    "payment_provider",
    "robokassa_prev_invoice_id",
    "last_robokassa_inv_id",
)
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_TTL = 24 * 3600


def wallet_path() -> Path:
    configured = Path(os.getenv("BOT_DATA_DIR", "/data"))
    base = configured if configured.exists() else Path(__file__).resolve().parent
    base.mkdir(parents=True, exist_ok=True)
    return base / "shared_wallet.json"


def _key(kind: str, user_id: int) -> str:
    return f"{kind}:{int(user_id)}"


def _blank(record: Optional[dict]) -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    src = record or {}
    wallet = {
        "questions": int(src.get("questions", 5 if record else 0) or 0),
        "subscription_end": src.get("subscription_end"),
        "email": src.get("email"),
        "last_refill_at": src.get("last_refill_at") or now,
        "yookassa_payment_method_id": src.get("yookassa_payment_method_id"),
        "subscription_plan_key": src.get("subscription_plan_key"),
        "subscription_price": src.get("subscription_price"),
        "auto_renew": bool(src.get("auto_renew")),
        "renew_fail_count": int(src.get("renew_fail_count") or 0),
        "next_renew_at": src.get("next_renew_at"),
        "last_yookassa_payment_id": src.get("last_yookassa_payment_id"),
        "refill_notice_on": src.get("refill_notice_on"),
        "payment_provider": src.get("payment_provider"),
        "robokassa_prev_invoice_id": src.get("robokassa_prev_invoice_id"),
        "last_robokassa_inv_id": src.get("last_robokassa_inv_id"),
    }
    return wallet


def _load(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    raw.setdefault("wallets", {})
    raw.setdefault("bind", {})
    raw.setdefault("codes", {})
    return raw


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class _Lock:
    def __init__(self, path: Path) -> None:
        self.lock_path = path.with_suffix(".lock")

    def __enter__(self) -> "_Lock":
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
        raise TimeoutError(f"Не удалось занять {self.lock_path}")

    def __exit__(self, *_) -> None:
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _canon(data: dict[str, Any], kind: str, user_id: int) -> str:
    key = _key(kind, user_id)
    return str(data["bind"].get(key) or key)


def _ensure(data: dict[str, Any], kind: str, user_id: int, seed: Optional[dict]) -> dict[str, Any]:
    canon = _canon(data, kind, user_id)
    wallets = data["wallets"]
    if canon not in wallets:
        wallets[canon] = _blank(seed)
    return wallets[canon]


def mirror(into: Optional[dict], wallet: dict) -> None:
    if into is None:
        return
    for field in WALLET_FIELDS:
        if field in wallet:
            into[field] = wallet[field]


def peer(kind: str, user_id: int) -> Optional[str]:
    """Other platform key bound to the same wallet, if any."""
    path = wallet_path()
    with _Lock(path):
        data = _load(path)
        canon = _canon(data, kind, user_id)
        own = _key(kind, user_id)
        for src, dst in data["bind"].items():
            if dst == canon and src != own:
                return src
        if canon != own and canon.split(":", 1)[0] != kind:
            return canon
        return None


def pull_into(kind: str, users: dict) -> None:
    """Copy the shared wallet onto each local user record. Seed a wallet once if missing."""
    path = wallet_path()
    with _Lock(path):
        data = _load(path)
        changed = False
        for sid, rec in users.items():
            if not str(sid).isdigit() or not isinstance(rec, dict):
                continue
            canon = _canon(data, kind, int(sid))
            if canon not in data["wallets"]:
                data["wallets"][canon] = _blank(rec)
                changed = True
            mirror(rec, data["wallets"][canon])
        if changed:
            _save(path, data)


def view(kind: str, user_id: int, seed: Optional[dict] = None) -> dict[str, Any]:
    path = wallet_path()
    with _Lock(path):
        data = _load(path)
        wallet = dict(_ensure(data, kind, user_id, seed))
        _save(path, data)
        return wallet


def update(kind: str, user_id: int, seed: Optional[dict], changes: dict[str, Any]) -> dict[str, Any]:
    path = wallet_path()
    with _Lock(path):
        data = _load(path)
        wallet = _ensure(data, kind, user_id, seed)
        for field, value in changes.items():
            if field in WALLET_FIELDS:
                wallet[field] = value
        _save(path, data)
        return dict(wallet)


def add_questions(kind: str, user_id: int, delta: int, seed: Optional[dict]) -> Optional[dict[str, Any]]:
    path = wallet_path()
    with _Lock(path):
        data = _load(path)
        wallet = _ensure(data, kind, user_id, seed)
        current = int(wallet.get("questions") or 0)
        if delta < 0 and current <= 0:
            return None
        wallet["questions"] = current + int(delta) if delta >= 0 else current - 1
        _save(path, data)
        return dict(wallet)


def grant_periods(
    kind: str,
    user_id: int,
    seed: Optional[dict],
    *,
    period_days: int = 30,
    per_period: int = 5,
) -> int:
    """Add per_period for every full period since last_refill. Returns questions added."""
    path = wallet_path()
    now = datetime.now()
    with _Lock(path):
        data = _load(path)
        wallet = _ensure(data, kind, user_id, seed)
        raw = wallet.get("last_refill_at")
        try:
            last = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S") if raw else now
        except ValueError:
            last = now
        periods = (now.date() - last.date()).days // period_days
        if periods <= 0:
            _save(path, data)
            return 0
        wallet["questions"] = int(wallet.get("questions") or 0) + per_period * periods
        wallet["last_refill_at"] = (last + timedelta(days=period_days * periods)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _save(path, data)
        return per_period * periods


def issue_code(kind: str, user_id: int, seed: Optional[dict] = None) -> str:
    path = wallet_path()
    with _Lock(path):
        data = _load(path)
        _ensure(data, kind, user_id, seed)
        owner = _key(kind, user_id)
        data["codes"] = {
            code: meta
            for code, meta in data["codes"].items()
            if meta.get("owner") != owner and float(meta.get("exp") or 0) > time.time()
        }
        code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
        data["codes"][code] = {"owner": owner, "exp": time.time() + _CODE_TTL}
        _save(path, data)
        return code


def _later(left: Optional[str], right: Optional[str]) -> Optional[str]:
    if not left:
        return right
    if not right:
        return left
    return left if left >= right else right


def redeem(kind: str, user_id: int, code: str, seed: Optional[dict] = None) -> tuple[bool, str]:
    code = (code or "").strip().upper().replace(" ", "")
    if code.startswith("/LINK"):
        code = code[5:].strip()
    path = wallet_path()
    other_name = "MAX" if kind == "tg" else "Telegram"
    same_name = "Telegram" if kind == "tg" else "MAX"
    with _Lock(path):
        data = _load(path)
        meta = data["codes"].get(code)
        if not meta or float(meta.get("exp") or 0) < time.time():
            return False, "Код не найден или истёк. Откройте «Мой баланс» в другом мессенджере и возьмите новый."
        owner = str(meta.get("owner") or "")
        if ":" not in owner:
            return False, "Код повреждён. Запросите новый."
        owner_kind, owner_raw = owner.split(":", 1)
        if not owner_raw.isdigit():
            return False, "Код повреждён. Запросите новый."
        if owner_kind == kind:
            return False, f"Этот код тоже из {same_name}. Откройте бота в {other_name} и отправьте код туда."
        own = _key(kind, user_id)
        if data["bind"].get(own) or data["bind"].get(owner):
            return False, "Один из аккаунтов уже связан. Баланс общий."
        _ensure(data, kind, user_id, seed)
        _ensure(data, owner_kind, int(owner_raw), None)
        src = data["wallets"][own]
        dst_key = owner
        dst = data["wallets"][dst_key]
        dst["questions"] = int(dst.get("questions") or 0) + int(src.get("questions") or 0)
        dst["subscription_end"] = _later(dst.get("subscription_end"), src.get("subscription_end"))
        if not dst.get("email") and src.get("email"):
            dst["email"] = src["email"]
        if not dst.get("auto_renew") and src.get("auto_renew"):
            for field in (
                "auto_renew",
                "yookassa_payment_method_id",
                "subscription_plan_key",
                "subscription_price",
                "renew_fail_count",
                "next_renew_at",
            ):
                dst[field] = src.get(field)
        dst["last_refill_at"] = _later(dst.get("last_refill_at"), src.get("last_refill_at")) or dst.get(
            "last_refill_at"
        )
        data["bind"][own] = dst_key
        data["codes"].pop(code, None)
        _save(path, data)
        return True, (
            f"Готово. Баланс теперь общий с {other_name}: "
            f"{int(dst.get('questions') or 0)} вопросов. "
            "Списание в одном мессенджере видно в другом."
        )


def hint(kind: str, user_id: int, seed: Optional[dict] = None) -> str:
    other = "MAX" if kind == "tg" else "Telegram"
    if peer(kind, user_id):
        return f"\nОбщий баланс с {other} включён."
    code = issue_code(kind, user_id, seed)
    return (
        f"\n\nОдин баланс с {other}: откройте бота там и отправьте\n"
        f"/link {code}"
    )
