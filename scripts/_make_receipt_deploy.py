"""Generate one-paste VNC deploy script with embedded robokassa.py (base64)."""
from __future__ import annotations

import base64
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "bot_core" / "robokassa.py"
OUT = ROOT / "scripts" / "_deploy_receipt_onepaste.sh"

b64 = base64.b64encode(SRC.read_bytes()).decode("ascii")
chunks = "\n".join(b64[i : i + 76] for i in range(0, len(b64), 76))

script = f"""#!/bin/bash
set -euo pipefail
OUT=/root/tarolog/bot_core/robokassa.py
cp -a "$OUT" "$OUT.bak.$(date +%s)"
base64 -d <<'B64' > "$OUT"
{chunks}
B64
python3 -m py_compile "$OUT"
ENV=/root/tarolog/.env
grep -q '^ROBOKASSA_RECEIPT=' "$ENV" 2>/dev/null || echo 'ROBOKASSA_RECEIPT=1' >> "$ENV"
grep -q '^ROBOKASSA_TAX=' "$ENV" 2>/dev/null || echo 'ROBOKASSA_TAX=none' >> "$ENV"
if grep -q '^ROBOKASSA_RECURRING=' "$ENV" 2>/dev/null; then
  sed -i 's/^ROBOKASSA_RECURRING=.*/ROBOKASSA_RECURRING=0/' "$ENV"
else
  echo 'ROBOKASSA_RECURRING=0' >> "$ENV"
fi
systemctl restart tarolog
systemctl is-active tarolog
grep -n 'Receipt\\|build_receipt' "$OUT" | head -10
echo DONE
"""

OUT.write_text(script, encoding="utf-8", newline="\n")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
