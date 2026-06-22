#!/usr/bin/env bash
# install.sh — one-time setup on the host machine.
# Run as root: sudo bash deploy/install.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$REPO_DIR/deploy"
SERVICE_USER="${SERVICE_USER:-$(logname 2>/dev/null || echo user)}"

echo "==> Installing FlipperBoards services (repo: $REPO_DIR, user: $SERVICE_USER)"

# Patch the correct username into the service files
sed -i "s/^User=user$/User=$SERVICE_USER/" "$DEPLOY_DIR/flipperboards-backend.service"
sed -i "s|WorkingDirectory=/home/user/FlipperBoards/backend|WorkingDirectory=$REPO_DIR/backend|" "$DEPLOY_DIR/flipperboards-backend.service"
sed -i "s/^User=user$/User=$SERVICE_USER/" "$DEPLOY_DIR/flipperboards-frontend.service"
sed -i "s|WorkingDirectory=/home/user/FlipperBoards/frontend|WorkingDirectory=$REPO_DIR/frontend|" "$DEPLOY_DIR/flipperboards-frontend.service"
sed -i "s|ExecStart=/home/user/FlipperBoards/deploy/update.sh|ExecStart=$DEPLOY_DIR/update.sh|" "$DEPLOY_DIR/flipperboards-updater.service"

chmod +x "$DEPLOY_DIR/update.sh"

# Copy service/timer files to systemd
cp "$DEPLOY_DIR/flipperboards-backend.service"  /etc/systemd/system/
cp "$DEPLOY_DIR/flipperboards-frontend.service" /etc/systemd/system/
cp "$DEPLOY_DIR/flipperboards-updater.service"  /etc/systemd/system/
cp "$DEPLOY_DIR/flipperboards-updater.timer"    /etc/systemd/system/

# Initial npm install
echo "==> Running npm install…"
sudo -u "$SERVICE_USER" npm --prefix "$REPO_DIR/frontend" install

# Install Python deps
echo "==> Installing Python deps…"
pip install -q -r "$REPO_DIR/backend/requirements.txt"

systemctl daemon-reload
systemctl enable --now flipperboards-backend
systemctl enable --now flipperboards-frontend
systemctl enable --now flipperboards-updater.timer

echo ""
echo "Done! Services are running."
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Check logs:  journalctl -u flipperboards-backend -f"
echo "             journalctl -u flipperboards-frontend -f"
echo "             journalctl -t flipperboards-updater -f"
