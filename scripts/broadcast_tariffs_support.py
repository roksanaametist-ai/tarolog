#!/usr/bin/env python3
"""Tariffs + foreign cards + new site spreads. Same good-news photo. Dry-run by default. No bonus."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics import AnalyticsStore
from bot_core.operational_store import OperationalStore

CAMPAIGN_ID = "tariffs-support-2026-11"
PHOTO = Path("/root/tarolog/static/broadcast_referral_unlim.jpg")
BOT_URL = "https://t.me/Roxanaametist_Taro_bot"
ROXANA_URL = "https://t.me/roxanaametist"
SITE_READING_URL = "https://followthefrensy.ru/reading"

MESSAGE = (
    "Друзья, хорошие новости!\n"
    "\n"
    "Безлимит в боте можно получить, оказав поддержку моим проектам, "
    "на комфортную для вас сумму.\n"
    "Оплата возможна и с зарубежных карт!\n"
    "\n"
    "И ещё: на сайте появились новые расклады —\n"
    f"{SITE_READING_URL}\n"
    "\n"
    "Зайди в бота → «Оформить подписку».\n"
    "\n"
    "Предложения и сбои — в лс: @roxanaametist"
)


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


def kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔮 Открыть бота", url=BOT_URL)],
            [InlineKeyboardButton(text="🃏 Новые расклады", url=SITE_READING_URL)],
            [
                InlineKeyboardButton(
                    text="✍️ Написать Роксане",
                    url=ROXANA_URL,
                )
            ],
        ]
    )


def _save_campaign(store: OperationalStore, data_dir: Path, history: dict) -> None:
    store.save_document(
        "broadcast_campaigns",
        history,
        legacy_path=data_dir / "broadcast_campaigns.json",
    )


def _mark_blocked(store: OperationalStore, data_dir: Path, user_id: int, reason: str) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    key = str(user_id)

    def mutate(users):
        if not isinstance(users, dict):
            users = {}
        user = users.get(key)
        if not isinstance(user, dict):
            user = {}
            users[key] = user
        user["tg_blocked"] = True
        user["tg_blocked_at"] = now
        user["tg_blocked_reason"] = reason
        return users

    updater = getattr(store, "update_document", None)
    if callable(updater):
        updater(
            "users",
            mutate,
            legacy_path=data_dir / "user_data.json",
            source="broadcast",
            default={},
        )
        return
    users = store.load_document(
        "users", legacy_path=data_dir / "user_data.json", default={}
    )
    mutate(users)
    store.save_document("users", users, legacy_path=data_dir / "user_data.json")


async def send_messages(
    *,
    token: str,
    photo_path: Path,
    data_dir: Path,
    store: OperationalStore,
    analytics: AnalyticsStore,
    history: dict,
    recipients: list[int],
) -> tuple[int, int]:
    bot = Bot(token)
    markup = kb()
    campaign = history.setdefault(
        CAMPAIGN_ID,
        {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bonus": 0,
            "recipients": {},
        },
    )
    records = campaign.setdefault("recipients", {})
    sent = 0
    failed = 0
    file_id = None
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        for index, user_id in enumerate(recipients, start=1):
            key = str(user_id)
            record = records.get(key) if isinstance(records.get(key), dict) else {}
            if record.get("status") == "sent":
                continue
            try:
                if file_id:
                    msg = await bot.send_photo(
                        user_id,
                        file_id,
                        caption=MESSAGE,
                        reply_markup=markup,
                    )
                else:
                    msg = await bot.send_photo(
                        user_id,
                        FSInputFile(photo_path),
                        caption=MESSAGE,
                        reply_markup=markup,
                    )
                    if msg.photo:
                        file_id = msg.photo[-1].file_id
                records[key] = {
                    **record,
                    "status": "sent",
                    "sent_at": now,
                    "chat_id": int(msg.chat.id) if msg.chat else int(user_id),
                    "message_id": int(msg.message_id),
                }
                analytics.track(
                    "broadcast_sent",
                    user_id=user_id,
                    properties={"campaign": CAMPAIGN_ID, "bonus": 0},
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
                    _mark_blocked(store, data_dir, user_id, err_name)
                failed += 1
                if failed <= 20:
                    print(f"fail {user_id}: {type(exc).__name__}: {exc}", flush=True)
            if index % 25 == 0:
                _save_campaign(store, data_dir, history)
                await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(0.05)
            if index % 100 == 0:
                print(
                    f"progress {index}/{len(recipients)} sent={sent} failed={failed}",
                    flush=True,
                )
    finally:
        _save_campaign(store, data_dir, history)
        await bot.session.close()
    return sent, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Broadcast tariffs/support photo (dry-run by default, no bonus)."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("BOT_DATA_DIR") or "/root/tarolog"),
    )
    parser.add_argument("--sample", type=int, default=10)
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
    photo_path = data_dir / "static" / "broadcast_referral_unlim.jpg"
    if not photo_path.is_file():
        photo_path = PHOTO

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
    print("bonus: none")
    print(f"photo: {photo_path} exists={photo_path.is_file()}")
    print(f"caption_len: {len(MESSAGE)}")
    print(f"users in db: {len(users)}")
    print(f"already sent: {len(already_done)}")
    print(f"eligible recipients: {len(recipients)}")
    if recipients:
        sample = ", ".join(str(uid) for uid in recipients[: max(0, int(args.sample))])
        print(f"sample user IDs: {sample}")
    print("\nCaption preview:\n")
    print(MESSAGE)
    print("\nButtons: Открыть бота / Новые расклады / Написать Роксане")

    if not args.send:
        print(
            f"\nNo messages sent. Add --send --confirm {CAMPAIGN_ID} after review."
        )
        return 0
    if args.confirm != CAMPAIGN_ID:
        raise SystemExit(
            f"Refusing to send: --confirm must exactly equal '{CAMPAIGN_ID}'"
        )
    if not photo_path.is_file():
        raise SystemExit(f"Photo missing: {photo_path}")
    if len(MESSAGE) > 1024:
        raise SystemExit(f"Caption too long: {len(MESSAGE)} > 1024")
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
            photo_path=photo_path,
            data_dir=data_dir,
            store=store,
            analytics=analytics,
            history=history,
            recipients=recipients,
        )
    )
    print(f"\nDONE sent={sent} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
