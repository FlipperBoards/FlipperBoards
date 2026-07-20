"""Pirate Weather payload parsing (Dark Sky format) + coordinate locations."""
from services.weather import parse_pirate, resolve_coords


def test_resolve_coords_decimal():
    assert resolve_coords("33.41345148121321, -111.60386860370637") == \
        (33.41345148121321, -111.60386860370637, "LOCAL", "")


def test_resolve_coords_with_label():
    lat, lon, city, country = resolve_coords("Home | 33.413, -111.604")
    assert (lat, lon) == (33.413, -111.604)
    assert city == "HOME" and country == ""


def test_resolve_coords_dms():
    lat, lon, city, _ = resolve_coords("33°26'43.8\"N 111°59'21.0\"W")
    assert abs(lat - 33.4455) < 1e-4
    assert abs(lon + 111.9892) < 1e-4
    assert city == "LOCAL"


def test_resolve_coords_rejects_names():
    assert resolve_coords("Portland,US") is None
    assert resolve_coords("Home | not coords") is None


def _payload():
    return {
        "currently": {
            "temperature": 72.4,
            "apparentTemperature": 74.9,
            "humidity": 0.63,
            "summary": "Partly Cloudy",
        },
        "daily": {"data": [{"temperatureHigh": 81.2, "temperatureLow": 58.7}]},
    }


def test_parse_pirate_fields():
    w = parse_pirate(_payload())
    assert w == {"temp": 72, "feels": 75, "humidity": 63,
                 "desc": "PARTLY CLOUDY", "high": 81, "low": 59}


def test_parse_pirate_missing_daily():
    p = _payload()
    del p["daily"]
    w = parse_pirate(p)
    assert w["high"] == w["temp"] and w["low"] == w["temp"]


def test_parse_pirate_malformed():
    assert parse_pirate({}) is None
    assert parse_pirate({"currently": {}}) is None
    assert parse_pirate({"currently": {"temperature": "n/a"}}) is None
