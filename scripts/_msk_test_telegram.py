#!/usr/bin/env python3
import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/opt/targpt/.env")
token = (os.getenv("TELEGRAM_TOKEN") or "").strip()
print("TELEGRAM_PROXY env:", repr(os.getenv("TELEGRAM_PROXY")))
print("token_set:", bool(token))

for url, label in [
    ("https://api.telegram.org/", "api_root"),
    (f"https://api.telegram.org/bot{token}/getMe", "getMe") if token else (None, None),
]:
    if not url:
        continue
    try:
        with urllib.request.urlopen(url, timeout=12) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(label, "http", resp.status, "len", len(body))
            if label == "getMe":
                data = json.loads(body)
                print("ok", data.get("ok"), "bot", (data.get("result") or {}).get("username"))
    except Exception as exc:
        print(label, "FAIL", type(exc).__name__, exc)
