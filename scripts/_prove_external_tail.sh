#!/bin/bash
set -u
TOK=$(grep '^TELEGRAM_TOKEN=' /root/tarolog/.env | cut -d= -f2-)
python3 - <<'PY'
from pathlib import Path
def tok(p, keys):
  if not Path(p).exists(): return None
  for line in Path(p).read_text(errors='ignore').splitlines():
    for k in keys:
      if line.startswith(k+'='):
        return line.split('=',1)[1].strip()
  return None
a=tok('/root/ассистент/.env',['TELEGRAM_BOT_TOKEN','TELEGRAM_TOKEN'])
t=tok('/root/tarolog/.env',['TELEGRAM_TOKEN'])
print('assistant_same', a==t)
print('assistant_ends', (a or '')[-8:])
print('tarolog_ends', (t or '')[-8:])
PY
echo "stopping tarolog..."
systemctl stop tarolog.service
sleep 40
echo "getUpdates after 40s with HSHP bot OFF:"
curl -sS --max-time 20 "https://api.telegram.org/bot${TOK}/getUpdates?timeout=5&limit=1" || true
echo
echo "telegram connections now:"
ss -tnp | grep -E '149\.154|91\.108' || true
ps auxww | grep -E 'main.py|aiogram' | grep -v grep || echo 'no main.py running'
systemctl start tarolog.service
echo "started again"
head -30 /root/tarolog/amvera.yml
