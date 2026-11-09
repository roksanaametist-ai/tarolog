#!/usr/bin/env python3
"""Regression: RAM dump must not wipe an external +N grant."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_core.user_state_merge import merge_user_documents, overlay_wallet_from_disk


def check(name: str, cond: bool) -> None:
    if not cond:
        raise SystemExit(f"FAIL: {name}")
    print("ok", name)


def main() -> None:
    disk = {
        "1": {"questions": 30, "last_activity_at": "old", "subscription_end": None},
        "2": {"questions": 5},
    }
    ram = {
        "1": {"questions": 0, "last_activity_at": "new"},
        "3": {"questions": 5},
    }
    merged = merge_user_documents(disk, ram, dirty_questions=(), dirty_subscription=())
    check("preserve grant", merged["1"]["questions"] == 30)
    check("ram activity wins", merged["1"]["last_activity_at"] == "new")
    check("disk-only kept", merged["2"]["questions"] == 5)
    check("ram-only added", merged["3"]["questions"] == 5)

    spent = merge_user_documents(
        disk, ram, dirty_questions={"1"}, dirty_subscription=()
    )
    check("dirty spend wins", spent["1"]["questions"] == 0)

    ram2 = {"1": {"questions": 0, "last_activity_at": "new"}}
    overlay_wallet_from_disk(ram2, disk, dirty_questions=())
    check("overlay grant into ram", ram2["1"]["questions"] == 30)
    check("overlay keeps activity", ram2["1"]["last_activity_at"] == "new")
    print("all merge tests passed")


if __name__ == "__main__":
    main()
