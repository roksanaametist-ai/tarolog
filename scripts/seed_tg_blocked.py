#!/usr/bin/env python3
"""Seed tg_blocked from past campaign failures (dry-run by default).

Looks at broadcast_campaigns + winback_campaigns recipient records with
status=failed and Forbidden/blocked/deactivated errors.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_core.operational_store import OperationalStore

BLOCK_MARKERS = (
    "telegramforbiddenerror",
    "forbidden",
    "blocked",
    "deactivated",
    "chat not found",
    "peer_id_invalid",
)


def _is_block_error(error: object) -> bool:
    text = str(error or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in BLOCK_MARKERS)


def _iter_failed(campaigns: dict, *, source: str) -> list[tuple[str, str, str]]:
    """Return (user_id, campaign_id, error) for block-like failures."""
    found: list[tuple[str, str, str]] = []
    if not isinstance(campaigns, dict):
        return found
    for campaign_id, campaign in campaigns.items():
        if not isinstance(campaign, dict):
            continue
        recipients = campaign.get("recipients") or {}
        if not isinstance(recipients, dict):
            continue
        for user_id, record in recipients.items():
            if not isinstance(record, dict):
                continue
            if record.get("status") != "failed":
                continue
            error = str(record.get("error") or "")
            if not _is_block_error(error):
                continue
            if not str(user_id).isdigit():
                continue
            found.append((str(user_id), f"{source}:{campaign_id}", error or "failed"))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed tg_blocked from campaign failure history (dry-run default)."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("BOT_DATA_DIR") or "/root/tarolog"),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write tg_blocked flags to users store.",
    )
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()

    store = OperationalStore(data_dir / "bot_state.sqlite3")
    users = store.load_document(
        "users", legacy_path=data_dir / "user_data.json", default={}
    )
    broadcasts = store.load_document(
        "broadcast_campaigns",
        legacy_path=data_dir / "broadcast_campaigns.json",
        default={},
    )
    winbacks = store.load_document(
        "winback_campaigns",
        legacy_path=data_dir / "winback_campaigns.json",
        default={},
    )
    if not isinstance(users, dict):
        users = {}

    candidates = _iter_failed(broadcasts, source="broadcast") + _iter_failed(
        winbacks, source="winback"
    )
    # unique by user, keep first reason
    by_user: dict[str, tuple[str, str]] = {}
    for user_id, source, error in candidates:
        by_user.setdefault(user_id, (source, error))

    already = 0
    to_mark = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for user_id, (source, error) in sorted(by_user.items(), key=lambda x: int(x[0])):
        user = users.get(user_id)
        if not isinstance(user, dict):
            user = {}
            users[user_id] = user
        if user.get("tg_blocked"):
            already += 1
            continue
        to_mark += 1
        if args.apply:
            user["tg_blocked"] = True
            user["tg_blocked_at"] = now
            user["tg_blocked_reason"] = f"seed:{error}"[:80]
            user["tg_blocked_source"] = source[:80]

    print(f"mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"data_dir: {data_dir}")
    print(f"failed block-like recipients found: {len(by_user)}")
    print(f"already tg_blocked: {already}")
    print(f"would mark / marked: {to_mark}")
    if by_user:
        sample = list(by_user.items())[:10]
        print("sample:")
        for user_id, (source, error) in sample:
            print(f"  {user_id}  {source}  {error}")

    if args.apply and to_mark:
        store.save_document(
            "users", users, legacy_path=data_dir / "user_data.json"
        )
        print("saved users store")
    elif not args.apply:
        print("No writes. Re-run with --apply after review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
