#!/usr/bin/env bash
# FlipperBoards quick setup for Raspberry Pi / Linux
set -e

echo "=== FlipperBoards Setup ==="

# Check Python
python3 --version || { echo "Python 3.11+ required"; exit 1; }

# Check Node
node --version || { echo "Node.js 18+ required"; exit 1; }

# Backend deps
echo ""
echo "Installing Python dependencies..."
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Frontend build
echo ""
echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Start the server:"
echo "  cd backend && source .venv/bin/activate && python main.py"
echo ""
echo "Open display (TV browser):     http://<pi-ip>:8000/display"
echo "Open remote control (phone):   http://<pi-ip>:8000/"
echo ""
echo "Optional: copy flipperboards.service to /etc/systemd/system/ for auto-start"
