#!/bin/bash
echo "=== RAW ss :1080 established ==="
ss -tn state established '( sport = :1080 )'
echo
echo "=== Parsed peer IPs ==="
ss -Htn state established '( sport = :1080 )' | while read -r line; do
  peer=$(echo "$line" | awk '{print $4}')
  # when local is first after state... check columns
  echo "LINE:$line"
done | head -5

echo "=== Better parse (peer = last ip:port) ==="
ss -Htn state established '( sport = :1080 )' | awk '{print $NF}' | sed 's/:\([0-9]\+\)$/ \1/' | awk '{print $1}' | sort | uniq -c | sort -rn | tee /tmp/socks_peers.txt | head -40

echo
echo "unique:" $(awk '{print $2}' /tmp/socks_peers.txt | grep -v '^$' | wc -l)

echo
echo "=== Geo for top 15 ==="
awk '{print $2}' /tmp/socks_peers.txt | head -15 | while read -r ip; do
  [ -z "$ip" ] && continue
  info=$(curl -sS --max-time 4 "https://ipinfo.io/${ip}" 2>/dev/null)
  cc=$(echo "$info" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('country','?'), d.get('org','')[:60], d.get('city',''))" 2>/dev/null || echo "?")
  echo "$ip  $cc"
done

echo
echo "=== Telegram speakers on VPS ==="
ss -tnp | grep -E '149\.154\.|91\.108\.' | sed 's/users:(/ -> /'
