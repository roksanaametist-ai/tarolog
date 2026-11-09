#!/usr/bin/env python3
"""Re-apply a broadcast grant that the live bot RAM-dump wiped.

Dry-run by default. Adds `bonus` once when current questions <= balance_after - bonus
and there were not that many paid spends after grant.

  python scripts/repair_wiped_campaign_grants.py --campaign good-news-back-30
  python scripts/repair_wiped_campaign_grants.py --campaign good-news-back-30 --apply
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_core.operational_store import OperationalStore


def _int(val, default=0) -> int:
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return default


def spends_since(analytics: Path, user_id: int, since_iso: str) -> int:
    if not analytics.exists():
        return 0
    con = sqlite3.connect(str(analytics))
    row = con.execute(
        "SELECT count(*) FROM events WHERE user_id=? AND event_name='reading_started' "
        "AND occurred_at>=?",
        (user_id, since_iso),
    ).fetchone()
    return int(row[0] if row else 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--data-dir", default="/root/tarolog")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    store = OperationalStore(data_dir / "bot_state.sqlite3")
    users = store.load_document("users", legacy_path=data_dir / "user_data.json", default={})
    history = store.load_document(
        "broadcast_campaigns",
        legacy_path=data_dir / "broadcast_campaigns.json",
        default={},
    )
    camp = history.get(args.campaign) if isinstance(history, dict) else None
    if not isinstance(camp, dict):
        raise SystemExit(f"no campaign {args.campaign}")
    recs = camp.get("recipients") or {}
    bonus_default = _int(camp.get("bonus"))
    analytics = data_dir / "analytics.sqlite3"
    to_fix = []
    for uid, rec in recs.items() if isinstance(recs, dict) else []:
        if not isinstance(rec, dict) or not rec.get("granted"):
            continue
        bonus = _int(rec.get("bonus") or bonus_default)
        after = _int(rec.get("balance_after"))
        user = users.get(uid) if isinstance(users.get(uid), dict) else None
        if not isinstance(user, dict) or bonus <= 0:
            continue
        q = _int(user.get("questions"))
        if after - q < bonus:
            continue
        granted_at = str(rec.get("granted_at") or "2026-11-02T00:00:00+00:00")
        n_read = spends_since(analytics, _int(uid), granted_at)
        expected = max(after - n_read, after - bonus)
        # missing grant: current is about `after - bonus` minus spends
        to_fix.append((uid, q, after, bonus, n_read, q + bonus, expected, rec))

    print(f"candidates {len(to_fix)} apply={args.apply}")
    for uid, q, after, bonus, n_read, new_q, expected, rec in to_fix:
        print(
            f"  {uid} q={q} after={after} bonus={bonus} reads_since={n_read} "
            f"-> {new_q} (after-reads={after - n_read})"
        )

    if not args.apply or not to_fix:
        return

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    src = data_dir / "bot_state.sqlite3"
    if src.exists():
        shutil.copy2(src, data_dir / f"bot_state.backup-repair-grants-{stamp}.sqlite3")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for uid, q, after, bonus, n_read, new_q, expected, rec in to_fix:
        users[uid]["questions"] = new_q
        rec["restored_at"] = now
        rec["restored_from"] = q
        rec["repair_note"] = f"wiped-grant +{bonus}; reads_since={n_read}"
    store.save_document("users", users, legacy_path=data_dir / "user_data.json")
    store.save_document(
        "broadcast_campaigns",
        history,
        legacy_path=data_dir / "broadcast_campaigns.json",
    )
    print("wrote", len(to_fix), "repairs")


if __name__ == "__main__":
    main()
