"""Sound scheduling + per-push/MQTT sound override.

The server decides whether each broadcast should click, from the global
switch, the schedule window, and any per-push override. We test the pure
decision helper plus that pushes carry the sound flag over the WebSocket."""
import json
from datetime import datetime

import pytz

import main
from main import _sound_allowed_at


TZ = pytz.timezone("America/New_York")


def _now(h, m=0, weekday_iso="2026-07-20"):  # 2026-07-20 is a Monday
    return TZ.localize(datetime.strptime(f"{weekday_iso} {h:02d}:{m:02d}", "%Y-%m-%d %H:%M"))


def _settings(enabled=True, schedule=None):
    return {
        "sound_enabled": "true" if enabled else "false",
        "sound_schedule": json.dumps(schedule or {}),
    }


# ── Decision helper ───────────────────────────────────────────────────────────

def test_master_switch_off_always_silent():
    s = _settings(enabled=False, schedule={"enabled": True, "on_time": "00:00",
                                            "off_time": "23:59", "days": list(range(7))})
    assert _sound_allowed_at(s, _now(12)) is False


def test_no_schedule_always_on():
    assert _sound_allowed_at(_settings(), _now(3)) is True


def test_inside_window_on_outside_off():
    sched = {"enabled": True, "on_time": "09:00", "off_time": "22:00", "days": list(range(7))}
    s = _settings(schedule=sched)
    assert _sound_allowed_at(s, _now(12)) is True     # midday → on
    assert _sound_allowed_at(s, _now(23)) is False    # late night → off
    assert _sound_allowed_at(s, _now(7)) is False     # early morning → off


def test_overnight_window():
    sched = {"enabled": True, "on_time": "18:00", "off_time": "02:00", "days": list(range(7))}
    s = _settings(schedule=sched)
    assert _sound_allowed_at(s, _now(20)) is True     # evening → on
    assert _sound_allowed_at(s, _now(1)) is True      # after midnight → still on
    assert _sound_allowed_at(s, _now(12)) is False    # midday → off


def test_day_restriction():
    # Only Mondays (weekday 0). 2026-07-20 is Monday, 07-21 Tuesday.
    sched = {"enabled": True, "on_time": "00:00", "off_time": "23:59", "days": [0]}
    s = _settings(schedule=sched)
    assert _sound_allowed_at(s, _now(12, weekday_iso="2026-07-20")) is True
    assert _sound_allowed_at(s, _now(12, weekday_iso="2026-07-21")) is False


def test_malformed_schedule_is_ignored():
    s = {"sound_enabled": "true", "sound_schedule": "not json"}
    assert _sound_allowed_at(s, _now(12)) is True


# ── Broadcast carries the flag ────────────────────────────────────────────────

async def test_forced_sound_push_marks_broadcast(client, monkeypatch):
    """A push with sound=true must broadcast sound=true even when the schedule
    would otherwise silence the board."""
    captured = {}

    async def fake_broadcast(screen_id, msg):
        captured.update(msg)

    monkeypatch.setattr(main.manager, "broadcast", fake_broadcast)
    main._sound_state["allowed"] = False  # schedule currently OFF

    await client.post("/api/display/text?screen=main",
                      json={"text": "CLOSING TIME", "sound": True})
    assert captured.get("sound") is True


async def test_normal_push_follows_schedule(client, monkeypatch):
    captured = {}

    async def fake_broadcast(screen_id, msg):
        captured.update(msg)

    monkeypatch.setattr(main.manager, "broadcast", fake_broadcast)
    main._sound_state["allowed"] = False

    await client.post("/api/display/text?screen=main", json={"text": "QUIET"})
    assert captured.get("sound") is False

    main._sound_state["allowed"] = True
    await client.post("/api/display/text?screen=main", json={"text": "LOUD"})
    assert captured.get("sound") is True


async def test_mqtt_sound_override(client, monkeypatch):
    captured = {}

    async def fake_broadcast(screen_id, msg):
        captured.update(msg)

    monkeypatch.setattr(main.manager, "broadcast", fake_broadcast)
    main._sound_state["allowed"] = False

    await main._mqtt_dispatch("main", "text", None,
                              json.dumps({"text": "PING", "sound": True}))
    assert captured.get("sound") is True


async def test_settings_roundtrip_schedule(client):
    sched = {"enabled": True, "on_time": "11:00", "off_time": "16:00", "days": [0, 1, 2]}
    r = await client.put("/api/settings", json={"sound_schedule": sched})
    assert r.status_code == 200
    got = json.loads(r.json()["sound_schedule"])
    assert got == sched
