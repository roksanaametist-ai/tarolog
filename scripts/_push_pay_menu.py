#!/usr/bin/env python3
import json
import urllib.request
from pathlib import Path

env = Path("/root/tarolog/.env").read_text(encoding="utf-8")
token = ""
for line in env.splitlines():
    if line.startswith("TELEGRAM_TOKEN="):
        token = line.split("=", 1)[1].strip()
        break

kb = {
    "keyboard": [
        [{"text": "\u2753 \u0417\u0430\u0434\u0430\u0442\u044c \u0432\u043e\u043f\u0440\u043e\u0441"}],
        [{"text": "\u041a\u0430\u0440\u0442\u0430 \u0434\u043d\u044f"}, {"text": "\u0414\u0430/\u041d\u0435\u0442"}],
        [{"text": "\U0001f4b3 \u041e\u0444\u043e\u0440\u043c\u0438\u0442\u044c \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0443"}],
        [{"text": "\U0001f465 \u041f\u0440\u0438\u0433\u043b\u0430\u0441\u0438\u0442\u044c \u0434\u0440\u0443\u0433\u0430 (+5)"}],
        [{"text": "\u2728 \u041a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u044f \u044d\u0437\u043e\u0442\u0435\u0440\u0438\u043a\u0430 (\u043f\u043b\u0430\u0442\u043d\u043e)"}],
    ],
    "resize_keyboard": True,
}
payload = {
    "chat_id": 491482483,
    "text": (
        "\u041c\u0435\u043d\u044e \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u043e.\n"
        "\u041d\u0430\u0436\u043c\u0438 \u00ab\U0001f4b3 \u041e\u0444\u043e\u0440\u043c\u0438\u0442\u044c \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0443\u00bb \u043d\u0438\u0436\u0435."
    ),
    "reply_markup": kb,
}
req = urllib.request.Request(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
print(urllib.request.urlopen(req, timeout=20).read().decode("utf-8")[:500])
