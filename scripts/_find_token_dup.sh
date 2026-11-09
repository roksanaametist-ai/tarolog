#!/bin/bash
TOK=$(grep '^TELEGRAM_TOKEN=' /root/tarolog/.env | cut -d= -f2-)
echo "tarolog token ends ...${TOK: -8}"
echo "=== files containing this bot id ==="
grep -RIn --exclude-dir=venv --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=deploy-backups --exclude-dir=node_modules -l '7848066454' /root /home /opt /etc/systemd 2>/dev/null | head -50
echo "=== assistant token ==="
python3 - <<'PY'
from pathlib import Path
a=Path('/root/ассистент/.env')
t=Path('/root/tarolog/.env')
def get(p, key):
    if not p.exists(): return None
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        if line.startswith(key+'='):
            return line.split('=',1)[1].strip()
    return None
at=get(a,'TELEGRAM_BOT_TOKEN') or get(a,'TELEGRAM_TOKEN')
tt=get(t,'TELEGRAM_TOKEN')
print('same_as_tarolog', bool(at and tt and at==tt))
print('assistant_prefix', (at or '')[:12])
print('tarolog_prefix', (tt or '')[:12])
PY
echo "=== amvera / docker ==="
docker ps 2>/dev/null || true
systemctl list-units --all | grep -iE 'amvera|docker|bot|tar' || true
echo "=== main_kb snippet ==="
grep -n "def main_kb\|Оформить подписку\|PAYMENTS_ENABLED\|button_oplata\|Безлимит за друзей" /root/tarolog/main.py | head -40
sleep 5
journalctl -u tarolog.service -n 12 --no-pager
