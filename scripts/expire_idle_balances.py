#!/usr/bin/env python3
"""Cut idle ping recipients to 1 question after the deadline. Dry-run by default."""
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

from bot_core.idle_expire import (
    BUTTON_ASK,
    CALLBACK_ASK,
    CAMPAIGN_ID,
    CUT_TEXT,
    DEADLINE_MSK,
    KEEP_QUESTIONS,
    SKIP_ADMIN_IDS,
    has_reading_since,
    parse_iso_utc,
)
from bot_core.operational_store import OperationalStore


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
    items = store.load_document(
        "user_questions", legacy_path=data_dir / "user_questions.json", default=[]
    )
    if not isinstance(users, dict):
        users = {}
    if not isinstance(history, dict):
        history = {}
    if not isinstance(items, list):
        items = []
    return store, users, history, items


def _questions(user: dict) -> int:
    try:
        return int(user.get("questions") or 0)
    except (TypeError, ValueError):
        return 0


async def notify_cut(token: str, user_ids: list[int]) -> None:
    bot = Bot(token)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTON_ASK, callback_data=CALLBACK_ASK)]
        ]
    )
    try:
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, CUT_TEXT, reply_markup=kb)
            except Exception as exc:
                print(f"notify fail {user_id}: {type(exc).__name__}: {exc}", flush=True)
            await asyncio.sleep(0.05)
    finally:
        await bot.session.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply idle expire cut (dry-run default).")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("BOT_DATA_DIR") or "/root/tarolog"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true", help="Allow apply before deadline.")
    parser.add_argument("--notify", action="store_true", default=True)
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument(
        "--confirm",
        help=f"Required with --apply; must equal '{CAMPAIGN_ID}'.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = parse_args()
    notify = bool(args.notify) and not args.no_notify
    data_dir = args.data_dir.resolve()
    load_dotenv(data_dir / ".env")
    load_dotenv(ROOT / ".env")

    now = datetime.now(timezone.utc)
    store, users, history, items = _load(data_dir)
    campaign = history.get(CAMPAIGN_ID) if isinstance(history.get(CAMPAIGN_ID), dict) else {}
    records = campaign.get("recipients") if isinstance(campaign.get("recipients"), dict) else {}

    to_cut: list[tuple[int, int]] = []
    skipped_read = 0
    skipped_low = 0
    skipped_other = 0
    for key, record in records.items():
        if not isinstance(record, dict) or record.get("status") != "sent":
            continue
        if record.get("expired"):
            skipped_other += 1
            continue
        try:
            user_id = int(key)
        except (TypeError, ValueError):
            continue
        if user_id in SKIP_ADMIN_IDS:
            skipped_other += 1
            continue
        user = users.get(key) if isinstance(users.get(key), dict) else {}
        if user.get("tg_blocked"):
            skipped_other += 1
            continue
        sent_at = parse_iso_utc(record.get("sent_at")) or parse_iso_utc(campaign.get("created_at"))
        if sent_at is None:
            skipped_other += 1
            continue
        if has_reading_since(items, user_id, sent_at):
            skipped_read += 1
            continue
        q = _questions(user)
        if q <= KEEP_QUESTIONS:
            skipped_low += 1
            continue
        to_cut.append((user_id, q))

    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"now_utc: {now.isoformat()}")
    print(f"deadline: {DEADLINE_MSK.isoformat()}")
    print(f"campaign sent records: {sum(1 for r in records.values() if isinstance(r, dict) and r.get('status')=='sent')}")
    print(f"would_cut: {len(to_cut)} skipped_read={skipped_read} skipped_already_low={skipped_low} skipped_other={skipped_other}")
    if to_cut:
        preview = ", ".join(f"{uid}:{q}->{KEEP_QUESTIONS}" for uid, q in to_cut[:12])
        print(f"sample: {preview}")

    if not args.apply:
        print("\nNo balances changed. Add --apply --confirm idle-expire-keep1 after deadline.")
        return 0
    if args.confirm != CAMPAIGN_ID:
        raise SystemExit(f"Refusing: --confirm must equal '{CAMPAIGN_ID}'")
    if now < DEADLINE_MSK.astimezone(timezone.utc) and not args.force:
        raise SystemExit("Refusing: deadline not reached (pass --force to override)")

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = data_dir / f"user_data.backup-idle-expire-{stamp}.json"
    src = data_dir / "user_data.json"
    if src.exists():
        shutil.copy2(src, backup)
        print(f"backup: {backup}")

    cut_ids: list[int] = []
    now_s = now.isoformat(timespec="seconds")
    for user_id, old_q in to_cut:
        key = str(user_id)
        user = users.setdefault(key, {})
        if not isinstance(user, dict):
            user = {}
            users[key] = user
        user["questions"] = KEEP_QUESTIONS
        user["idle_expire_at"] = now_s
        user["idle_expire_from"] = old_q
        rec = records.get(key) if isinstance(records.get(key), dict) else {}
        rec["expired"] = True
        rec["expired_at"] = now_s
        rec["expired_from"] = old_q
        records[key] = rec
        cut_ids.append(user_id)

    store.save_document("users", users, legacy_path=data_dir / "user_data.json")
    store.save_document(
        "broadcast_campaigns",
        history,
        legacy_path=data_dir / "broadcast_campaigns.json",
    )
    print(f"cut {len(cut_ids)} users to {KEEP_QUESTIONS}")

    if notify and cut_ids:
        token = (
            os.getenv("TELEGRAM_TOKEN")
            or os.getenv("BOT_TOKEN")
            or os.getenv("TELEGRAM_BOT_TOKEN")
            or ""
        ).strip()
        if not token:
            print("skip notify: no token")
        else:
            asyncio.run(notify_cut(token, cut_ids))
            print(f"notified {len(cut_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
