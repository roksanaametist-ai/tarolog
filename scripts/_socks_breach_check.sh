#!/bin/bash
set -e
echo "=== listening ports (what SOCKS clients could hit via 127.0.0.1) ==="
ss -tlnp | awk 'NR==1 || /LISTEN/'
echo
echo "=== auth services without password risk surface ==="
ss -tlnp | grep -E ':(6379|5432|3306|27017|9200|11211|5672|15672|8080|8000|5000|3000|5433)\s' || echo "no classic DB/admin ports open"
echo
echo "=== SSH recent successful logins ==="
last -ai | head -20
echo
echo "=== SSH failed (sample) ==="
journalctl -u ssh -u sshd --since "14 days ago" -g "Failed|Invalid|Accepted" --no-pager 2>/dev/null | tail -30 || grep -E "Failed|Accepted|Invalid" /var/log/auth.log 2>/dev/null | tail -30
echo
echo "=== who can reach bot .env / readable by others ==="
ls -la /root/tarolog/.env /root/tarolog/main.py 2>/dev/null
stat -c '%a %U:%G %n' /root/tarolog/.env 2>/dev/null
echo
echo "=== pproxy only listen? (no -r upstream) ==="
systemctl cat tg-socks.service 2>/dev/null | grep ExecStart
echo
echo "=== unexpected root processes / cron ==="
crontab -l 2>/dev/null | head -20
ls /etc/cron.d/ 2>/dev/null
echo
echo "=== recent modified in /root (suspicious) ==="
find /root -maxdepth 2 -type f -mtime -14 ! -path '*/venv/*' ! -path '*/backups/*' ! -path '*/__pycache__/*' 2>/dev/null | head -40
