#!/usr/bin/env python3
"""Grant +20 readings and ask for a review. Dry-run by default."""
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

CAMPAIGN_ID = "review-gift-20"
BONUS = 20
DEEP_LINK = "https://t.me/Roxanaametist_Taro_bot?start=c_review-gift"

MESSAGE = (
    "✨ Небольшой подарок для вас\n\n"
    f"На ваш баланс уже начислено +{BONUS} раскладов — "
    "можно сразу задать вопрос картам.\n\n"
    "Если бот вам помогает, пожалуйста, оставьте короткий честный отзыв. "
    "Это очень поддерживает проект и помогает другим людям найти нас.\n\n"
    "Нажмите кнопку ниже — откроется форма отзыва.\n\n"
    "Отключить такие сообщения: /unsubscribe"
)


def _load(data_dir: Path):
    store = OperationalStore(data_dir / "bot_state.sqlite3")
    users = store.load_document(
        "users", legacy_path=data_dir / "user_data.json", default={}
    )
    agreements = store.load_document(
        "agreements", legacy_path=data_dir / "user_agreements.json", default={}
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
        if not bool(agreements.get(str(user_id))):
            continue
        user = raw_user if isinstance(raw_user, dict) else {}
        if bool(user.get("marketing_opt_out")):
            continue
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
) -> tuple[dict, int]:
    user_data_path = data_dir / "user_data.json"
    if user_data_path.exists():
        backup = data_dir / (
            f"user_data.backup-review-gift-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        )
        shutil.copy2(user_data_path, backup)
        print(f"backup: {backup}", flush=True)

    state_db = data_dir / "bot_state.sqlite3"
    if state_db.exists():
        state_backup = data_dir / (
            f"bot_state.backup-review-gift-{datetime.now().strftime('%Y%m%d%H%M%S')}.sqlite3"
        )
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
            "granted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
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
    return users, granted


async def send_messages(
    *,
    token: str,
    data_dir: Path,
    store: OperationalStore,
    analytics: AnalyticsStore,
    history: dict,
    recipients: list[int],
) -> tuple[int, int]:
    bot = Bot(token)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Оставить отзыв", url=DEEP_LINK)],
            [
                InlineKeyboardButton(
                    text="🔮 Открыть бота",
                    url="https://t.me/Roxanaametist_Taro_bot",
                )
            ],
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
    try:
        for index, user_id in enumerate(recipients, start=1):
            key = str(user_id)
            record = records.get(key) if isinstance(records.get(key), dict) else {}
            if record.get("status") == "sent":
                continue
            try:
                await bot.send_message(user_id, MESSAGE, reply_markup=kb)
                records[key] = {
                    **record,
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    ),
                }
                analytics.track(
                    "broadcast_sent",
                    user_id=user_id,
                    properties={"campaign": CAMPAIGN_ID, "bonus": BONUS},
                    dedupe_key=f"broadcast:{CAMPAIGN_ID}:{user_id}",
                )
                analytics.track(
                    "campaign_bonus_granted",
                    user_id=user_id,
                    properties={"campaign": CAMPAIGN_ID, "bonus": BONUS},
                    dedupe_key=f"bonus:{CAMPAIGN_ID}:{user_id}",
                )
                sent += 1
            except Exception as exc:
                records[key] = {
                    **record,
                    "status": "failed",
                    "failed_at": datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    ),
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
                    user["tg_blocked_at"] = datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    )
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
        store.save_document(
            "users", users, legacy_path=data_dir / "user_data.json"
        )
        store.save_document(
            "broadcast_campaigns",
            history,
            legacy_path=data_dir / "broadcast_campaigns.json",
        )
        await bot.session.close()
    return sent, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Grant +20 readings and ask for a review (dry-run by default)."
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

    print(f"mode: {'SEND' if args.send else 'DRY-RUN'}")
    print(f"campaign: {CAMPAIGN_ID}")
    print(f"bonus: +{BONUS}")
    print(f"users in db: {len(users)}")
    print(f"agreements: {sum(1 for v in agreements.values() if v)}")
    print(f"already done / excluded: {len(already_done)}")
    print(f"eligible recipients: {len(recipients)}")
    if recipients:
        sample = ", ".join(str(uid) for uid in recipients[: max(0, int(args.sample))])
        print(f"sample user IDs: {sample}")
    print("\nMessage preview:\n")
    print(MESSAGE)
    print(f"\nDeep link: {DEEP_LINK}")

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

    users, granted = grant_bonus(store, data_dir, users, recipients, history)
    print(f"granted +{BONUS} to {granted} users", flush=True)
    analytics = AnalyticsStore(data_dir / "analytics.sqlite3")
    sent, failed = asyncio.run(
        send_messages(
            token=token,
            data_dir=data_dir,
            store=store,
            analytics=analytics,
            history=history,
            recipients=recipients,
        )
    )
    print(f"\nDONE sent={sent} failed={failed} granted={granted}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
