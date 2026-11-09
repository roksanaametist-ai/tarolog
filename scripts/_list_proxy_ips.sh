#!/bin/bash
echo "=== Clients on SOCKS :1080 (IP -> your VPS) ==="
ss -tn state established '( sport = :1080 )' | awk 'NR>1{print $5}' | sed 's/:[0-9]*$//' | sort | uniq -c | sort -rn

echo
echo -n "unique SOCKS clients now: "
ss -tn state established '( sport = :1080 )' | awk 'NR>1{print $5}' | sed 's/:[0-9]*$//' | sort -u | wc -l

echo
echo "=== Who talks to Telegram API from this VPS ==="
ss -tnp | grep -E '149\.154\.|91\.108\.' || true

echo
echo "=== Top SOCKS clients + country ==="
mapfile -t IPS < <(ss -tn state established '( sport = :1080 )' | awk 'NR>1{print $5}' | sed 's/:[0-9]*$//' | sort | uniq -c | sort -rn | head -12 | awk '{print $2}')
for ip in "${IPS[@]}"; do
  cc=$(curl -sS --max-time 3 "https://ipinfo.io/${ip}/country" 2>/dev/null || echo "?")
  org=$(curl -sS --max-time 3 "https://ipinfo.io/${ip}/org" 2>/dev/null || echo "")
  echo "$ip  [$cc]  $org"
done
