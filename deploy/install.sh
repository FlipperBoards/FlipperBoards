#!/usr/bin/env bash
# install.sh — one-time setup on the host machine.
# Run as root: sudo bash deploy/install.sh
#
# Installs a single systemd service: the FastAPI backend serving both the API
# and the production frontend build on port 8000, plus an optional auto-update
# timer that pulls new commits and rebuilds.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$REPO_DIR/deploy"
SERVICE_USER="${SERVICE_USER:-$(logname 2>/dev/null || echo user)}"

echo "==> Installing FlipperBoards (repo: $REPO_DIR, user: $SERVICE_USER)"

# Use the repo venv when present (created by setup.sh), else system python
if [ -x "$REPO_DIR/backend/.venv/bin/python" ]; then
    PYTHON="$REPO_DIR/backend/.venv/bin/python"
    PIP="$REPO_DIR/backend/.venv/bin/pip"
else
    PYTHON="/usr/bin/python3"
    PIP="pip"
fi

# Patch machine-specific values into the unit files
sed -i "s/^User=.*/User=$SERVICE_USER/" "$DEPLOY_DIR/flipperboards-backend.service"
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$REPO_DIR/backend|" "$DEPLOY_DIR/flipperboards-backend.service"
sed -i "s|^ExecStart=.*|ExecStart=$PYTHON -m uvicorn main:app --host 0.0.0.0 --port 8000|" "$DEPLOY_DIR/flipperboards-backend.service"
sed -i "s|^ExecStart=.*|ExecStart=$DEPLOY_DIR/update.sh|" "$DEPLOY_DIR/flipperboards-updater.service"

chmod +x "$DEPLOY_DIR/update.sh"

cp "$DEPLOY_DIR/flipperboards-backend.service" /etc/systemd/system/
cp "$DEPLOY_DIR/flipperboards-updater.service" /etc/systemd/system/
cp "$DEPLOY_DIR/flipperboards-updater.timer"   /etc/systemd/system/

echo "==> Installing Python deps…"
$PIP install -q -r "$REPO_DIR/backend/requirements.txt"

echo "==> Building frontend (production bundle, served by the backend)…"
sudo -u "$SERVICE_USER" npm --prefix "$REPO_DIR/frontend" install
sudo -u "$SERVICE_USER" npm --prefix "$REPO_DIR/frontend" run build

# git as root in a user-owned repo needs this or every fetch fails
git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true

systemctl daemon-reload
systemctl enable --now flipperboards-backend
systemctl enable --now flipperboards-updater.timer

echo ""
echo "Done! FlipperBoards is running."
echo "  App:      http://localhost:8000        (remote control)"
echo "  Display:  http://localhost:8000/display"
echo ""
echo "Logs:      journalctl -u flipperboards-backend -f"
echo "Updater:   journalctl -t flipperboards-updater -f"
echo "           (disable auto-update: systemctl disable --now flipperboards-updater.timer)"
