# FlipperBoards Pi Kiosk Client

Turns a Raspberry Pi into a dedicated display client. The Pi runs **no
FlipperBoards code** — it boots straight into a fullscreen Chromium window
pointed at your FlipperBoards server (e.g. the Docker container on your
Unraid box). All content, scheduling, and control happens on the server;
the Pi is just a screen.

```
┌─────────────┐   HTTP/WebSocket    ┌──────────────────┐   HDMI   ┌──────┐
│ Unraid box   │ ◄────────────────► │ Raspberry Pi      │ ───────► │  TV  │
│ (Docker app) │                    │ (Chromium kiosk)  │          └──────┘
└─────────────┘                     └──────────────────┘
```

## Requirements

- Raspberry Pi 3B+ or newer (Pi Zero 2 W works for 1080p)
- **Raspberry Pi OS Lite** (64-bit, Bookworm) — no desktop needed
- Network access to your FlipperBoards server

## Install

Flash Pi OS Lite, boot, connect to your network, then:

```bash
git clone https://github.com/FlipperBoards/FlipperBoards
cd FlipperBoards/deploy/pi-kiosk
sudo ./setup.sh http://<unraid-ip>:8000            # default screen
sudo ./setup.sh http://<unraid-ip>:8000 lobby      # named screen
sudo reboot
```

That's it. On boot the Pi waits for the server to be reachable, then opens
the display fullscreen with the cursor hidden and screen blanking disabled.

## Configuration

Settings live in `/etc/default/flipperboards-kiosk`:

```bash
FB_SERVER_URL=http://192.168.1.50:8000
FB_SCREEN=lobby        # blank = default "main" screen
FB_SOUND=1             # 1 = flip sounds on, 0 = silent
```

Edit and restart to apply:

```bash
sudo systemctl restart flipperboards-kiosk
```

## Useful commands

```bash
sudo systemctl status flipperboards-kiosk    # is it running?
sudo journalctl -u flipperboards-kiosk -f    # live logs
sudo systemctl restart flipperboards-kiosk   # reload the browser
sudo systemctl stop flipperboards-kiosk      # back to console
```

## Notes

- The browser runs in incognito mode, so a power cut never triggers a
  "restore pages?" bar.
- Chromium is launched with `--autoplay-policy=no-user-gesture-required`
  so the synthesized flip sounds play without a click.
- If the server goes down the service keeps retrying and reconnects
  automatically (the app's WebSocket also auto-reconnects on its own).
- Rotate the display? Add `display_rotate=1` (or use `kanshi`/KMS options)
  in `/boot/firmware/config.txt` as usual — the kiosk doesn't care.
