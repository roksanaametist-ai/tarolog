#!/bin/bash
set -u
TOK=$(grep '^TELEGRAM_TOKEN=' /root/tarolog/.env | cut -d= -f2-)
echo "token ...${TOK: -10}"
echo
echo "=== local processes with token / polling ==="
ps auxww | grep -E 'main.py|getUpdates|aiogram|telegram|tarolog|amvera|7848066454' | grep -v grep || true
echo
echo "=== systemd units mentioning tarolog/bot/token ==="
systemctl list-units --all --type=service --no-pager | grep -iE 'tar|bot|gpt|amvera|assist' || true
echo
echo "=== grep token across /root /home /opt /var (paths only) ==="
grep -RIn --exclude-dir=venv --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=deploy-backups --exclude-dir=backups --exclude-dir=.git -l --include='*.env' --include='*.py' --include='*.yml' --include='*.yaml' --include='*.service' --include='*.sh' --include='*.json' '7848066454' /root /home /opt /var/www /etc 2>/dev/null | head -80
echo
echo "=== docker / podman ==="
docker ps -a 2>/dev/null || true
podman ps -a 2>/dev/null || true
echo
echo "=== cron / timers ==="
crontab -l 2>/dev/null || true
ls /etc/cron.* 2>/dev/null | head
systemctl list-timers --all --no-pager | grep -iE 'tar|bot|amvera' || true
echo
echo "=== network listeners python ==="
ss -tnp 2>/dev/null | grep -i python | head -30 || true
echo
echo "=== getUpdates while OUR bot stopped (proves external tail) ==="
systemctl stop tarolog.service
sleep 2
curl -sS --max-time 12 "https://api.telegram.org/bot${TOK}/getUpdates?timeout=3&limit=1" || true
echo
systemctl start tarolog.service
sleep 3
journalctl -u tarolog.service -n 12 --no-pager
echo
echo "=== amvera git remotes / configs ==="
find /root /home -maxdepth 4 \( -name 'amvera.yml' -o -name '.amvera*' -o -name '*amvera*' \) 2>/dev/null | head -40
cd /root/tarolog 2>/dev/null && git remote -v 2>/dev/null || true
echo
echo "=== screen/tmux sessions ==="
screen -ls 2>/dev/null || true
tmux ls 2>/dev/null || true
who
