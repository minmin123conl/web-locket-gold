#!/bin/bash
# Run as root on any Ubuntu/Debian VPS
# Oracle Cloud Free Tier (always free) recommended

set -e

echo "=== LocketGold Fake RC API Server Setup ==="

# Create app directory
mkdir -p /opt/locketgold

# Copy files
cp server.js    /opt/locketgold/
cp server.crt   /opt/locketgold/
cp server.key   /opt/locketgold/

# Install Node.js if not present
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# Allow port 443
ufw allow 443/tcp
ufw allow 80/tcp

# Install systemd service
cp locketgold.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable locketgold
systemctl start locketgold

echo ""
echo "=== Done! ==="
echo "Server running. Your VPS IP: $(curl -s ifconfig.me)"
echo "Add this IP to NextDNS rewrite: api.revenuecat.com -> $(curl -s ifconfig.me)"
