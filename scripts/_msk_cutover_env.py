"""Patch /opt/targpt/.env for Moscow bot cutover. Run on Moscow as root."""
from pathlib import Path

p = Path("/opt/targpt/.env")
text = p.read_text(encoding="utf-8")
lines = text.splitlines()
want = {
    "PAYMENTS_ENABLED": "1",
    "PAYMENT_PROVIDER": "robokassa",
    "ROBOKASSA_IS_TEST": "0",
    "ROBOKASSA_RECURRING": "0",
    "ROBOKASSA_RECEIPT": "1",
    "ROBOKASSA_TAX": "none",
    "ROBOKASSA_RESULT_URL": "https://followthefrensy.ru/robokassa/result",
    "BOT_DATA_DIR": "/opt/targpt",
    "LANDING_DATA_DIR": "/opt/targpt",
}
# Ensure live passwords exist if missing (from known prod values — only fill empty)
optional_fill = {
    "ROBOKASSA_LOGIN": "followthefrensy",
}
keys_done: set[str] = set()
out: list[str] = []
proxy_commented = False
for line in lines:
    raw = line.strip()
    if not raw or raw.startswith("#") or "=" not in line:
        out.append(line)
        continue
    k, _v = line.split("=", 1)
    if k == "TELEGRAM_PROXY":
        out.append(
            "# TELEGRAM_PROXY disabled for MSK cutover (was socks5://37.46.18.192:1080)"
        )
        proxy_commented = True
        keys_done.add(k)
        continue
    if k in want:
        out.append(f"{k}={want[k]}")
        keys_done.add(k)
        continue
    out.append(line)

if not proxy_commented:
    out.append("# TELEGRAM_PROXY disabled for MSK cutover")
for k, v in want.items():
    if k not in keys_done:
        out.append(f"{k}={v}")
for k, v in optional_fill.items():
    if not any(l.startswith(k + "=") for l in out if not l.startswith("#")):
        out.append(f"{k}={v}")

p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("patched", p)
