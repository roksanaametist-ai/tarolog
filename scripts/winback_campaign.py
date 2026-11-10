#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, types
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics import AnalyticsStore
from bot_core import (
    OperationalStore,
    build_campaign_payload,
    select_winback_candidates,
    winback_message,
)
from bot_core.attribution import normalize_tracking_code


def _last_activity(database: Path) -> dict[int, datetime]:
    if not database.exists():
        return {}
    with closing(sqlite3.connect(database)) as conn:
        rows = conn.execute(
            """
            SELECT user_id, MAX(occurred_at)
            FROM events
            WHERE user_id IS NOT NULL
              AND event_name NOT LIKE 'admin_%'
            GROUP BY user_id
            """
        ).fetchall()
    output: dict[int, datetime] = {}
    for user_id, raw_at in rows:
        try:
            parsed = datetime.fromisoformat(str(raw_at))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            output[int(user_id)] = parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
    return output


def _load_state(data_dir: Path):
    store = OperationalStore(data_dir / "bot_state.sqlite3")
    users = store.load_document(
        "users", legacy_path=data_dir / "user_data.json", default={}
    )
    agreements = store.load_document(
        "agreements", legacy_path=data_dir / "user_agreements.json", default={}
    )
    nurture = store.load_document(
        "payment_nurture",
        legacy_path=data_dir / "payment_nurture.json",
        default={},
    )
    history = store.load_document(
        "winback_campaigns",
        legacy_path=data_dir / "winback_campaigns.json",
        default={},
    )
    return store, users, agreements, nurture, history


async def _send(
    *,
    token: str,
    data_dir: Path,
    operational_store: OperationalStore,
    analytics: AnalyticsStore,
    users: dict,
    history: dict,
    campaign_id: str,
    segment: str,
    recipients,
) -> tuple[int, int]:
    bot = Bot(token)
    sent = 0
    failed = 0
    try:
        me = await bot.get_me()
        payload = build_campaign_payload(campaign_id)
        link = f"https://t.me/{me.username}?start={payload}"
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="🔮 Вернуться к раскладу", url=link)]
            ]
        )
        campaign = history.setdefault(
            campaign_id,
            {
                "segment": segment,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "recipients": {},
            },
        )
        records = campaign.setdefault("recipients", {})
        for candidate in recipients:
            user_key = str(candidate.user_id)
            try:
                await bot.send_message(
                    candidate.user_id,
                    winback_message(segment),
                    reply_markup=markup,
                )
                records[user_key] = {
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                analytics.track(
                    "winback_sent",
                    user_id=candidate.user_id,
                    properties={"campaign": campaign_id, "segment": segment},
                    dedupe_key=f"winback:{campaign_id}:{candidate.user_id}",
                )
                sent += 1
            except Exception as exc:
                records[user_key] = {
                    "status": "failed",
                    "failed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "error": type(exc).__name__,
                }
                err_name = type(exc).__name__
                err_text = str(exc).lower()
                if (
                    err_name == "TelegramForbiddenError"
                    or "blocked" in err_text
                    or "deactivated" in err_text
                ):
                    user = users.setdefault(user_key, {})
                    if not isinstance(user, dict):
                        user = {}
                        users[user_key] = user
                    user["tg_blocked"] = True
                    user["tg_blocked_at"] = datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    )
                    user["tg_blocked_reason"] = err_name
                failed += 1
            operational_store.save_document(
                "winback_campaigns",
                history,
                legacy_path=data_dir / "winback_campaigns.json",
            )
            await asyncio.sleep(0.11)
    finally:
        operational_store.save_document(
            "users", users, legacy_path=data_dir / "user_data.json"
        )
        await bot.session.close()
    return sent, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan a segmented win-back campaign; dry-run is the default."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("BOT_DATA_DIR") or ROOT),
    )
    parser.add_argument(
        "--segment",
        required=True,
        choices=("inactive", "zero-balance", "lapsed", "checkout-abandoned"),
    )
    parser.add_argument("--inactive-days", type=int, default=14)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--sample", type=int, default=15)
    parser.add_argument("--send", action="store_true")
    parser.add_argument(
        "--confirm",
        help="Required with --send; must exactly match the normalized campaign ID.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(ROOT / ".env")
    args = parse_args()
    data_dir = args.data_dir.resolve()
    campaign_id = normalize_tracking_code(args.campaign_id, field="campaign")
    limit = max(1, min(int(args.limit), 500))
    store, users, agreements, nurture, history = _load_state(data_dir)
    campaign_history = history.get(campaign_id) or {}
    already_sent = {
        int(user_id)
        for user_id, record in (campaign_history.get("recipients") or {}).items()
        if isinstance(record, dict)
        and record.get("status") == "sent"
        and str(user_id).isdigit()
    }
    candidates = select_winback_candidates(
        users=users,
        agreements=agreements,
        nurture=nurture,
        last_activity=_last_activity(data_dir / "analytics.sqlite3"),
        already_sent=already_sent,
        segment=args.segment,
        inactive_days=args.inactive_days,
    )
    selected = candidates[:limit]
    print(f"mode: {'SEND' if args.send else 'DRY-RUN'}")
    print(f"campaign: {campaign_id}")
    print(f"segment: {args.segment}")
    print(f"eligible: {len(candidates)}")
    print(f"selected by limit: {len(selected)}")
    if already_sent:
        print(f"already sent and excluded: {len(already_sent)}")
    if selected:
        sample_ids = ", ".join(
            str(item.user_id) for item in selected[: max(0, int(args.sample))]
        )
        print(f"sample user IDs: {sample_ids}")
    print("\nMessage preview:\n")
    print(winback_message(args.segment))

    if not args.send:
        print("\nNo messages sent. Add --send --confirm", campaign_id, "after review.")
        return 0
    if args.confirm != campaign_id:
        raise SystemExit(
            f"Refusing to send: --confirm must exactly equal '{campaign_id}'"
        )
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        raise SystemExit("Refusing to send: TELEGRAM_TOKEN is missing")
    analytics = AnalyticsStore(data_dir / "analytics.sqlite3")
    sent, failed = asyncio.run(
        _send(
            token=token,
            data_dir=data_dir,
            operational_store=store,
            analytics=analytics,
            users=users,
            history=history,
            campaign_id=campaign_id,
            segment=args.segment,
            recipients=selected,
        )
    )
    print(f"\nsent: {sent}; failed: {failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
