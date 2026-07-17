#!/usr/bin/env bash
# FlipperBoards Pi app controller installer — run with sudo.
#
#   sudo ./setup.sh
#
# Then edit /etc/flipperboards/appctl.json with your MQTT broker details
# and app list, and: sudo systemctl restart flipperboards-appctl
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo ./setup.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing paho-mqtt..."
apt-get update
apt-get install -y --no-install-recommends python3-paho-mqtt 2>/dev/null \
    || pip3 install --break-system-packages paho-mqtt

echo "==> Installing controller to /opt/flipperboards-appctl..."
mkdir -p /opt/flipperboards-appctl
install -m 755 "$SCRIPT_DIR/appctl.py" /opt/flipperboards-appctl/appctl.py

echo "==> Writing config..."
mkdir -p /etc/flipperboards
if [ ! -f /etc/flipperboards/appctl.json ]; then
    install -m 644 "$SCRIPT_DIR/appctl.json.example" /etc/flipperboards/appctl.json
    echo "    Created /etc/flipperboards/appctl.json — EDIT THIS with your broker."
else
    echo "    Keeping existing /etc/flipperboards/appctl.json"
fi

echo "==> Installing systemd service..."
install -m 644 "$SCRIPT_DIR/flipperboards-appctl.service" \
    /etc/systemd/system/flipperboards-appctl.service
systemctl daemon-reload
systemctl enable flipperboards-appctl

echo ""
echo "Done. Next steps:"
echo "  1. sudo nano /etc/flipperboards/appctl.json   # broker + apps"
echo "  2. sudo systemctl start flipperboards-appctl"
echo "  3. Check logs: sudo journalctl -u flipperboards-appctl -f"
