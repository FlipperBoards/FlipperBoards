#!/usr/bin/env bash
# FlipperBoards Pi kiosk installer — run with sudo on Raspberry Pi OS Lite.
#
#   sudo ./setup.sh http://<server-ip>:8000 [screen-id]
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo ./setup.sh http://<server-ip>:8000 [screen-id]" >&2
    exit 1
fi

SERVER_URL="${1:?Usage: sudo ./setup.sh http://<server-ip>:8000 [screen-id]}"
SCREEN="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# The desktop user the kiosk session runs as (whoever invoked sudo, else pi)
KIOSK_USER="${SUDO_USER:-pi}"
KIOSK_UID="$(id -u "$KIOSK_USER")"

echo "==> Installing packages (minimal X + Chromium)..."
apt-get update
apt-get install -y --no-install-recommends \
    xserver-xorg x11-xinit xserver-xorg-legacy openbox unclutter curl
# Package name differs across Pi OS releases
apt-get install -y --no-install-recommends chromium-browser 2>/dev/null \
    || apt-get install -y --no-install-recommends chromium

echo "==> Allowing X to start from the systemd service..."
cat > /etc/X11/Xwrapper.config <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

echo "==> Writing /etc/default/flipperboards-kiosk..."
cat > /etc/default/flipperboards-kiosk <<EOF
FB_SERVER_URL=$SERVER_URL
FB_SCREEN=$SCREEN
FB_SOUND=1
EOF

echo "==> Installing launcher to /opt/flipperboards-kiosk..."
mkdir -p /opt/flipperboards-kiosk
install -m 755 "$SCRIPT_DIR/kiosk.sh" /opt/flipperboards-kiosk/kiosk.sh

echo "==> Installing systemd service (user: $KIOSK_USER)..."
sed -e "s/^User=.*/User=$KIOSK_USER/" \
    -e "s/^Group=.*/Group=$KIOSK_USER/" \
    -e "s|^Environment=XDG_RUNTIME_DIR=.*|Environment=XDG_RUNTIME_DIR=/run/user/$KIOSK_UID|" \
    "$SCRIPT_DIR/flipperboards-kiosk.service" \
    > /etc/systemd/system/flipperboards-kiosk.service

systemctl daemon-reload
systemctl enable flipperboards-kiosk

echo ""
echo "Done. The kiosk will start on next boot, or right now with:"
echo "  sudo systemctl start flipperboards-kiosk"
echo ""
echo "Server:  $SERVER_URL"
echo "Screen:  ${SCREEN:-main (default)}"
echo "Config:  /etc/default/flipperboards-kiosk"
