#!/bin/bash
set -e
ENV=/root/tarolog/.env
cp -a "$ENV" "$ENV.bak-pay-enable-$(date +%Y%m%d%H%M%S)"
python3 - <<'PY'
from pathlib import Path
p = Path("/root/tarolog/.env")
text = p.read_text(encoding="utf-8")
lines = text.splitlines()
out = []
seen = set()
wanted = {
    "PAYMENTS_ENABLED": "1",
    "PAYMENT_PROVIDER": "robokassa",
    "ROBOKASSA_IS_TEST": "0",
    "ROBOKASSA_RECURRING": "1",
}
for line in lines:
    if not line or line.lstrip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    key, _, _ = line.partition("=")
    key = key.strip()
    if key in wanted:
        out.append(f"{key}={wanted[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, val in wanted.items():
    if key not in seen:
        out.append(f"{key}={val}")
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("env updated:")
for k in wanted:
    print(" ", k, "=", wanted[k])
PY
