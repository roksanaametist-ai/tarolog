#!/bin/bash
systemctl restart tarolog.service
sleep 6
echo "=== journal ==="
journalctl -u tarolog.service -n 15 --no-pager
TOK=$(grep '^TELEGRAM_TOKEN=' /root/tarolog/.env | cut -d= -f2-)
systemctl stop tarolog.service
sleep 8
echo "=== getUpdates with HSHP off ==="
curl -sS --max-time 15 "https://api.telegram.org/bot${TOK}/getUpdates?timeout=3&limit=1" || true
echo
systemctl start tarolog.service
sleep 5
echo "=== journal after start ==="
journalctl -u tarolog.service -n 10 --no-pager
