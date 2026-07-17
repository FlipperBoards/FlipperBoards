# FlipperBoards Pi App Controller (MQTT)

Lets one Raspberry Pi drive a TV with **several apps** — FlipperBoards
kiosk, [DynaFrame](https://github.com/Glenn-Sun/DynaFrame), anything that
runs as a systemd unit — with **only one running at a time**, switched over
MQTT.

Exclusivity is the point: heavy apps like DynaFrame get the whole Pi.
Activating an app stops every other managed app first (freeing its RAM and
GPU), then starts the target.

```
Home Assistant / Node-RED / mosquitto_pub
        │  MQTT
        ▼
┌───────────────────────────── Raspberry Pi ─┐
│  appctl.py (this service, runs as root)    │
│    ├── flipperboards-kiosk.service   ◄── exactly one
│    ├── dynaframe.service             ◄── active at a time
│    └── anything-else.service              │
└────────────────────────────────────────────┘
```

## Install

```bash
cd FlipperBoards/deploy/pi-appctl
sudo ./setup.sh
sudo nano /etc/flipperboards/appctl.json   # broker address + app list
sudo systemctl start flipperboards-appctl
```

## Configuration

`/etc/flipperboards/appctl.json`:

```json
{
  "mqtt": { "host": "192.168.1.50", "port": 1883, "username": "", "password": "" },
  "device_name": "Living Room TV",
  "ha_discovery": true,
  "apps": [
    { "id": "flipperboards", "name": "FlipperBoards", "units": ["flipperboards-kiosk.service"] },
    { "id": "dynaframe",     "name": "DynaFrame",     "units": ["dynaframe.service"] }
  ]
}
```

An app can list multiple units — they start in order and stop in reverse.

## MQTT topics

Base topic defaults to `flipperboards/<hostname>/app`.

| Topic | Direction | Payload |
|-------|-----------|---------|
| `…/app/set` | you → Pi | app id or name (case-insensitive), or `off` |
| `…/app` | Pi → you | current app name, `Off` when none (retained) |
| `…/app/availability` | Pi → you | `online` / `offline` (last-will, retained) |

Try it from any machine:

```bash
mosquitto_pub -h 192.168.1.50 -t flipperboards/livingroom-pi/app/set -m dynaframe
mosquitto_pub -h 192.168.1.50 -t flipperboards/livingroom-pi/app/set -m flipperboards
mosquitto_pub -h 192.168.1.50 -t flipperboards/livingroom-pi/app/set -m off
```

## Home Assistant

With `ha_discovery` on (default) the Pi announces itself via MQTT
discovery — it appears as a device with a **Display App** dropdown
(`select` entity). No YAML needed. Use it directly on dashboards, or in
automations:

```yaml
# Photo frame during the day, split-flap board in the evening
- alias: Evening board
  trigger: { platform: sun, event: sunset }
  action:
    - service: select.select_option
      target: { entity_id: select.living_room_tv_display_app }
      data: { option: FlipperBoards }
```

The controller also polls every 15 s, so if an app crashes or someone runs
`systemctl` by hand, the reported state stays truthful.

## Notes

- Runs as root because it starts/stops systemd units. It only ever
  touches units listed in its config.
- No TLS/auth beyond what your broker enforces — treat it as LAN-trusted,
  same as the FlipperBoards server itself.
- Pairs with [`../pi-kiosk/`](../pi-kiosk/) — install that first for the
  FlipperBoards app entry.
