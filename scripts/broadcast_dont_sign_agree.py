#!/usr/bin/env python3
"""Invite users without agreement: confirm → +15 → yes/no. Dry-run by default."""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics import AnalyticsStore
from bot_core.operational_store import OperationalStore

CAMPAIGN_ID = "dont-sign-agree-15"
CAMPAIGN_CODE = "dont-sign"
BONUS = 15
AGREEMENT_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-01-21-11"

MESSAGE = (
    "На этой неделе не подписывай.\n\n"
    "Пока не спросишь карты.\n"
    f"Чтобы открыть расклад, подтверди соглашение — за это +{BONUS} на баланс."
)


def _load(data_dir: Path):
    store = OperationalStore(data_dir / "bot_state.sqlite3")
    users = store.load_document(
        "users", legacy_path=data_dir / "user_data.json", default={}
    )
    agreements = store.load_document(
        "user_agreements",
        legacy_path=data_dir / "user_agreements.json",
        default={},
    )
    history = store.load_document(
        "broadcast_campaigns",
        legacy_path=data_dir / "broadcast_campaigns.json",
        default={},
    )
    if not isinstance(users, dict):
        users = {}
    if not isinstance(agreements, dict):
        agreements = {}
    if not isinstance(history, dict):
        history = {}
    return store, users, agreements, history


def select_recipients(
    users: dict,
    agreements: dict,
    already_done: set[int],
) -> list[int]:
    ids: list[int] = []
    for raw_id, raw_user in users.items():
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in already_done:
            continue
        if bool(agreements.get(str(user_id))):
            continue
        user = raw_user if isinstance(raw_user, dict) else {}
        if bool(user.get("tg_blocked")):
            continue
        ids.append(user_id)
    return sorted(set(ids))


