#!/bin/bash
set -e
sed -n '3950,4010p' /root/tarolog/main.py
echo '===='
TOKEN=$(grep '^TELEGRAM_TOKEN=' /root/tarolog/.env | cut -d= -f2-)
echo "token_prefix=${TOKEN:0:12}"
curl -sS "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
echo
curl -sS "https://api.telegram.org/bot${TOKEN}/getMe"
echo
echo '==== assistant env ===='
grep -E 'TOKEN|BOT' /root/ассистент/.env 2>/dev/null | sed -E 's/=.*/=***/' || true
echo '==== other polling hosts? ===='
# drop webhook just in case, then force single polling restart
curl -sS "https://api.telegram.org/bot${TOKEN}/deleteWebhook?drop_pending_updates=false"
echo
systemctl restart tarolog.service
sleep 3
systemctl is-active tarolog.service
journalctl -u tarolog.service -n 15 --no-pager
