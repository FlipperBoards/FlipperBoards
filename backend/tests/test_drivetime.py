"""Drive Times mode: config parsing, Google Route Matrix parsing, row layout,
traffic accents, MQTT overrides (destinations + ready-made minutes), cache
staleness, and the mode registration — all with mocked fetches."""
import pytest

from charmap import CHARS
from services import drivetime
from services.drivetime import (GREEN, RED, YELLOW, entry_row,
                                get_drivetime_matrix, make_waypoint,
                                parse_destinations, parse_matrix, set_override)

ROWS, COLS = 6, 22


def _row_text(row):
    return "".join(CHARS[c] if 0 < c < 71 else " " for c in row).strip()


@pytest.fixture(autouse=True)
def _clean():
    drivetime._cache.clear()
    drivetime._override.clear()
    drivetime._cursor.clear()
    yield
    drivetime._cache.clear()
    drivetime._override.clear()
    drivetime._cursor.clear()


def _element(idx, secs, static=None, condition="ROUTE_EXISTS"):
    return {"originIndex": 0, "destinationIndex": idx,
            "duration": f"{secs}s", "staticDuration": f"{static or secs}s",
            "condition": condition}


# ── Config parsing ────────────────────────────────────────────────────────────

def test_parse_destinations_named_and_bare():
    text = "Home | 456 Oak Ave\nPDX Airport\n\n  Work  |  1 Main St  "
    dests = parse_destinations(text)
    assert dests == [
        {"name": "Home", "dest": "456 Oak Ave"},
        {"name": "PDX Airport", "dest": "PDX Airport"},
        {"name": "Work", "dest": "1 Main St"},
    ]


def test_parse_destinations_caps_at_six():
    text = "\n".join(f"D{i} | addr {i}" for i in range(9))
    assert len(parse_destinations(text)) == 6


# ── Waypoints: addresses vs coordinates ───────────────────────────────────────

def test_waypoint_coordinates():
    wp = make_waypoint("45.52, -122.68")
    assert wp == {"waypoint": {"location": {"latLng": {
        "latitude": 45.52, "longitude": -122.68}}}}
    wp = make_waypoint("-33.86,151.21")   # no space, southern hemisphere
    assert wp["waypoint"]["location"]["latLng"]["latitude"] == -33.86


def test_waypoint_dms_coordinates():
    # Exactly what Google Maps gives you on right-click → copy
    wp = make_waypoint('33°26\'43.8"N 111°59\'21.0"W')
    ll = wp["waypoint"]["location"]["latLng"]
    assert ll["latitude"] == pytest.approx(33.4455, abs=1e-4)
    assert ll["longitude"] == pytest.approx(-111.9892, abs=1e-4)

    # Southern/eastern hemispheres, typographic quotes, comma separator
    wp = make_waypoint("33°51’54.0”S, 151°12’36.0”E")
    ll = wp["waypoint"]["location"]["latLng"]
    assert ll["latitude"] == pytest.approx(-33.865, abs=1e-3)
    assert ll["longitude"] == pytest.approx(151.21, abs=1e-3)

    # Degrees-only DMS still parses
    wp = make_waypoint("45°N 122°W")
    assert wp["waypoint"]["location"]["latLng"]["latitude"] == 45.0


def test_waypoint_address_passthrough():
    assert make_waypoint("123 Main St, Portland OR") == \
        {"waypoint": {"address": "123 Main St, Portland OR"}}
    # Out-of-range numbers are not coordinates — "1234, 5678 Elm St" is an address
    assert "address" in make_waypoint("91.0, 200.0")["waypoint"]
    assert "address" in make_waypoint("PDX Airport")["waypoint"]
    assert "address" in make_waypoint('95°26\'43.8"N 111°59\'21.0"W')["waypoint"]


# ── Matrix response parsing + traffic accents ─────────────────────────────────

def test_parse_matrix_traffic_tiles():
    elements = [
        _element(0, 600, 600),    # no delay → green
        _element(1, 750, 600),    # 1.25x → yellow
        _element(2, 1200, 600),   # 2x → red
    ]
    out = parse_matrix(elements, ["A", "B", "C"])
    assert [e["tile"] for e in out] == [GREEN, YELLOW, RED]
    assert [e["minutes"] for e in out] == [10, 12, 20]  # 750s → 12.5 → banker's 12


def test_parse_matrix_missing_route():
    elements = [_element(0, 600), _element(1, 0, condition="ROUTE_NOT_FOUND")]
    out = parse_matrix(elements, ["A", "B"])
    assert out[0]["minutes"] == 10
    assert out[1]["minutes"] is None


# ── Row layout ────────────────────────────────────────────────────────────────

def test_entry_row_layout():
    row = entry_row({"name": "Home", "minutes": 23, "tile": GREEN}, COLS)
    assert len(row) == COLS
    assert row[0] == GREEN
    text = _row_text(row)
    assert text.startswith("HOME")
    assert text.endswith("23 MIN")
    assert drivetime.DOT in row  # dot leaders between name and time


