#!/usr/bin/env bash
# FlipperBoards kiosk launcher — runs inside the X session started by the
# flipperboards-kiosk systemd service. Reads /etc/default/flipperboards-kiosk.

CONFIG=/etc/default/flipperboards-kiosk
[ -f "$CONFIG" ] && . "$CONFIG"

FB_SERVER_URL="${FB_SERVER_URL:-http://localhost:8000}"
FB_SERVER_URL="${FB_SERVER_URL%/}"
URL="$FB_SERVER_URL/display?kiosk=1"
[ -n "$FB_SCREEN" ] && URL="$URL&screen=$FB_SCREEN"
[ -n "$FB_SOUND" ]  && URL="$URL&sound=$FB_SOUND"

# Never blank or power down the screen
xset s off
xset s noblank
xset -dpms

# Hide the mouse cursor when idle
command -v unclutter >/dev/null && unclutter -idle 0.5 -root &

# Minimal window manager so fullscreen/kiosk sizing behaves
command -v openbox >/dev/null && openbox &

# Wait until the server answers before launching the browser,
# so a cold boot doesn't land on a connection-error page.
until curl -sf --max-time 3 "$FB_SERVER_URL/api/screens" >/dev/null 2>&1; do
    sleep 2
done

# Bookworm ships the binary as "chromium"; older images as "chromium-browser"
BROWSER=$(command -v chromium-browser || command -v chromium)

# GPU flags: Chromium blocklists the Pi's VideoCore GPU by default and falls
# back to software rendering — forcing GPU rasterization makes the split-flap
# canvas dramatically smoother on Pi 3 hardware.
exec "$BROWSER" \
    --kiosk \
    --incognito \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --autoplay-policy=no-user-gesture-required \
    --check-for-update-interval=31536000 \
    --ignore-gpu-blocklist \
    --enable-gpu-rasterization \
    --enable-zero-copy \
    --disable-smooth-scrolling \
    "$URL"
