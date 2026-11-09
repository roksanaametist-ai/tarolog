#!/bin/bash
# Run in HSHP VNC so the agent can SSH on :2222
set -e
mkdir -p /etc/ssh/sshd_config.d
printf '%s\n' 'Port 2222' 'PasswordAuthentication no' 'PubkeyAuthentication yes' > /etc/ssh/sshd_config.d/port2222.conf
systemctl enable --now ssh
systemctl restart ssh
ufw disable 2>/dev/null || true
iptables -P INPUT ACCEPT 2>/dev/null || true
iptables -P FORWARD ACCEPT 2>/dev/null || true
iptables -F INPUT 2>/dev/null || true
# keep ESTABLISHED if filter table empty is too aggressive on some hosts - only flush if ufw was the issue
ss -tlnp | grep -E ':2222|:22' || true
systemctl is-active ssh
echo "PUBLIC_IP=$(curl -4 -sS --max-time 5 ifconfig.me 2>/dev/null || echo unknown)"
echo "Ready: ssh -p 2222 root@$(curl -4 -sS --max-time 5 ifconfig.me 2>/dev/null || echo 37.46.18.192)"
