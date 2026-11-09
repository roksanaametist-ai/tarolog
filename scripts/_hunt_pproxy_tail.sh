#!/bin/bash
echo "=== pproxy process ==="
ps auxww | grep pproxy | grep -v grep
echo
echo "=== who listens 1080 / connects to pproxy ==="
ss -tlnp | grep 1080 || true
ss -tnp | grep ':1080' | head -40 || true
echo
echo "=== pproxy service / autostart ==="
systemctl list-units --all | grep -i proxy || true
ls /etc/systemd/system/*proxy* 2>/dev/null || true
crontab -l 2>/dev/null | grep -i proxy || true
grep -RIn --include='*.service' -l 'pproxy\|1080' /etc/systemd/system /lib/systemd/system 2>/dev/null || true
echo
echo "=== recent peers on 1080 ==="
ss -tn sport = :1080 or dport = :1080 | head -50
echo
echo "=== env files mentioning socks/1080/proxy for bot ==="
grep -RIn --exclude-dir=venv --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=deploy-backups -n '1080\|SOCKS\|ALL_PROXY\|HTTPS_PROXY\|pproxy' /root/tarolog/.env /root/ассистент/.env /root/*/ .env 2>/dev/null | head -40
echo
echo "=== stop test: stop tarolog, watch if pproxy keeps telegram long-poll ==="
systemctl stop tarolog.service
sleep 2
echo "telegram fds of pproxy before:"
ls -l /proc/2298287/fd 2>/dev/null | wc -l
ss -tnp | grep 149.154 | grep pproxy || true
# try getUpdates now quickly (may 409 if proxy client holds poll)
TOK=$(grep '^TELEGRAM_TOKEN=' /root/tarolog/.env | cut -d= -f2-)
curl -sS --max-time 8 "https://api.telegram.org/bot${TOK}/getUpdates?timeout=1&limit=1" || true
echo
systemctl start tarolog.service
