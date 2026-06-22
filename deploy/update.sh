#!/usr/bin/env bash
# update.sh — polls GitHub and restarts services when new commits land.
# Invoked by the flipperboards-updater systemd service every 60 seconds.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH="${BRANCH:-main}"
LOG_TAG="flipperboards-updater"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | systemd-cat -t "$LOG_TAG" -p info; }

cd "$REPO_DIR"

git fetch origin "$BRANCH" --quiet

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

log "New commit detected ($LOCAL → $REMOTE), updating…"
git pull origin "$BRANCH" --ff-only --quiet

# Reinstall Python deps only if requirements.txt changed
if git diff --name-only "$LOCAL" "$REMOTE" | grep -q "backend/requirements"; then
  log "requirements.txt changed, reinstalling…"
  pip install -q -r "$REPO_DIR/backend/requirements.txt"
fi

# npm install only if package.json changed
if git diff --name-only "$LOCAL" "$REMOTE" | grep -q "frontend/package"; then
  log "package.json changed, running npm install…"
  npm --prefix "$REPO_DIR/frontend" install --silent
fi

log "Restarting services…"
systemctl restart flipperboards-backend
systemctl restart flipperboards-frontend

log "Update complete — now at $(git rev-parse --short HEAD)."
