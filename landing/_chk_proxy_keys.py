from pathlib import Path
import os

p = Path(os.environ.get("ENV_PATH", "/opt/targpt/.env"))
t = p.read_text(encoding="utf-8", errors="replace")
keys = []
for line in t.splitlines():
    if not line or line.startswith("#") or "=" not in line:
        continue
    k = line.split("=", 1)[0]
    if any(x in k.upper() for x in ("PROXY", "SOCKS", "AIOHTTP", "TELEGRAM_PROXY", "HTTP", "HTTPS")):
        keys.append(k)
print("proxy_related_keys", keys)
print("has_token", any(l.startswith("TELEGRAM_TOKEN=") for l in t.splitlines()))
