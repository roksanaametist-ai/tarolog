#!/bin/bash
# Paste in HSHP VNC as root. Deploys Receipt-enabled robokassa.py from base64.
set -euo pipefail
B64_FILE=/tmp/robokassa.b64
OUT=/root/tarolog/bot_core/robokassa.py
cp -a "$OUT" "${OUT}.bak.$(date +%s)"
# After this line: paste ONE line of base64 into the file, then Ctrl+D
echo "Paste base64 now, then Ctrl+D:"
cat > "$B64_FILE"
base64 -d "$B64_FILE" > "$OUT"
python3 -m py_compile "$OUT"
grep -n 'Receipt\|build_receipt\|ROBOKASSA_RECEIPT' "$OUT" | head -20
# ensure tax default in .env if missing
ENV=/root/tarolog/.env
grep -q '^ROBOKASSA_RECEIPT=' "$ENV" 2>/dev/null || echo 'ROBOKASSA_RECEIPT=1' >> "$ENV"
grep -q '^ROBOKASSA_TAX=' "$ENV" 2>/dev/null || echo 'ROBOKASSA_TAX=none' >> "$ENV"
grep -q '^ROBOKASSA_RECURRING=' "$ENV" && sed -i 's/^ROBOKASSA_RECURRING=.*/ROBOKASSA_RECURRING=0/' "$ENV" || echo 'ROBOKASSA_RECURRING=0' >> "$ENV"
systemctl restart tarolog
systemctl is-active tarolog
echo DONE
