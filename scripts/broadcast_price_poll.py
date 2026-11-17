#!/usr/bin/env python3
"""Broadcast monthly price poll. Dry-run by default."""
from __future__ import annotations

import argparse
import asyncio
import os
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
from bot_core.price_poll import CALLBACK_PREFIX, CAMPAIGN_ID, CHOICES, QUESTION


def _load(data_dir: Path):
    store = OperationalStore(data_dir / "bot_state.sqlite3")
    users = store.load_document(
        "users", legacy_path=data_dir / "user_data.json", default={}
    )
    history = store.load_document(
        "broadcast_campaigns",
        legacy_path=data_dir / "broadcast_campaigns.json",
        default={},
    )
    if not isinstance(users, dict):
        users = {}
    if not isinstance(history, dict):
        history = {}
    return store, users, history


def poll_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for code, label in CHOICES:
        pair.append(
            InlineKeyboardButton(text=label, callback_data=f"{CALLBACK_PREFIX}{code}")
        )
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def select_recipients(users: dict, already_done: set[int]) -> list[int]:
    ids: list[int] = []
    for raw_id, raw_user in users.items():
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in already_done:
            continue
        user = raw_user if isinstance(raw_user, dict) else {}
        if bool(user.get("tg_blocked")):
            continue
        ids.append(user_id)
    return sorted(set(ids))


async def send_messages(
    *,
    token: str,
    data_dir: Path,
    store: OperationalStore,
    analytics: AnalyticsStore,
    history: dict,
    users: dict,
    recipients: list[int],
) -> tuple[int, int]:
    bot = Bot(token)
    from _broadcast_retry import install_retry_after  # [fix-039] FloodWait
    install_retry_after(bot)
    kb = poll_kb()
    campaign = history.setdefault(
        CAMPAIGN_ID,
        {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
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
                await bot.send_message(user_id, QUESTION, reply_markup=kb)
                records[key] = {
                    **record,
                    "status": "sent",
                    "sent_at": now,
                }
                analytics.track(
                    "broadcast_sent",
                    user_id=user_id,
                    properties={"campaign": CAMPAIGN_ID},
                    dedupe_key=f"broadcast:{CAMPAIGN_ID}:{user_id}",
                )
                sent += 1
            except Exception as exc:
                records[key] = {
                    **record,
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
        description="Broadcast monthly price poll (dry-run by default)."
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

    store, users, history = _load(data_dir)
    campaign = history.get(CAMPAIGN_ID) or {}
    already_done = {
        int(user_id)
        for user_id, record in (campaign.get("recipients") or {}).items()
        if str(user_id).isdigit()
        and isinstance(record, dict)
        and record.get("status") == "sent"
    }
    recipients = select_recipients(users, already_done)

    print(f"mode: {'SEND' if args.send else 'DRY-RUN'}")
    print(f"campaign: {CAMPAIGN_ID}")
    print(f"users in db: {len(users)}")
    print(f"already sent: {len(already_done)}")
    print(f"eligible recipients: {len(recipients)}")
    if recipients:
        sample = ", ".join(str(uid) for uid in recipients[: max(0, int(args.sample))])
        print(f"sample user IDs: {sample}")
    print("\nMessage preview:\n")
    print(QUESTION)
    print("\nChoices:", ", ".join(label for _c, label in CHOICES))

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
        send_messages(
            token=token,
            data_dir=data_dir,
            store=store,
            analytics=analytics,
            history=history,
            users=users,
            recipients=recipients,
        )
    )
    print(f"\nDONE sent={sent} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
