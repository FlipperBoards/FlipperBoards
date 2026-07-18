"""MQTT bridge — control FlipperBoards from any MQTT client (Home Assistant,
Node-RED, mosquitto_pub, ...).

Topic contract (base topic configurable, default "flipperboards"):

  Commands (subscribed):
    {base}/<screen>/text/set                 "HELLO" or {"text":"HI","duration":30}
    {base}/<screen>/matrix/set               {"matrix":[[...]],"duration":30}
    {base}/<screen>/design/set               design name, id, or {"design":...,"duration":60}
    {base}/<screen>/image/set                library image id/name or {"image":...,"duration":60}
    {base}/<screen>/mode/set                 mode id, e.g. "clock"
    {base}/<screen>/blank/set                any payload
    {base}/<screen>/playlist/set             "next" | "play" | item index
    {base}/<screen>/scoreboard/set           {"home_score":3,...} (first scoreboard item)
    {base}/<screen>/scoreboard/<item_id>/set same, targeting a specific playlist item

  State (published, retained):
    {base}/bridge/availability               "online"/"offline" (last will)
    {base}/<screen>/state                    {"mode","rows","cols","playlist_pos","playlist_len"}
    {base}/<screen>/mode                     current mode string
    {base}/<screen>/text/state               last pushed text

With ha_discovery enabled, each screen is announced to Home Assistant as a
device with a message text entity, a mode select, and next/blank buttons.
"""

import asyncio
import json
import logging

import aiomqtt

import database

logger = logging.getLogger("flipperboards.mqtt")

HA_PREFIX = "homeassistant"
RECONNECT_DELAY = 5


