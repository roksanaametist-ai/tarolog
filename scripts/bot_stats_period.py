#!/usr/bin/env python3
"""Prod bot stats from /root/tarolog JSON. Run on VPS or via bot_stats_remote.ps1."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics import AnalyticsStore
from bot_core.operational_store import OperationalStore


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_base(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    for c in (Path("/root/tarolog"), Path("/opt/targpt/data"), Path(".")):
        if any(
            (c / name).exists()
            for name in (
                "analytics.sqlite3",
                "bot_state.sqlite3",
                "logs.json",
                "user_data.json",
            )
        ):
            return c
    raise SystemExit("No data dir with logs.json / user_data.json")


def _print_public_deck_sqlite(counts: dict, unique: dict) -> None:
    print(f"PUBLIC_DECK_PREVIEW\t{counts.get('public_deck_created', 0)}")
    print(f"PUBLIC_DECK_SENT\t{counts.get('public_deck_sent', 0)}")
    print(f"PUBLIC_DECK_OPENED_CHAT\t{counts.get('public_deck_opened_chat', 0)}")
    print(f"PUBLIC_DECK_OPENED_DM\t{counts.get('public_deck_opened_dm', 0)}")
    print(f"PUBLIC_DECK_OPENED\t{counts.get('public_deck_opened', 0)}")
    print(f"PUBLIC_DECK_REOPENED\t{counts.get('public_deck_reopened', 0)}")
    print(f"PUBLIC_DECK_SHUFFLED\t{counts.get('public_deck_shuffled', 0)}")
    print(f"PUBLIC_DECK_OWN\t{counts.get('public_deck_own_spread', 0)}")
    print(f"PUBLIC_DECK_USERS\t{unique.get('public_deck_created', 0)}")
    print(f"PUBLIC_DECK_SENT_USERS\t{unique.get('public_deck_sent', 0)}")


def _entry_context(e: dict, posts: dict) -> str:
    ctx = str(e.get("context") or "").strip().lower()
    if ctx in {"dm", "chat"}:
        return ctx
    post = posts.get(str(e.get("public_card_id") or "")) or {}
    return "chat" if post.get("inline_message_id") else "dm"


def print_sqlite_stats(base: Path, days: int, by_day: bool) -> bool:
    db = base / "analytics.sqlite3"
    if not db.exists():
        return False
    store = AnalyticsStore(db)
    period = store.period(days)
    users = load_json(base / "user_data.json") or {}
    counts = period.get("counts") or {}
    unique = period.get("unique") or {}
    print(f"BASE {base}")
    print(f"SOURCE {db}")
    print(f"PERIOD {period['start']} -> {period['end']} ({days}d)")
    print(f"ACTIVE_USERS\t{period['active_users']}")
    print(f"NEW_USERS\t{unique.get('user_registered', 0)}")
    print(f"SHARED_USERS\t{unique.get('share_opened', 0)}")
    print(f"SHARE_CLICKS\t{counts.get('share_opened', 0)}")
    print(f"SHARE_LINK_STARTS\t{unique.get('share_link_started', 0)}")
    print(f"READINGS\t{counts.get('reading_completed', 0)}")
    print(f"READING_USERS\t{unique.get('reading_completed', 0)}")
    print(f"READING_ERRORS\t{counts.get('reading_failed', 0)}")
    _print_public_deck_sqlite(counts, unique)
    print(f"NEW_REFERRED\t{unique.get('referral_signup', 0)}")
    print(f"NEW_FROM_SHARE\t{unique.get('referral_share_signup', 0)}")
    print(f"USERS_DB\t{len(users)}")
    print(f"EVENTS\t{sum(int(v) for v in counts.values())}")
    if not by_day:
        return True
    print()
    hdr = f"{'Дата':<12} {'Актив':>6} {'Новые':>6} {'Шеры':>6} {'Раскл':>6} {'Событ':>7}"
    print(hdr)
    print("-" * len(hdr))
    for row in store.daily(days):
        print(
            f"{row['date']:<12} {row['active_users']:>6} {row['new_users']:>6} "
            f"{row['share_users']:>6} {row['readings']:>6} {row['events']:>7}"
        )
    print("-" * len(hdr))
    print(
        f"{'Уники ' + str(days) + 'д':<12} {period['active_users']:>6} "
        f"{unique.get('user_registered', 0):>6} {unique.get('share_opened', 0):>6} "
        f"{counts.get('reading_completed', 0):>6} "
        f"{sum(int(v) for v in counts.values()):>7}"
    )
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="TarGPT bot period stats")
    ap.add_argument("--days", type=int, default=14, help="Lookback days (default 14)")
    ap.add_argument("--base", default=None, help="Data directory")
    ap.add_argument("--by-day", action="store_true", help="Print daily table")
    args = ap.parse_args()

    base = resolve_base(args.base)
    if print_sqlite_stats(base, max(1, args.days), args.by_day):
        return
    logs = load_json(base / "logs.json") or []
    users = load_json(base / "user_data.json") or {}
    # reading_history устарел; живой журнал — user_questions.json
    rh = load_json(base / "user_questions.json")
    if rh is None:
        rh = load_json(base / "reading_history.json")

    now = datetime.now()
    start = (now - timedelta(days=max(1, args.days) - 1)).date()
    end = now.date()
    cutoff = start.strftime("%Y-%m-%d")
    day_list = [
        (start + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range((end - start).days + 1)
    ]

    first: dict = {}
    for l in logs:
        uid = l.get("user_id")
        d = str(l.get("date") or "")
        if uid is None or not d:
            continue
        if uid not in first or d < first[uid]:
            first[uid] = d

    period_logs = [l for l in logs if str(l.get("date") or "") >= cutoff]
    active = {l.get("user_id") for l in period_logs if l.get("user_id") is not None}
    new_users = [uid for uid, d in first.items() if d >= cutoff]

    share_users = set()
    for uid, u in users.items():
        # Факт шера: клик «Поделиться». Не путать с last_share_pack (черновик после расклада).
        click_at = str(u.get("last_share_click_at") or "")
        clicks = int(u.get("share_clicks") or 0)
        if clicks <= 0 and not click_at:
            continue
        if click_at >= cutoff or (not click_at and clicks > 0):
            # без даты клика — только в all-time при широком окне не включаем в period
            if click_at >= cutoff:
                share_users.add(uid)

    # readings (user_questions.json = list; legacy reading_history = dict)
    reading_items = []
    if isinstance(rh, list):
        reading_items = rh
    elif isinstance(rh, dict):
        for uid, arr in rh.items():
            if isinstance(arr, list):
                for r in arr:
                    reading_items.append({**r, "_uid": uid})

    readings_period = []
    read_users = set()
    for r in reading_items:
        at = str(r.get("at") or r.get("date") or r.get("created_at") or "")
        if at >= cutoff:
            readings_period.append(r)
            uid = r.get("user_id") or r.get("chat_id") or r.get("_uid")
            if uid is not None:
                read_users.add(uid)

    referred_new = 0
    from_share = 0
    for uid in new_users:
        u = users.get(str(uid)) or users.get(uid) or {}
        if u.get("referred_by") is not None:
            referred_new += 1
            if str(u.get("referral_source") or "ref") == "share":
                from_share += 1

    print(f"BASE {base}")
    print(f"PERIOD {cutoff} -> {now.strftime('%Y-%m-%d %H:%M')} ({args.days}d)")
    print(f"ACTIVE_USERS\t{len(active)}")
    print(f"NEW_USERS\t{len(new_users)}")
    print(f"SHARED_USERS\t{len(share_users)}")
    print(f"READINGS\t{len(readings_period)}")
    print(f"READING_USERS\t{len(read_users)}")
    print(f"NEW_REFERRED\t{referred_new}")
    print(f"NEW_FROM_SHARE\t{from_share}")
    print(f"USERS_DB\t{len(users)}")
    print(f"EVENTS\t{len(period_logs)}")

    # Своя колода — воронка из entries (create/sent/open*), не из сырых posts.
    entries = load_json(base / "public_card_entries.json") or []
    if isinstance(entries, dict):
        entries = list(entries.get("entries") or [])
    posts_raw = load_json(base / "public_card_posts.json") or {}
    posts = (posts_raw.get("posts") or {}) if isinstance(posts_raw, dict) else {}
    deck_by_type: dict = defaultdict(int)
    deck_open_ctx: dict = defaultdict(int)
    deck_users = set()
    sent_users = set()
    for e in entries if isinstance(entries, list) else []:
        at = str(e.get("created_at") or "")
        if at < cutoff:
            continue
        et = str(e.get("entry_type") or "other")
        deck_by_type[et] += 1
        uid = e.get("user_id")
        if uid is not None:
            deck_users.add(uid)
            if et == "sent":
                sent_users.add(uid)
        if et == "open":
            deck_open_ctx[_entry_context(e, posts)] += 1
    print(f"PUBLIC_DECK_PREVIEW\t{deck_by_type.get('create', 0)}")
    print(f"PUBLIC_DECK_SENT\t{deck_by_type.get('sent', 0)}")
    print(f"PUBLIC_DECK_OPENED_CHAT\t{deck_open_ctx.get('chat', 0)}")
    print(f"PUBLIC_DECK_OPENED_DM\t{deck_open_ctx.get('dm', 0)}")
    print(f"PUBLIC_DECK_OPENED\t{deck_by_type.get('open', 0)}")
    print(f"PUBLIC_DECK_REOPENED\t{deck_by_type.get('reopen', 0)}")
    print(f"PUBLIC_DECK_SHUFFLED\t{deck_by_type.get('shuffle', 0)}")
    print(f"PUBLIC_DECK_OWN\t{deck_by_type.get('own_spread', 0)}")
    print(f"PUBLIC_DECK_USERS\t{len(deck_users)}")
    print(f"PUBLIC_DECK_SENT_USERS\t{len(sent_users)}")

    if not args.by_day:
        return

    active_d: dict = defaultdict(set)
    events_d: dict = defaultdict(int)
    for l in period_logs:
        day = str(l.get("date") or "")[:10]
        if day not in day_list:
            continue
        uid = l.get("user_id")
        if uid is not None:
            active_d[day].add(uid)
        events_d[day] += 1

    new_d: dict = defaultdict(set)
    for uid, fs in first.items():
        day = fs[:10]
        if day in day_list:
            new_d[day].add(uid)

    share_d: dict = defaultdict(set)
    for uid, u in users.items():
        day = str(u.get("last_share_click_at") or "")[:10]
        if day in day_list:
            share_d[day].add(uid)

    read_d: dict = defaultdict(int)
    for r in reading_items:
        day = str(r.get("at") or r.get("date") or r.get("created_at") or "")[:10]
        if day in day_list:
            read_d[day] += 1

    print()
    hdr = f"{'Дата':<12} {'Актив':>6} {'Новые':>6} {'Шеры':>6} {'Раскл':>6} {'Событ':>7}"
    print(hdr)
    print("-" * len(hdr))
    for d in day_list:
        print(
            f"{d:<12} {len(active_d[d]):>6} {len(new_d[d]):>6} "
            f"{len(share_d[d]):>6} {read_d[d]:>6} {events_d[d]:>7}"
        )
    print("-" * len(hdr))
    print(
        f"{'Уники ' + str(args.days) + 'д':<12} {len(active):>6} {len(new_users):>6} "
        f"{len(share_users):>6} {len(readings_period):>6} {len(period_logs):>7}"
    )


if __name__ == "__main__":
    main()
