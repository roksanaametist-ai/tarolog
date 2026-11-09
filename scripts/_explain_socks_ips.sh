#!/bin/bash
echo "unique peers in snapshot:"
wc -l </tmp/socks_peers.txt
echo
echo "=== top clients (connections -> IP) ==="
head -30 /tmp/socks_peers.txt
echo
echo "=== sample org/country ==="
for ip in $(awk '{print $2}' /tmp/socks_peers.txt | head -10); do
  info=$(whois "$ip" 2>/dev/null | grep -iE '^(org-name|OrgName|netname|descr|country|Country):' | head -5 | paste -sd ' | ' -)
  echo "$ip | $info"
done
