#!/usr/bin/env python3
"""Tech-support dump for one user or a campaign wipe check.

  python scripts/support_user.py 651339619
  python scripts/support_user.py @Naskillah
  python scripts/support_user.py --campaign good-news-back-30
"""
from __future__ import annotations

import argparse
import json
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


def load_store(data_dir: Path) -> tuple[OperationalStore, dict, dict, list, list]:
    store = OperationalStore(data_dir / "bot_state.sqlite3")
    users = store.load_document("users", legacy_path=data_dir / "user_data.json", default={})
    campaigns = store.load_document(
        "broadcast_campaigns",
        legacy_path=data_dir / "broadcast_campaigns.json",
        default={},
    )
    logs = store.load_document("logs", legacy_path=data_dir / "logs.json", default=[])
    questions = store.load_document(
        "user_questions", legacy_path=data_dir / "user_questions.json", default=[]
    )
    if not isinstance(users, dict):
        users = {}
    if not isinstance(campaigns, dict):
        campaigns = {}
    if not isinstance(logs, list):
        logs = []
    if not isinstance(questions, list):
        questions = []
    return store, users, campaigns, logs, questions


def find_by_username(users: dict, nick: str) -> list[str]:
    want = nick.lower().lstrip("@")
    hits = []
    for uid, rec in users.items():
        if not isinstance(rec, dict):
            continue
        got = str(rec.get("username") or "").lower().lstrip("@")
        if got == want:
            hits.append(str(uid))
    return hits


def campaign_hits(campaigns: dict, uid: str) -> list[str]:
    lines = []
    for cid, camp in campaigns.items():
        if not isinstance(camp, dict):
            continue
        recs = camp.get("recipients") or {}
        rec = recs.get(uid) if isinstance(recs, dict) else None
        if not isinstance(rec, dict):
            continue
        bonus = rec.get("bonus")
        after = rec.get("balance_after")
        granted = rec.get("granted")
        restored = rec.get("restored_at")
        q_note = ""
        lines.append(
            f"  {cid}: granted={granted} bonus={bonus} after={after} "
            f"restored={restored} sent={rec.get('status')} {q_note}"
        )
    return lines


def wipe_heuristic(q: int, rec: dict) -> str:
    if not rec.get("granted"):
        return ""
    after = _int(rec.get("balance_after"))
    bonus = _int(rec.get("bonus"))
    if bonus <= 0:
        return ""
    delta = after - q
    if delta >= bonus:
        return f"WIPE? q={q} after={after} delta={delta} (grant {bonus} missing)"
    if 0 < delta < bonus:
        return f"spent {delta} of grant (ok unless user disputes)"
    return "matches grant"


