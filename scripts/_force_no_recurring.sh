#!/bin/bash
set -e
python3 - <<'PY'
from pathlib import Path
p = Path("/root/tarolog/bot_core/robokassa.py")
t = p.read_text(encoding="utf-8")
old = 'if recurring:\n        payload["Recurring"] = "true"'
new = 'if False:  # recurring disabled (Robokassa error 34)\n        payload["Recurring"] = "true"'
if old not in t:
    # already patched or different formatting
    t = t.replace('payload["Recurring"] = "true"', '# payload["Recurring"] = "true"  # disabled')
else:
    t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("robokassa.py patched")

env = Path("/root/tarolog/.env")
lines = []
for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
    if line.startswith("ROBOKASSA_RECURRING="):
        lines.append("ROBOKASSA_RECURRING=0")
    else:
        lines.append(line)
env.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("env:", [l for l in lines if l.startswith("ROBOKASSA_RECURRING=")])
PY
systemctl restart tarolog.service
sleep 4
systemctl is-active tarolog.service
grep -n 'Recurring\|if False' /root/tarolog/bot_core/robokassa.py | head -15
