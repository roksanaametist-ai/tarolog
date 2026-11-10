#!/usr/bin/env python3
"""Report agree-bonus-15 campaign conversion on prod data."""
from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path

from bot_core.operational_store import OperationalStore

DATA_DIR = Path("/root/tarolog")


def main() -> None:
    store = OperationalStore(DATA_DIR / "bot_state.sqlite3")
    users = store.load_document(
        "users", legacy_path=DATA_DIR / "user_data.json", default={}
    ) or {}
    history = store.load_document(
        "broadcast_campaigns",
        legacy_path=DATA_DIR / "broadcast_campaigns.json",
        default={},
    ) or {}

    camp = history.get("agree-bonus-15") or {}
    recs = camp.get("recipients") or {}
    status_counts: Counter[str] = Counter()
    for record in recs.values():
        if isinstance(record, dict):
            status_counts[str(record.get("status") or "?")] += 1
        else:
            status_counts["bad"] += 1

    claimed = []
    touched = []
    for uid, user in users.items():
        if not isinstance(user, dict):
            continue
        if user.get("agree_bonus_15_claimed"):
            claimed.append((uid, user.get("agree_bonus_15_at")))
        touch = user.get("campaign_touch") or {}
        if isinstance(touch, dict) and str(touch.get("code") or "") in {
            "agree15",
            "agree-bonus-15",
        }:
            touched.append((uid, touch.get("started_at") or touch.get("at")))

    granted_in_camp = sum(
        1
        for record in recs.values()
        if isinstance(record, dict) and (record.get("granted") or record.get("claimed"))
    )

    print("campaign_id: agree-bonus-15")
    for key in ("created_at", "bonus"):
        if key in camp:
            print(f"  {key}: {camp.get(key)}")
    print(f"recipients_total: {len(recs)}")
    print(f"recipient_status: {dict(status_counts)}")
    print(f"users_agree_bonus_15_claimed: {len(claimed)}")
    print(f"users_campaign_touch_agree15: {len(touched)}")
    print(f"campaign_records_granted_flag: {granted_in_camp}")

    by_day: Counter[str] = Counter()
    for _uid, at in claimed:
        by_day[str(at or "")[:10] or "?"] += 1
    print("claimed_by_day:")
    for day, count in sorted(by_day.items()):
        print(f"  {day}: {count}")

    print("sample_claimed_first:")
    for row in sorted(claimed, key=lambda item: str(item[1] or ""))[:8]:
        print(f"  {row}")
    print("sample_claimed_last:")
    for row in sorted(claimed, key=lambda item: str(item[1] or ""))[-8:]:
        print(f"  {row}")

    adb = DATA_DIR / "analytics.sqlite3"
    if not adb.exists():
        return
    con = sqlite3.connect(adb)
    cur = con.cursor()
    cur.execute(
        """
        SELECT event_name, COUNT(*)
        FROM events
        WHERE COALESCE(json_extract(properties_json, '$.campaign'), '') = 'agree-bonus-15'
           OR COALESCE(json_extract(properties_json, '$.code'), '') = 'agree15'
           OR event_name LIKE '%agree%'
        GROUP BY event_name
        ORDER BY COUNT(*) DESC
        LIMIT 20
        """
    )
    print("analytics_agree_related:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]}")
    cur.execute(
        """
        SELECT COUNT(DISTINCT user_id)
        FROM events
        WHERE event_name = 'broadcast_sent'
          AND COALESCE(json_extract(properties_json, '$.campaign'), '') = 'agree-bonus-15'
        """
    )
    print(f"analytics_broadcast_sent_unique: {cur.fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()
