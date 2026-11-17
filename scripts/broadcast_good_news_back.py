#!/usr/bin/env python3
"""Good news: bot is back, +30 readings, Farnsworth photo. Dry-run by default."""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
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

CAMPAIGN_ID = "good-news-back-30"
BONUS = 30
PHOTO = Path("/root/tarolog/static/broadcast_referral_unlim.jpg")
BOT_URL = "https://t.me/Roxanaametist_Taro_bot"
ROXANA_URL = "https://t.me/roxanaametist"

MESSAGE = (
    "Друзья, хорошие новости!\n"
    "\n"
    "Бот-таролог снова в строю!\n"
    "Всем +30 раскладов на счет!\n"
    "\n"
    "Совсем скоро можно будет получить безлимит вопросов "
    "за символическую финансовую поддержку бота, "
    "об этом - в следующей рассылке.\n"
    "\n"
    "Если что-то не работает и есть предложения\\пожелания "
    "по работе бота, пишите в лс гадалочке-Роксаночке: @roxanaametist"
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


def grant_bonus(
    store: OperationalStore,
    data_dir: Path,
    users: dict,
    recipients: list[int],
    history: dict,
) -> int:
    user_data_path = data_dir / "user_data.json"
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    if user_data_path.exists():
        backup = data_dir / f"user_data.backup-good-news-{stamp}.json"
        shutil.copy2(user_data_path, backup)
        print(f"backup: {backup}", flush=True)
    state_db = data_dir / "bot_state.sqlite3"
    if state_db.exists():
        state_backup = data_dir / f"bot_state.backup-good-news-{stamp}.sqlite3"
        shutil.copy2(state_db, state_backup)
        print(f"backup: {state_backup}", flush=True)

    campaign = history.setdefault(
        CAMPAIGN_ID,
        {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bonus": BONUS,
            "recipients": {},
        },
    )
    records = campaign.setdefault("recipients", {})
    granted = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for user_id in recipients:
        key = str(user_id)
        record = records.get(key) if isinstance(records.get(key), dict) else {}
        if record.get("granted"):
            continue
        user = users.setdefault(key, {})
        if not isinstance(user, dict):
            user = {}
            users[key] = user
        try:
            questions = int(user.get("questions", 0) or 0)
        except (TypeError, ValueError):
            questions = 0
        user["questions"] = questions + BONUS
        records[key] = {
            **record,
            "granted": True,
            "granted_at": now,
            "bonus": BONUS,
            "balance_after": user["questions"],
        }
        granted += 1

    store.save_document("users", users, legacy_path=user_data_path)
    store.save_document(
        "broadcast_campaigns",
        history,
        legacy_path=data_dir / "broadcast_campaigns.json",
    )
    return granted


def kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔮 Открыть бота", url=BOT_URL)],
            [
                InlineKeyboardButton(
                    text="✍️ Написать Роксане",
                    url=ROXANA_URL,
                )
            ],
        ]
    )


async def send_messages(
    *,
    token: str,
    photo_path: Path,
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
    markup = kb()
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
                    await bot.send_photo(
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
        description="Broadcast good-news photo and +30 (dry-run by default)."
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
        and (record.get("status") == "sent" or record.get("granted"))
    }
    recipients = select_recipients(users, already_done)

    print(f"mode: {'SEND' if args.send else 'DRY-RUN'}")
    print(f"campaign: {CAMPAIGN_ID}")
    print(f"bonus: +{BONUS}")
    print(f"photo: {photo_path} exists={photo_path.is_file()}")
    print(f"users in db: {len(users)}")
    print(f"already done: {len(already_done)}")
    print(f"eligible recipients: {len(recipients)}")
    if recipients:
        sample = ", ".join(str(uid) for uid in recipients[: max(0, int(args.sample))])
        print(f"sample user IDs: {sample}")
    print("\nCaption preview:\n")
    print(MESSAGE)
    print("\nButtons: Открыть бота / Написать Роксане")

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
    token = (
        os.getenv("TELEGRAM_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()
    if not token:
        raise SystemExit("Refusing to send: TELEGRAM_TOKEN is missing")

    granted = grant_bonus(store, data_dir, users, recipients, history)
    print(f"granted +{BONUS} to {granted} users", flush=True)
    analytics = AnalyticsStore(data_dir / "analytics.sqlite3")
    sent, failed = asyncio.run(
        send_messages(
            token=token,
            photo_path=photo_path,
            data_dir=data_dir,
            store=store,
            analytics=analytics,
            history=history,
            users=users,
            recipients=recipients,
        )
    )
    print(f"\nDONE sent={sent} failed={failed} granted={granted}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
