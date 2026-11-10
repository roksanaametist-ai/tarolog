#!/usr/bin/env python3
"""Backfill analytics.sqlite3 from the bot's existing JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics import AnalyticsStore


def load(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    db_path = (args.db or data_dir / "analytics.sqlite3").resolve()
    store = AnalyticsStore(db_path)
    counts = store.backfill_legacy(
        logs=load(data_dir / "logs.json", []),
        readings=load(data_dir / "user_questions.json", []),
        users=load(data_dir / "user_data.json", {}),
        payment_data=load(data_dir / "payment_data.json", {}),
    )
    print(f"Database: {db_path}")
    for key, value in sorted(counts.items()):
        print(f"{key}: {value}")
    snapshot = store.snapshot()
    print("Today active:", snapshot["periods"]["today"]["active_users"])
    print("7d readings:", snapshot["periods"]["7d"]["counts"].get("reading_completed", 0))


if __name__ == "__main__":
    main()
