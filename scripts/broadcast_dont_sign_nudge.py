#!/usr/bin/env python3
"""Nudge unused +15: one-tap yes/no «подписывать ли». Dry-run by default."""
from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
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

CAMPAIGN_ID = "dont-sign-nudge"
SOURCE_CAMPAIGN = "dont-sign-15"
SINCE_DATE = "2026-08-23"

MESSAGE = (
    "У тебя +15 раскладов уже лежат.\n\n"
    "Карты готовы на один вопрос:\n"
    "«На этой неделе подписывать?»\n\n"
    "Это не оплата. Один тап — сразу да или нет."
)

BUTTON_TEXT = "Тянуть карту"


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


def users_who_read_since(analytics_db: Path, since_date: str) -> set[int]:
    if not analytics_db.is_file():
        return set()
    conn = sqlite3.connect(analytics_db)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT user_id
            FROM events
            WHERE user_id IS NOT NULL
              AND local_date >= ?
              AND event_name IN ('reading_started', 'reading_completed')
            """,
            (since_date,),
        ).fetchall()
    finally:
        conn.close()
    return {int(r[0]) for r in rows if r[0]}


def select_recipients(
    users: dict,
    agreements: dict,
    history: dict,
    already_done: set[int],
    already_read: set[int],
) -> list[int]:
    source = history.get(SOURCE_CAMPAIGN) or {}
    source_recs = source.get("recipients") if isinstance(source, dict) else {}
    if not isinstance(source_recs, dict):
        source_recs = {}
    ids: list[int] = []
    for raw_id, rec in source_recs.items():
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in already_done or user_id in already_read:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("status") != "sent" or not rec.get("granted"):
            continue
        if not bool(agreements.get(str(user_id))):
            continue
        user = users.get(str(user_id)) if isinstance(users.get(str(user_id)), dict) else {}
        if bool(user.get("tg_blocked")):
            continue
        try:
            questions = int(user.get("questions") or 0)
        except (TypeError, ValueError):
            questions = 0
        if questions <= 0:
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
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTON_TEXT, callback_data="dontsign_now")]
        ]
    )
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
                await bot.send_message(user_id, MESSAGE, reply_markup=kb)
                records[key] = {**record, "status": "sent", "sent_at": now}
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
        description="Nudge unused +15 into one-tap yes/no (dry-run by default)."
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
        and record.get("status") == "sent"
    }
    already_read = users_who_read_since(data_dir / "analytics.sqlite3", SINCE_DATE)
    recipients = select_recipients(
        users, agreements, history, already_done, already_read
    )

    print(f"mode: {'SEND' if args.send else 'DRY-RUN'}")
    print(f"campaign: {CAMPAIGN_ID}")
    print(f"read today (excluded): {len(already_read)}")
    print(f"already nudged: {len(already_done)}")
    print(f"eligible recipients: {len(recipients)}")
    if recipients:
        sample = ", ".join(str(uid) for uid in recipients[: max(0, int(args.sample))])
        print(f"sample user IDs: {sample}")
    print("\nMessage preview:\n")
    print(MESSAGE)
    print(f"\nButton: {BUTTON_TEXT} -> callback dontsign_now")

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
