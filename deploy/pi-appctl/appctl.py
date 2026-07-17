#!/usr/bin/env python3
"""FlipperBoards Pi app controller — MQTT-driven exclusive app switching.

Each "app" is a set of systemd units (FlipperBoards kiosk, DynaFrame, ...).
Only one app runs at a time: activating one stops the others first, so a
resource-hungry app like DynaFrame gets the whole Pi to itself.

MQTT contract (base topic defaults to flipperboards/<hostname>/app):
  <base>/set           command: app id or name (case-insensitive), or "off"
  <base>               state: current app name, "Off" when none (retained)
  <base>/availability  "online"/"offline" via last-will (retained)

With ha_discovery enabled (default), a Home Assistant "select" entity is
announced automatically — the Pi appears as a device with a dropdown you
can put on a dashboard or drive from automations.
"""
import json
import queue
import socket
import subprocess
import sys
import time

import paho.mqtt.client as mqtt

CONFIG_PATH = sys.argv[1] if len(sys.argv) > 1 else "/etc/flipperboards/appctl.json"

OFF = "Off"


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    if not cfg.get("apps"):
        sys.exit("appctl: no apps defined in config")
    cfg.setdefault("node", socket.gethostname())
    cfg.setdefault("device_name", f"Pi Display {cfg['node']}")
    cfg.setdefault("base_topic", f"flipperboards/{cfg['node']}/app")
    cfg.setdefault("ha_discovery", True)
    cfg.setdefault("ha_prefix", "homeassistant")
    cfg.setdefault("poll_seconds", 15)
    return cfg


def systemctl(*args):
    return subprocess.run(["systemctl", "--no-ask-password", *args],
                          capture_output=True, text=True)


def unit_active(unit):
    return systemctl("is-active", "--quiet", unit).returncode == 0


class AppController:
    def __init__(self, cfg):
        self.cfg = cfg
        self.base = cfg["base_topic"]
        self.requests = queue.Queue()
        self.last_state = None

        # paho-mqtt v2 changed the constructor; support both
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1,
                                      client_id=f"fb-appctl-{cfg['node']}")
        except AttributeError:
            self.client = mqtt.Client(client_id=f"fb-appctl-{cfg['node']}")

        m = cfg.get("mqtt", {})
        if m.get("username"):
            self.client.username_pw_set(m["username"], m.get("password") or None)
        self.client.will_set(f"{self.base}/availability", "offline", retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(m.get("host", "localhost"), int(m.get("port", 1883)), 60)

    # ── MQTT callbacks (network thread — keep them quick) ────────────────────

    def on_connect(self, client, userdata, flags, rc, *args):
        client.subscribe(f"{self.base}/set")
        client.publish(f"{self.base}/availability", "online", retain=True)
        if self.cfg["ha_discovery"]:
            self.publish_discovery()
        self.publish_state(force=True)

    def on_message(self, client, userdata, msg):
        self.requests.put(msg.payload.decode("utf-8", "replace").strip())

    # ── Discovery / state ────────────────────────────────────────────────────

    def publish_discovery(self):
        node = self.cfg["node"]
        payload = {
            "name": "Display App",
            "unique_id": f"fb_appctl_{node}",
            "command_topic": f"{self.base}/set",
            "state_topic": self.base,
            "availability_topic": f"{self.base}/availability",
            "options": [OFF] + [a["name"] for a in self.cfg["apps"]],
            "icon": "mdi:television-guide",
            "device": {
                "identifiers": [f"fb_appctl_{node}"],
                "name": self.cfg["device_name"],
                "manufacturer": "FlipperBoards",
                "model": "Pi App Controller",
            },
        }
        topic = f"{self.cfg['ha_prefix']}/select/fb_appctl_{node}/app/config"
        self.client.publish(topic, json.dumps(payload), retain=True)

    def current_app(self):
        for app in self.cfg["apps"]:
            if app["units"] and unit_active(app["units"][0]):
                return app
        return None

    def publish_state(self, force=False):
        app = self.current_app()
        state = app["name"] if app else OFF
        if force or state != self.last_state:
            self.client.publish(self.base, state, retain=True)
            self.last_state = state

    # ── Switching ────────────────────────────────────────────────────────────

    def resolve(self, requested):
        want = requested.lower()
        if want in ("off", "none", "stop", ""):
            return OFF
        for app in self.cfg["apps"]:
            if want in (app["id"].lower(), app["name"].lower()):
                return app
        return None

    def switch(self, target):
        for app in self.cfg["apps"]:
            if app is not target:
                for unit in reversed(app["units"]):
                    systemctl("stop", unit)
        if target is not OFF:
            for unit in target["units"]:
                r = systemctl("start", unit)
                if r.returncode != 0:
                    print(f"appctl: failed to start {unit}: {r.stderr.strip()}",
                          flush=True)
        self.publish_state(force=True)

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self):
        self.client.loop_start()
        try:
            while True:
                try:
                    requested = self.requests.get(timeout=self.cfg["poll_seconds"])
                except queue.Empty:
                    self.publish_state()  # reflect crashes/manual systemctl use
                    continue
                target = self.resolve(requested)
                if target is None:
                    print(f"appctl: unknown app '{requested}'", flush=True)
                    continue
                name = OFF if target is OFF else target["name"]
                print(f"appctl: switching to {name}", flush=True)
                self.switch(target)
        finally:
            self.client.publish(f"{self.base}/availability", "offline", retain=True)
            self.client.loop_stop()


if __name__ == "__main__":
    AppController(load_config()).run()
