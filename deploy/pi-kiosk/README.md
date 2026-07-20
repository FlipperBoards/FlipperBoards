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

Two setups, depending on which OS image you flashed:

| Image | Session | Use |
|-------|---------|-----|
| **Raspberry Pi OS with desktop** (Bookworm+) | labwc (Wayland) | [labwc autostart](#raspberry-pi-os-with-desktop-labwcwayland) — current default |
| **Raspberry Pi OS Lite** (no desktop) | X11 via systemd | [setup.sh / kiosk.sh](#raspberry-pi-os-lite-x11) |

---

## Raspberry Pi OS with desktop (labwc/Wayland)

Current Raspberry Pi OS desktop images boot into the **labwc** Wayland
compositor. Don't use `kiosk.sh` here (and if you previously installed the
systemd service, disable it — it will fight the desktop session and relaunch
the browser over and over: `sudo systemctl disable --now flipperboards-kiosk`).

Instead, launch the kiosk from labwc's autostart:

```bash
cp deploy/pi-kiosk/labwc-autostart.sample ~/.config/labwc/autostart
chmod +x ~/.config/labwc/autostart
nano ~/.config/labwc/autostart     # set FB_SERVER_URL and FB_SCREEN
```

[`labwc-autostart.sample`](labwc-autostart.sample) waits for the server, then
launches Chromium fullscreen with Wayland + GPU flags.

### Things the old X11 tools used to do — and their labwc equivalents

- **Screen blanking** (`xset s off` / `-dpms` on X11): labwc only blanks if a
  `swayidle … wlopm --off` line is present in your autostart — the **Screen
  Blanking** toggle in the Control Centre / `raspi-config` adds or removes
  that line. Keep the toggle **off**; `wlr-randr --output HDMI-A-1 --on` in
  the sample is harmless belt-and-braces.
- **Cursor hiding** (`unclutter` on X11): does nothing for native-Wayland
  Chromium. With no pointing device attached, labwc shows no cursor at all —
  the usual case for a TV. If a mouse must stay plugged in, use a transparent
  cursor theme or a `swayidle` + `wtype` keybind trick.
- **Window manager** (`openbox` on X11): not needed — labwc *is* the window
  manager.

### ⚠ Quote the URL

The display URL contains `&` (`?screen=office&kiosk=1`). Unquoted, the shell
treats `&` as the background operator — Chromium silently loads the URL
**without** `kiosk=1` and the on-screen chrome stays visible. Always:

```sh
chromium ... "http://<server>:8000/display?screen=office&kiosk=1" &
```

---

## Raspberry Pi OS Lite (X11)

For headless Lite images (no desktop), `setup.sh` installs a minimal X11
session managed by systemd.

### Requirements

- Raspberry Pi 3B+ or newer (Pi Zero 2 W works for 1080p)
- **Raspberry Pi OS Lite** (64-bit, Bookworm) — no desktop
- Network access to your FlipperBoards server

### Install

Flash Pi OS Lite, boot, connect to your network, then:

```bash
git clone https://github.com/FlipperBoards/FlipperBoards
cd FlipperBoards/deploy/pi-kiosk
sudo ./setup.sh http://<unraid-ip>:8000            # default screen
sudo ./setup.sh http://<unraid-ip>:8000 lobby      # named screen
sudo reboot
```

On boot the Pi waits for the server to be reachable, then opens the display
fullscreen with the cursor hidden and screen blanking disabled.

### Configuration

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

### Useful commands

```bash
sudo systemctl status flipperboards-kiosk    # is it running?
sudo journalctl -u flipperboards-kiosk -f    # live logs
sudo systemctl restart flipperboards-kiosk   # reload the browser
sudo systemctl stop flipperboards-kiosk      # back to console
```

Note: the systemd service **restarts Chromium whenever it exits** — that's
what keeps a kiosk alive after a crash, but it also means the browser will
keep reopening if you're trying to use the Pi interactively. Stop or disable
the service first.

---

## Performance tuning (both setups)

- The display's canvas engine self-tunes (it steps down its tick rate and
  internal resolution if the Pi can't keep up, and remembers the setting).
  Pin it manually with URL params: `&scale=0.75` `&fps=20`.
- On a Pi 3 driving a 1080p TV, set the HDMI output to **720p** in
  `/boot/firmware/config.txt` — the TV upscales, every rendering cost
  halves, and at TV distance you can't tell.
- The GPU flags (`--ignore-gpu-blocklist --enable-gpu-rasterization
  --enable-zero-copy`) matter: Chromium blocklists the Pi's GPU by default
  and falls back to software rendering.

## Notes

- The browser runs in incognito mode (X11 script) so a power cut never
  triggers a "restore pages?" bar.
- Chromium is launched with `--autoplay-policy=no-user-gesture-required`
  so the synthesized flip sounds play without a click.
- If the server goes down the kiosk keeps retrying and reconnects
  automatically (the app's WebSocket also auto-reconnects on its own).
- Rotate the display? Add `display_rotate=1` (or use `kanshi`/KMS options)
  in `/boot/firmware/config.txt` as usual — the kiosk doesn't care.
