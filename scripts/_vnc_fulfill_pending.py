#!/usr/bin/env python3
"""Run on DE VPS: list recent Robokassa invoices and fulfill unpaid/pending ones."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path("/root/tarolog")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.setdefault("BOT_DATA_DIR", str(ROOT))
os.environ.setdefault("LANDING_DATA_DIR", str(ROOT))

inv_path = ROOT / "robokassa_invoices.json"
if not inv_path.exists():
    # try data subdir
    alt = ROOT / "data" / "robokassa_invoices.json"
    inv_path = alt if alt.exists() else inv_path

print("invoice_file", inv_path, "exists", inv_path.exists())
if not inv_path.exists():
    raise SystemExit("no robokassa_invoices.json")

data = json.loads(inv_path.read_text(encoding="utf-8"))
invoices = data.get("invoices") or {}
rows = []
for k, v in invoices.items():
    if isinstance(v, dict):
        rows.append((int(k), v))
rows.sort(key=lambda x: x[0], reverse=True)

print("--- last 20 invoices ---")
for inv_id, v in rows[:20]:
    print(
        inv_id,
        v.get("status"),
        v.get("plan_key"),
        "chat",
        v.get("chat_id"),
        "fulfilled",
        v.get("fulfilled"),
        "amt",
        v.get("amount_kopecks"),
        v.get("created_at"),
    )

need = [
    (i, v)
    for i, v in rows
    if v.get("status") != "paid" or not v.get("fulfilled")
]
print("need_fulfill", [i for i, _ in need[:10]])

from bot_core.robokassa_fulfill import fulfill_invoice

for inv_id, v in need[:10]:
    print("fulfilling", inv_id, v.get("chat_id"), v.get("plan_key"))
    r = fulfill_invoice(inv_id)
    print(" ->", r)

print("DONE_FULFILL")
