#!/usr/bin/env python3
"""Import all Telegram bot operational JSON files into bot_state.sqlite3."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot_core import OperationalStore


DOCUMENTS = {
    "logs": ("logs.json", []),
    "users": ("user_data.json", {}),
    "grant_state": ("grant_state.json", {}),
    "consultation_leads": ("consultation_leads.json", []),
    "reading_history": ("reading_history.json", {}),
    "user_questions": ("user_questions.json", []),
    "reviews": ("reviews.json", {"items": []}),
    "payment_nurture": ("payment_nurture.json", {}),
    "channel_bonus_status": ("status_data.json", {}),
    "order_number": ("order_number.json", {"order_number": 0}),
    "one_day_card": ("chat_data.json", {}),
    "tomorrow_cards": ("tomorrow_card.json", {}),
    "user_agreements": ("user_agreements.json", {}),
    "admins": ("admins.json", {}),
    "payment_totals": ("payment_data.json", {}),
    "used_promocodes": ("used_promocodes.json", {}),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    database = (args.db or data_dir / "bot_state.sqlite3").resolve()
    store = OperationalStore(database, mirror_json=True)
    for name, (filename, default) in DOCUMENTS.items():
        value = store.load_document(
            name,
            legacy_path=data_dir / filename,
            default=default,
        )
        size = len(value) if hasattr(value, "__len__") else 1
        print(f"{name}: {size}")
    print(f"Database: {database}")
    print(f"Integrity: {store.integrity_check()}")
    for item in store.list_documents():
        print(
            f"{item['name']}: revision={item['revision']} "
            f"bytes={item['bytes']} source={item['source']}"
        )


if __name__ == "__main__":
    main()
