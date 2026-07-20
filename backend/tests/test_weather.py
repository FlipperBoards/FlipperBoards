"""Pirate Weather payload parsing (Dark Sky format)."""
from services.weather import parse_pirate


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