def test_entry_row_long_times_use_hours():
    row = entry_row({"name": "Coast", "minutes": 125, "tile": GREEN}, COLS)
    assert _row_text(row).endswith("2H05")


def test_entry_row_unknown_time():
    row = entry_row({"name": "X", "minutes": None, "tile": 0}, COLS)
    assert _row_text(row).endswith("--")


# ── Full matrix ───────────────────────────────────────────────────────────────

async def test_matrix_renders_configured_destinations(monkeypatch):
    async def fake_fetch(api_key, origin, dests):
        return [_element(i, 600 * (i + 1)) for i in range(len(dests))]

    monkeypatch.setattr(drivetime, "_fetch_matrix", fake_fetch)
    m = await get_drivetime_matrix(ROWS, COLS, api_key="k", origin="Bar",
                                   destinations="Home | 1 A St\nWork | 2 B St")
    lines = [_row_text(r) for r in m if _row_text(r)]
    assert lines[0] == "DRIVE TIMES"
    assert lines[1].startswith("HOME") and lines[1].endswith("10 MIN")
    assert lines[2].startswith("WORK") and lines[2].endswith("20 MIN")


async def test_matrix_requires_key_and_origin():
    m = await get_drivetime_matrix(ROWS, COLS, api_key="", origin="Bar",
                                   destinations="Home | 1 A St")
    joined = " ".join(_row_text(r) for r in m)
    assert "GOOGLE MAPS API" in joined
    m = await get_drivetime_matrix(ROWS, COLS, api_key="k", origin="",
                                   destinations="Home | 1 A St")
    assert any("SET ORIGIN" in _row_text(r) for r in m)
    m = await get_drivetime_matrix(ROWS, COLS, api_key="k", origin="Bar",
                                   destinations="")
    assert any("ADD DESTINATIONS" in _row_text(r) for r in m)


async def test_stale_cache_survives_outage(monkeypatch):
    async def ok(api_key, origin, dests):
        return [_element(0, 600)]

    monkeypatch.setattr(drivetime, "_fetch_matrix", ok)
    await get_drivetime_matrix(ROWS, COLS, api_key="k", origin="Bar",
                               destinations="Home | 1 A St")
    key = next(iter(drivetime._cache))
    drivetime._cache[key] = (0.0, drivetime._cache[key][1])  # expire

    async def boom(api_key, origin, dests):
        raise RuntimeError("api down")

    monkeypatch.setattr(drivetime, "_fetch_matrix", boom)
    m = await get_drivetime_matrix(ROWS, COLS, api_key="k", origin="Bar",
                                   destinations="Home | 1 A St")
    assert any(_row_text(r).endswith("10 MIN") for r in m)


# ── MQTT overrides ────────────────────────────────────────────────────────────

async def test_override_with_ready_made_minutes():
    assert set_override("main", [
        {"name": "Home", "minutes": 17, "traffic": "heavy"},
        {"name": "Work", "minutes": 8},
    ])
    # No API key needed — times came over MQTT
    m = await get_drivetime_matrix(ROWS, COLS, api_key="", origin="",
                                   destinations="", screen_id="main")
    lines = [_row_text(r) for r in m if _row_text(r)]
    assert lines[1].startswith("HOME") and lines[1].endswith("17 MIN")
    assert lines[2].startswith("WORK") and lines[2].endswith("8 MIN")
    # traffic hint colors the accent tile
    home_row = next(r for r in m if _row_text(r).startswith("HOME"))
    assert home_row[0] == RED


async def test_override_destinations_computed(monkeypatch):
    async def fake_fetch(api_key, origin, dests):
        assert dests == ["9 Z St"]
        return [_element(0, 300)]

    monkeypatch.setattr(drivetime, "_fetch_matrix", fake_fetch)
    set_override("main", [{"name": "Gym", "dest": "9 Z St"}])
    m = await get_drivetime_matrix(ROWS, COLS, api_key="k", origin="Bar",
                                   destinations="Home | ignored", screen_id="main")
    lines = [_row_text(r) for r in m if _row_text(r)]
    assert lines[1].startswith("GYM")
    assert not any("HOME" in ln for ln in lines)


def test_override_clear_and_validation():
    assert set_override("main", [{"name": "A", "minutes": 5}])
    assert drivetime.get_override("main")
    assert set_override("main", None)          # clears
    assert drivetime.get_override("main") is None
    assert not set_override("main", "garbage")
    assert not set_override("main", [{"no_name": True}])


async def test_mqtt_dispatch_drivetime(client):
    import json as _json
    import main
    await main._mqtt_dispatch("main", "drivetime", None, _json.dumps(
        [{"name": "Home", "minutes": 12}]))
    assert drivetime.get_override("main")[0]["minutes"] == 12
    await main._mqtt_dispatch("main", "drivetime", None, "clear")
    assert drivetime.get_override("main") is None


# ── Registration ──────────────────────────────────────────────────────────────

async def test_mode_registered(client):
    modes = (await client.get("/api/modes/available")).json()
    dt = next((m for m in modes if m["id"] == "drivetime"), None)
    assert dt is not None
    assert "origin" in dt["config_schema"]
    assert "destinations" in dt["config_schema"]
