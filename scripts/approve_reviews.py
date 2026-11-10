#!/usr/bin/env python3
"""Approve pending reviews by id (prod one-shot)."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aiogram import Bot
from bot_core.operational_store import OperationalStore


def load_items(store: OperationalStore, data_dir: Path) -> tuple[dict | list, list]:
    raw = store.load_document(
        "reviews", legacy_path=data_dir / "reviews.json", default={"items": []}
    )
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        items = [x for x in raw["items"] if isinstance(x, dict)]
        return raw, items
    if isinstance(raw, list):
        items = [x for x in raw if isinstance(x, dict)]
        return {"items": items}, items
    return {"items": []}, []


async def notify(token: str, user_ids: list[int]) -> None:
    bot = Bot(token)
    try:
        for uid in user_ids:
            try:
                await bot.send_message(
                    uid, "Ваш отзыв опубликован в ленте. Спасибо ещё раз! ❤️"
                )
                print(f"notified {uid}")
            except Exception as exc:
                print(f"notify fail {uid}: {type(exc).__name__}: {exc}")
    finally:
        await bot.session.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("/root/tarolog"))
    parser.add_argument("--ids", nargs="+", type=int, required=True)
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    load_dotenv(data_dir / ".env")

    store = OperationalStore(data_dir / "bot_state.sqlite3")
    wrapper, items = load_items(store, data_dir)
    approved_users: list[int] = []
    for rid in args.ids:
        item = next((x for x in items if int(x.get("id") or 0) == rid), None)
        if not item:
            print(f"missing #{rid}")
            continue
        old = item.get("status")
        item["status"] = "approved"
        print(f"#{rid}: {old} -> approved | user={item.get('user_id')}")
        try:
            approved_users.append(int(item["user_id"]))
        except (TypeError, ValueError, KeyError):
            pass

    if isinstance(wrapper, dict):
        wrapper["items"] = items
        store.save_document(
            "reviews", wrapper, legacy_path=data_dir / "reviews.json"
        )
    else:
        store.save_document(
            "reviews", {"items": items}, legacy_path=data_dir / "reviews.json"
        )
    print("saved")

    if args.notify and approved_users:
        token = (os.getenv("TELEGRAM_TOKEN") or "").strip()
        if not token:
            print("TELEGRAM_TOKEN missing, skip notify")
            return 0
        asyncio.run(notify(token, approved_users))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
