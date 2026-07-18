#!/usr/bin/env bash
# update.sh — polls GitHub and restarts the service when new commits land.
# Invoked by the flipperboards-updater systemd timer.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH="${BRANCH:-main}"
LOG_TAG="flipperboards-updater"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | systemd-cat -t "$LOG_TAG" -p info; }

cd "$REPO_DIR"

# Running as root against a user-owned clone — required or git refuses with
# "detected dubious ownership in repository"
git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true

git fetch origin "$BRANCH" --quiet

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

log "New commit detected ($LOCAL → $REMOTE), updating…"
git pull origin "$BRANCH" --ff-only --quiet

# Use the repo venv when present, mirroring install.sh
if [ -x "$REPO_DIR/backend/.venv/bin/pip" ]; then
  PIP="$REPO_DIR/backend/.venv/bin/pip"
else
  PIP="pip"
fi

CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE")

if echo "$CHANGED" | grep -q "backend/requirements"; then
  log "requirements.txt changed, reinstalling…"
  $PIP install -q -r "$REPO_DIR/backend/requirements.txt"
fi

if echo "$CHANGED" | grep -q "^frontend/"; then
  if echo "$CHANGED" | grep -q "frontend/package"; then
    log "package.json changed, running npm install…"
    npm --prefix "$REPO_DIR/frontend" install --silent
  fi
  log "Rebuilding frontend…"
  npm --prefix "$REPO_DIR/frontend" run build --silent
fi

log "Restarting service…"
systemctl restart flipperboards-backend

log "Update complete — now at $(git rev-parse --short HEAD)."