def _backup(data_dir: Path) -> None:
    user_data_path = data_dir / "user_data.json"
    if user_data_path.exists():
        backup = data_dir / (
            f"user_data.backup-dont-sign-agree-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        )
        shutil.copy2(user_data_path, backup)
        print(f"backup: {backup}", flush=True)
    state_db = data_dir / "bot_state.sqlite3"
    if state_db.exists():
        state_backup = data_dir / (
            f"bot_state.backup-dont-sign-agree-{datetime.now().strftime('%Y%m%d%H%M%S')}.sqlite3"
        )
        shutil.copy2(state_db, state_backup)
        print(f"backup: {state_backup}", flush=True)


async def send_invites(
    *,
    token: str,
    data_dir: Path,
    store: OperationalStore,
    analytics: AnalyticsStore,
    users: dict,
    history: dict,
    recipients: list[int],
) -> tuple[int, int]:
    _backup(data_dir)
    bot = Bot(token)
    from _broadcast_retry import install_retry_after  # [fix-039] FloodWait
    install_retry_after(bot)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Подтвердить и спросить — +{BONUS}",
                    callback_data="agree_dontsign",
                )
            ],
            [InlineKeyboardButton(text="📄 Читать соглашение", url=AGREEMENT_URL)],
        ]
    )
    campaign = history.setdefault(
        CAMPAIGN_ID,
        {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bonus": BONUS,
            "recipients": {},
        },
    )
    records = campaign.setdefault("recipients", {})
    sent = 0
    failed = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        for index, user_id in enumerate(recipients, start=1):
            key = str(user_id)
            record = records.get(key) if isinstance(records.get(key), dict) else {}
            if record.get("status") == "sent":
                continue
            try:
                await bot.send_message(user_id, MESSAGE, reply_markup=kb)
                user = users.setdefault(key, {})
                if not isinstance(user, dict):
                    user = {}
                    users[key] = user
                user["campaign_touch"] = {
                    "code": CAMPAIGN_CODE,
                    "started_at": now,
                }
                records[key] = {
                    **record,
                    "invited": True,
                    "invited_at": now,
                    "status": "sent",
                    "sent_at": now,
                }
                analytics.track(
                    "broadcast_sent",
                    user_id=user_id,
                    properties={"campaign": CAMPAIGN_ID, "bonus": BONUS},
                    dedupe_key=f"broadcast:{CAMPAIGN_ID}:{user_id}",
                )
                sent += 1
            except Exception as exc:
                records[key] = {
                    **record,
                    "invited": True,
                    "invited_at": now,
                    "status": "failed",
                    "failed_at": now,
                    "error": type(exc).__name__,
                }
                err_name = type(exc).__name__
                err_text = str(exc).lower()
                if (
                    err_name == "TelegramForbiddenError"
                    or "blocked" in err_text
                    or "deactivated" in err_text
                ):
                    user = users.setdefault(key, {})
                    if not isinstance(user, dict):
                        user = {}
                        users[key] = user
                    user["tg_blocked"] = True
                    user["tg_blocked_at"] = now
                    user["tg_blocked_reason"] = err_name
                failed += 1
                if failed <= 20:
                    print(f"fail {user_id}: {type(exc).__name__}: {exc}", flush=True)
            if index % 25 == 0:
                store.save_document(
                    "users", users, legacy_path=data_dir / "user_data.json"
                )
                store.save_document(
                    "broadcast_campaigns",
                    history,
                    legacy_path=data_dir / "broadcast_campaigns.json",
                )
                await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(0.05)
            if index % 100 == 0:
                print(
                    f"progress {index}/{len(recipients)} sent={sent} failed={failed}",
                    flush=True,
                )
    finally:
        store.save_document("users", users, legacy_path=data_dir / "user_data.json")
        store.save_document(
            "broadcast_campaigns",
            history,
            legacy_path=data_dir / "broadcast_campaigns.json",
        )
        await bot.session.close()
    return sent, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Invite non-agreed users: confirm agreement, +15, yes/no (dry-run by default)."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("BOT_DATA_DIR") or "/root/tarolog"),
    )
    parser.add_argument("--sample", type=int, default=15)
    parser.add_argument("--send", action="store_true")
    parser.add_argument(
        "--confirm",
        help=f"Required with --send; must equal '{CAMPAIGN_ID}'.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = parse_args()
    data_dir = args.data_dir.resolve()
    load_dotenv(data_dir / ".env")
    load_dotenv(ROOT / ".env")

    store, users, agreements, history = _load(data_dir)
    campaign = history.get(CAMPAIGN_ID) or {}
    already_done = {
        int(user_id)
        for user_id, record in (campaign.get("recipients") or {}).items()
        if str(user_id).isdigit()
        and isinstance(record, dict)
        and (record.get("status") == "sent" or record.get("granted"))
    }
    recipients = select_recipients(users, agreements, already_done)
    no_agree = sum(
        1
        for k in users
        if str(k).isdigit()
        and int(k) > 0
        and not bool(agreements.get(str(k)))
    )

    print(f"mode: {'SEND' if args.send else 'DRY-RUN'}")
    print(f"campaign: {CAMPAIGN_ID}")
    print(f"bonus after agree: +{BONUS}")
    print(f"users in db: {len(users)}")
    print(f"without agreement: {no_agree}")
    print(f"already done / excluded: {len(already_done)}")
    print(f"eligible recipients: {len(recipients)}")
    if recipients:
        sample = ", ".join(str(uid) for uid in recipients[: max(0, int(args.sample))])
        print(f"sample user IDs: {sample}")
    print("\nMessage preview:\n")
    print(MESSAGE)
    print("Bonus is granted only after the user confirms the agreement.")

    if not args.send:
        print(
            f"\nNo messages sent. Add --send --confirm {CAMPAIGN_ID} after review."
        )
        return 0
    if args.confirm != CAMPAIGN_ID:
        raise SystemExit(
            f"Refusing to send: --confirm must exactly equal '{CAMPAIGN_ID}'"
        )
    token = (
        os.getenv("TELEGRAM_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()
    if not token:
        raise SystemExit("Refusing to send: TELEGRAM_TOKEN is missing")

    analytics = AnalyticsStore(data_dir / "analytics.sqlite3")
    sent, failed = asyncio.run(
        send_invites(
            token=token,
            data_dir=data_dir,
            store=store,
            analytics=analytics,
            users=users,
            history=history,
            recipients=recipients,
        )
    )
    print(f"\nDONE sent={sent} failed={failed} (bonus pending until agree)")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
