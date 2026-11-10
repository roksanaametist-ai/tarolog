#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from bot_core.operational_store import OperationalStore

DATA_DIR = Path("/root/tarolog")


def main() -> None:
    store = OperationalStore(DATA_DIR / "bot_state.sqlite3")
    raw = store.load_document(
        "reviews", legacy_path=DATA_DIR / "reviews.json", default={"items": []}
    )
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        items = [x for x in raw["items"] if isinstance(x, dict)]
    elif isinstance(raw, list):
        items = [x for x in raw if isinstance(x, dict)]
    else:
        items = []

    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "?")
        counts[status] = counts.get(status, 0) + 1

    pending = [x for x in items if str(x.get("status") or "") == "pending"]
    print(f"total_reviews: {len(items)}")
    print(f"status_counts: {counts}")
    print(f"pending_count: {len(pending)}")
    print("---")
    for item in sorted(pending, key=lambda row: int(row.get("id") or 0)):
        rid = item.get("id")
        uid = item.get("user_id")
        stars = item.get("stars")
        at = item.get("at") or item.get("created_at")
        uname = item.get("username") or ""
        text = str(item.get("text") or "").replace("\n", " ").strip()
        if len(text) > 300:
            text = text[:297] + "..."
        print(f"#{rid} | user={uid} @{uname} | {stars}* | {at}")
        print(f"  {text}")
        print()


if __name__ == "__main__":
    main()
