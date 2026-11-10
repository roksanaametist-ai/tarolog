#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path

from bot_core.operational_store import OperationalStore

d = Path("/root/tarolog")
s = OperationalStore(d / "bot_state.sqlite3")
users = s.load_document("users", legacy_path=d / "user_data.json", default={}) or {}

ref_by = share_clicks = milestones = 0
sum_ref = sum_active = 0
for u in users.values():
    if not isinstance(u, dict):
        continue
    if u.get("referred_by"):
        ref_by += 1
    sum_ref += int(u.get("referrals_count") or 0)
    sum_active += int(u.get("active_referrals_count") or 0)
    share_clicks += int(u.get("share_clicks") or 0)
    if u.get("referral_milestone_3") or u.get("referral_milestone_10"):
        milestones += 1

print(f"users={len(users)}")
print(f"have_referred_by={ref_by}")
print(f"sum_referrals_count={sum_ref}")
print(f"sum_active_referrals={sum_active}")
print(f"sum_share_clicks={share_clicks}")
print(f"milestone_users={milestones}")

con = sqlite3.connect(d / "analytics.sqlite3")
cur = con.cursor()
cols = [r[1] for r in cur.execute("PRAGMA table_info(events)")]
print("cols", cols)
names = [
    "share_opened",
    "share_forward_prompted",
    "share_card_generated",
    "share_link_started",
    "referral_share_signup",
    "referral_share_activated",
    "user_registered",
    "reading_completed",
    "broadcast_sent",
]
for n in names:
    cur.execute(
        "SELECT COUNT(*), COUNT(DISTINCT user_id) FROM events WHERE event_name=?",
        (n,),
    )
    print(n, cur.fetchone())

if "occurred_at" in cols:
    cur.execute(
        """
        SELECT event_name, COUNT(*), COUNT(DISTINCT user_id)
        FROM events
        WHERE occurred_at >= datetime('now', '-14 days')
          AND event_name IN (
            'share_opened','share_forward_prompted','share_link_started',
            'referral_share_signup','referral_share_activated',
            'user_registered','reading_completed'
          )
        GROUP BY 1 ORDER BY 2 DESC
        """
    )
    print("last_14d:")
    for row in cur.fetchall():
        print(" ", row)
con.close()
