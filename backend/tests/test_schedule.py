"""Quiet-hours: window math, manual sleep/wake, schedule persistence."""
from datetime import datetime

import pytz

import main


def _dt(weekday: int, hour: int, minute: int = 0):
    # 2026-07-13 is a Monday (weekday 0)
    return pytz.utc.localize(datetime(2026, 7, 13 + weekday, hour, minute))


def test_same_day_window():
    sched = {"enabled": True, "off_time": "14:00", "on_time": "18:00", "days": [0]}
    assert main._in_quiet_window(_dt(0, 15), sched)
    assert not main._in_quiet_window(_dt(0, 13), sched)
    assert not main._in_quiet_window(_dt(0, 18), sched)   # end exclusive
    assert not main._in_quiet_window(_dt(1, 15), sched)   # Tuesday not selected


def test_overnight_window():
    sched = {"enabled": True, "off_time": "22:00", "on_time": "06:00", "days": [0]}
    assert main._in_quiet_window(_dt(0, 23), sched)       # Monday night
    assert main._in_quiet_window(_dt(1, 3), sched)        # spills into Tuesday morning
    assert not main._in_quiet_window(_dt(1, 7), sched)    # Tuesday after wake
    assert not main._in_quiet_window(_dt(1, 23), sched)   # Tuesday night not selected
    assert not main._in_quiet_window(_dt(0, 21), sched)


def test_disabled_and_invalid():
    assert not main._in_quiet_window(_dt(0, 12), {})
    assert not main._in_quiet_window(_dt(0, 12), {"enabled": False, "off_time": "00:00", "on_time": "23:59"})
    assert not main._in_quiet_window(_dt(0, 12), {"enabled": True, "off_time": "bad", "on_time": "06:00"})
    assert not main._in_quiet_window(_dt(0, 12), {"enabled": True, "off_time": "10:00", "on_time": "10:00"})


async def test_manual_sleep_wake(client):
    r = await client.post("/api/screens/main/sleep", json={"sleeping": True})
    assert r.status_code == 200 and r.json()["sleeping"] is True
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "sleep"
    assert not any(any(row) for row in s["matrix"])

    screens = (await client.get("/api/screens")).json()
    assert next(sc for sc in screens if sc["id"] == "main")["sleeping"] is True

    r = await client.post("/api/screens/main/sleep", json={"sleeping": False})
    assert r.status_code == 200 and r.json()["sleeping"] is False
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] != "sleep"


async def test_push_wakes_sleeping_screen(client):
    await client.post("/api/screens/main/sleep", json={"sleeping": True})
    r = await client.post("/api/display/text?screen=main", json={"text": "WAKE UP"})
    assert r.status_code == 200
    screens = (await client.get("/api/screens")).json()
    assert next(sc for sc in screens if sc["id"] == "main")["sleeping"] is False


async def test_schedule_roundtrip(client):
    sched = {"enabled": True, "off_time": "23:30", "on_time": "07:00", "days": [4, 5]}
    r = await client.put("/api/screens/main",
                         json={"name": "Main Display", "rows": 6, "cols": 22,
                               "schedule": sched})
    assert r.status_code == 200
    screens = (await client.get("/api/screens")).json()
    saved = next(sc for sc in screens if sc["id"] == "main")["schedule"]
    assert saved["enabled"] is True
    assert saved["off_time"] == "23:30" and saved["days"] == [4, 5]

    # invalid time rejected
    r = await client.put("/api/screens/main",
                         json={"name": "Main Display", "rows": 6, "cols": 22,
                               "schedule": {"enabled": True, "off_time": "25:99",
                                            "on_time": "07:00", "days": [0]}})
    assert r.status_code == 422

    # disable again for other tests
    r = await client.put("/api/screens/main",
                         json={"name": "Main Display", "rows": 6, "cols": 22,
                               "schedule": {"enabled": False, "off_time": "22:00",
                                            "on_time": "08:00", "days": [0, 1, 2, 3, 4, 5, 6]}})
    assert r.status_code == 200


async def test_mqtt_sleep_command(client):
    await main._mqtt_dispatch("main", "sleep", None, "on")
    screens = (await client.get("/api/screens")).json()
    assert next(sc for sc in screens if sc["id"] == "main")["sleeping"] is True
    await main._mqtt_dispatch("main", "sleep", None, "off")
    screens = (await client.get("/api/screens")).json()
    assert next(sc for sc in screens if sc["id"] == "main")["sleeping"] is False
