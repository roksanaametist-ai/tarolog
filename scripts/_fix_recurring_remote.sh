#!/bin/bash
set -e
python3 - <<'PY'
from pathlib import Path
import re
p = Path("/root/tarolog/.env")
text = p.read_text(encoding="utf-8", errors="replace")
new = re.sub(r"(?m)^ROBOKASSA_RECURRING=.*$", "ROBOKASSA_RECURRING=0", text)
p.write_text(new, encoding="utf-8")
print("env ok")
PY
grep '^ROBOKASSA_RECURRING' /root/tarolog/.env
systemctl start tarolog.service || systemctl restart tarolog.service
sleep 4
systemctl is-active tarolog.service
journalctl -u tarolog.service -n 10 --no-pager
