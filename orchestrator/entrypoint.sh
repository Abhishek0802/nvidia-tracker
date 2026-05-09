#!/bin/bash
set -e

# Resolve the Daytona proxy container IP (accessible via service name on daytona-net)
PROXY_IP=$(getent hosts proxy | awk '{ print $1 }')
echo "[entrypoint] Daytona proxy IP: $PROXY_IP"

# Configure dnsmasq to resolve *.proxy.localhost → proxy IP
cat > /etc/dnsmasq.conf <<EOF
address=/.proxy.localhost/$PROXY_IP
listen-address=127.0.0.1
bind-interfaces
no-resolv
server=127.0.0.11
EOF

# Prepend dnsmasq to DNS resolution (Docker bind-mounts resolv.conf so we copy+replace)
cp /etc/resolv.conf /tmp/resolv.conf.bak
{ echo "nameserver 127.0.0.1"; cat /tmp/resolv.conf.bak; } > /etc/resolv.conf || \
  echo "nameserver 127.0.0.1" | tee -a /etc/resolv.conf > /dev/null

# Start dnsmasq in background
dnsmasq --no-daemon &
sleep 1

echo "[entrypoint] DNS ready — *.proxy.localhost → $PROXY_IP"

exec python main.py