class MQTTBridge:
    """Owns the broker connection lifecycle. Command semantics live in the
    injected `dispatch(screen_id, command, arg, payload)` coroutine."""

    def __init__(self, dispatch, screens_provider, modes_provider):
        self._dispatch = dispatch
        self._screens = screens_provider     # () -> dict[str, ScreenState]
        self._modes = modes_provider         # () -> list[dict] (mode catalog)
        self._task: asyncio.Task | None = None
        self._client: aiomqtt.Client | None = None
        self.base = "flipperboards"
        self._ha_discovery = True
        self._last_state: dict[str, str] = {}   # screen_id -> last state JSON

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self):
        settings = await database.get_settings()
        if settings.get("mqtt_enabled") != "true" or not settings.get("mqtt_host"):
            logger.info("MQTT disabled or no host configured")
            return
        self.base = (settings.get("mqtt_base_topic") or "flipperboards").strip("/")
        self._ha_discovery = settings.get("mqtt_ha_discovery", "true") == "true"
        self._task = asyncio.create_task(self._run(
            host=settings["mqtt_host"],
            port=int(settings.get("mqtt_port") or 1883),
            username=settings.get("mqtt_username") or None,
            password=settings.get("mqtt_password") or None,
        ))

    async def stop(self):
        if self._client:
            try:
                await self._client.publish(
                    f"{self.base}/bridge/availability", "offline", retain=True)
            except Exception:
                pass
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self._client = None

    async def restart(self):
        await self.stop()
        await self.start()

    # ── Connection loop ──────────────────────────────────────────────────────

    async def _run(self, host, port, username, password):
        will = aiomqtt.Will(f"{self.base}/bridge/availability", "offline", retain=True)
        while True:
            try:
                async with aiomqtt.Client(
                    host, port=port, username=username, password=password,
                    will=will, identifier="flipperboards-server",
                ) as client:
                    self._client = client
                    logger.info("MQTT connected to %s:%s", host, port)
                    await client.publish(
                        f"{self.base}/bridge/availability", "online", retain=True)
                    if self._ha_discovery:
                        await self._publish_discovery()
                    for state in self._screens().values():
                        await self.publish_screen_state(state)
                    await client.subscribe(f"{self.base}/+/+/set")
                    await client.subscribe(f"{self.base}/+/scoreboard/+/set")
                    async for message in client.messages:
                        try:
                            await self._handle(message)
                        except Exception:
                            logger.exception("MQTT message handling failed: %s",
                                             message.topic)
            except asyncio.CancelledError:
                self._client = None
                raise
            except aiomqtt.MqttError as e:
                self._client = None
                logger.warning("MQTT connection lost (%s); retrying in %ss",
                               e, RECONNECT_DELAY)
                await asyncio.sleep(RECONNECT_DELAY)
            except Exception:
                self._client = None
                logger.exception("MQTT loop error; retrying in %ss", RECONNECT_DELAY)
                await asyncio.sleep(RECONNECT_DELAY)

    async def _handle(self, message):
        # {base}/<sid>/<command>/set  or  {base}/<sid>/scoreboard/<item_id>/set
        parts = str(message.topic).split("/")
        base_parts = self.base.split("/")
        if parts[: len(base_parts)] != base_parts:
            return
        parts = parts[len(base_parts):]
        if len(parts) < 3 or parts[-1] != "set":
            return
        screen_id, command = parts[0], parts[1]
        arg = parts[2] if len(parts) == 4 else None
        payload = (message.payload or b"").decode("utf-8", "replace").strip()
        await self._dispatch(screen_id, command, arg, payload)

    # ── State publishing ─────────────────────────────────────────────────────

    async def publish_screen_state(self, state, text: str | None = None):
        if not self._client:
            return
        try:
            sid = state.screen_id
            payload = json.dumps({
                "mode": state.mode,
                "rows": state.rows,
                "cols": state.cols,
                "playlist_pos": state.playlist_pos,
                "playlist_len": len(state.playlist_items),
            })
            # Clock mode broadcasts every second — only publish real changes
            if payload != self._last_state.get(sid):
                self._last_state[sid] = payload
                await self._client.publish(f"{self.base}/{sid}/state", payload,
                                           retain=True)
                await self._client.publish(f"{self.base}/{sid}/mode", state.mode,
                                           retain=True)
            if text is not None:
                await self._client.publish(f"{self.base}/{sid}/text/state", text,
                                           retain=True)
        except Exception:
            logger.debug("MQTT state publish failed", exc_info=True)

    # ── Home Assistant discovery ─────────────────────────────────────────────

    def _device_block(self, sid: str, name: str) -> dict:
        return {
            "identifiers": [f"flipperboards_{sid}"],
            "name": f"FlipperBoards {name}",
            "manufacturer": "FlipperBoards",
            "model": "Split-Flap Display",
        }

    def _discovery_configs(self, state) -> dict[str, dict]:
        sid = state.screen_id
        base = self.base
        avail = f"{base}/bridge/availability"
        device = self._device_block(sid, state.name)
        return {
            f"{HA_PREFIX}/text/flipperboards_{sid}/message/config": {
                "name": "Message",
                "unique_id": f"flipperboards_{sid}_message",
                "command_topic": f"{base}/{sid}/text/set",
                "state_topic": f"{base}/{sid}/text/state",
                "max": min(255, state.rows * state.cols),
                "icon": "mdi:message-text",
                "availability_topic": avail,
                "device": device,
            },
            f"{HA_PREFIX}/select/flipperboards_{sid}/mode/config": {
                "name": "Mode",
                "unique_id": f"flipperboards_{sid}_mode",
                "command_topic": f"{base}/{sid}/mode/set",
                "state_topic": f"{base}/{sid}/mode",
                "options": [m["id"] for m in self._modes()],
                "icon": "mdi:view-carousel",
                "availability_topic": avail,
                "device": device,
            },
            f"{HA_PREFIX}/button/flipperboards_{sid}/next/config": {
                "name": "Next",
                "unique_id": f"flipperboards_{sid}_next",
                "command_topic": f"{base}/{sid}/playlist/set",
                "payload_press": "next",
                "icon": "mdi:skip-next",
                "availability_topic": avail,
                "device": device,
            },
            f"{HA_PREFIX}/button/flipperboards_{sid}/blank/config": {
                "name": "Blank",
                "unique_id": f"flipperboards_{sid}_blank",
                "command_topic": f"{base}/{sid}/blank/set",
                "payload_press": "blank",
                "icon": "mdi:monitor-off",
                "availability_topic": avail,
                "device": device,
            },
        }

    async def _publish_discovery(self):
        if not self._client:
            return
        for state in self._screens().values():
            for topic, payload in self._discovery_configs(state).items():
                await self._client.publish(topic, json.dumps(payload), retain=True)

    async def refresh_discovery(self):
        if self._client and self._ha_discovery:
            try:
                await self._publish_discovery()
            except Exception:
                logger.debug("MQTT discovery refresh failed", exc_info=True)

    async def remove_screen_discovery(self, screen_id: str):
        """Clear retained discovery configs for a deleted screen."""
        if not self._client:
            return
        for kind, entity in (("text", "message"), ("select", "mode"),
                             ("button", "next"), ("button", "blank")):
            try:
                await self._client.publish(
                    f"{HA_PREFIX}/{kind}/flipperboards_{screen_id}/{entity}/config",
                    "", retain=True)
            except Exception:
                pass