def dump_user(
    uid: str,
    users: dict,
    campaigns: dict,
    logs: list,
    questions: list,
    analytics_path: Path,
) -> None:
    rec = users.get(uid) if isinstance(users.get(uid), dict) else None
    if rec is None:
        print(f"USER {uid}: not in store")
        return
    q = _int(rec.get("questions"))
    print(f"USER {uid}")
    print(f"  questions={q}")
    print(f"  username={rec.get('username')!r} first_reading={rec.get('first_reading_done')}")
    print(f"  last_activity_at={rec.get('last_activity_at')}")
    print(f"  last_refill_at={rec.get('last_refill_at')}")
    print(f"  unlim={rec.get('subscription_end')} source={rec.get('unlim_source')}")
    print(
        f"  referred_by={rec.get('referred_by')} referrals={rec.get('referrals_count')} "
        f"active={rec.get('active_referrals_count')}"
    )
    print(
        f"  join_bonus_day={rec.get('referral_join_bonus_day')} "
        f"count={rec.get('referral_join_bonus_count')}"
    )
    print(f"  first_start_payload={rec.get('first_start_payload')!r}")

    print("CAMPAIGNS")
    hits = campaign_hits(campaigns, uid)
    if not hits:
        print("  (none)")
    else:
        for line in hits:
            print(line)
        for cid, camp in campaigns.items():
            if not isinstance(camp, dict):
                continue
            recs = camp.get("recipients") or {}
            row = recs.get(uid) if isinstance(recs, dict) else None
            if isinstance(row, dict) and row.get("granted"):
                print(f"  {cid} {wipe_heuristic(q, row)}")

    print("INVITEES (referred_by this user)")
    n = 0
    for other, urec in users.items():
        if not isinstance(urec, dict):
            continue
        if _int(urec.get("referred_by")) != _int(uid):
            continue
        n += 1
        print(
            f"  {other} acq={urec.get('acquired_at')} payload={urec.get('first_start_payload')} "
            f"read={urec.get('first_reading_done')} q={urec.get('questions')}"
        )
    if n == 0:
        print("  (none)")

    print("LAST LOGS")
    mine = [x for x in logs if isinstance(x, dict) and str(x.get("user_id")) == uid]
    for x in mine[-12:]:
        print(f"  {x.get('date')} {str(x.get('command') or '')[:120]}")
    if not mine:
        print("  (none)")

    print("LAST QUESTIONS")
    mine_q = [
        x
        for x in questions
        if isinstance(x, dict) and str(x.get("user_id") or "") == uid
    ]
    for x in mine_q[-8:]:
        print(f"  {x.get('at')} {x.get('kind')} {str(x.get('question') or '')[:80]}")
    if not mine_q:
        print("  (none)")

    if analytics_path.exists():
        print("ANALYTICS last 12")
        con = sqlite3.connect(str(analytics_path))
        rows = con.execute(
            "SELECT occurred_at, event_name, properties FROM events "
            "WHERE user_id=? ORDER BY occurred_at DESC LIMIT 12",
            (_int(uid),),
        ).fetchall()
        for row in rows:
            print(f"  {row[0]} {row[1]} {str(row[2] or '')[:100]}")
        if not rows:
            print("  (none)")


def dump_campaign(campaigns: dict, users: dict, campaign_id: str) -> None:
    camp = campaigns.get(campaign_id)
    if not isinstance(camp, dict):
        print(f"campaign {campaign_id}: missing")
        print("known:", ", ".join(sorted(str(k) for k in campaigns)[:30]))
        return
    recs = camp.get("recipients") or {}
    bonus = _int(camp.get("bonus"))
    wiped = []
    spent = []
    ok = 0
    granted = 0
    for uid, rec in recs.items() if isinstance(recs, dict) else []:
        if not isinstance(rec, dict) or not rec.get("granted"):
            continue
        granted += 1
        after = _int(rec.get("balance_after"))
        b = _int(rec.get("bonus") or bonus)
        user = users.get(uid) if isinstance(users.get(uid), dict) else {}
        q = _int(user.get("questions"))
        delta = after - q
        if b and delta >= b:
            wiped.append((uid, q, after, delta, rec.get("restored_at")))
        elif 0 < delta < b:
            spent.append((uid, q, after, delta))
        else:
            ok += 1
    print(f"CAMPAIGN {campaign_id} bonus={bonus}")
    print(f"  granted={granted} match_or_higher={ok} partial_spend={len(spent)} missing_grant={len(wiped)}")
    print("  WIPE candidates (q <= after-bonus):")
    if not wiped:
        print("    (none)")
    for row in wiped[:40]:
        print(f"    uid={row[0]} q={row[1]} after={row[2]} delta={row[3]} restored={row[4]}")
    if len(wiped) > 40:
        print(f"    … +{len(wiped) - 40}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tech-support user / campaign dump")
    parser.add_argument("target", nargs="?", help="telegram user id or @username")
    parser.add_argument("--campaign", help="audit a broadcast campaign for wiped grants")
    parser.add_argument(
        "--data-dir",
        default="/root/tarolog",
        help="prod data dir (default /root/tarolog)",
    )
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    _, users, campaigns, logs, questions = load_store(data_dir)
    analytics_path = data_dir / "analytics.sqlite3"

    if args.campaign:
        dump_campaign(campaigns, users, args.campaign)
        if not args.target:
            return

    if not args.target:
        parser.error("user id / @username or --campaign required")

    target = str(args.target).strip()
    if target.startswith("@"):
        hits = find_by_username(users, target)
        if not hits:
            print(f"username {target}: not stored on user records (resolve via Telegram /who)")
            return
        for uid in hits:
            dump_user(uid, users, campaigns, logs, questions, analytics_path)
        return
    dump_user(target, users, campaigns, logs, questions, analytics_path)


if __name__ == "__main__":
    main()
