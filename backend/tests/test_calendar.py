from datetime import datetime

import pytz

from charmap import CHARS
from services import calendar_svc
from services.calendar_svc import _compact_time, _parse_ical_dt, get_calendar_matrix


# ── Date parsing (unchanged behavior) ─────────────────────────────────────────

def test_utc_z_converted_to_local():
    tz = pytz.timezone("America/Chicago")
    dt = _parse_ical_dt("20260701T180000Z", tz)
    # 18:00 UTC == 13:00 Chicago (CDT)
    assert dt.hour == 13
    assert dt.tzinfo is not None


def test_naive_treated_as_local():
    tz = pytz.timezone("America/Chicago")
    dt = _parse_ical_dt("20260701T180000", tz)
    assert dt.hour == 18


def test_date_only():
    tz = pytz.utc
    dt = _parse_ical_dt("20260701", tz)
    assert dt == tz.localize(datetime(2026, 7, 1))


def test_garbage_returns_none():
    assert _parse_ical_dt("not-a-date", pytz.utc) is None


# ── Compact time ──────────────────────────────────────────────────────────────

def _at(hour, minute=0):
    return pytz.utc.localize(datetime(2026, 7, 20, hour, minute))


def test_compact_time_on_the_hour():
    assert _compact_time(_at(19)) == "7P"
    assert _compact_time(_at(11)) == "11A"


def test_compact_time_with_minutes():
    assert _compact_time(_at(11, 15)) == "11:15A"
    assert _compact_time(_at(19, 30)) == "7:30P"


def test_compact_time_noon_and_midnight():
    assert _compact_time(_at(12)) == "12P"
    assert _compact_time(_at(0)) == "12A"


# ── Rendered layout ───────────────────────────────────────────────────────────

def _text(matrix):
    return ["".join(CHARS[c] if c < 71 else "#" for c in row).rstrip() for row in matrix]


async def _render(monkeypatch, events, rows=6, cols=22):
    async def fake_fetch(url, tz):
        return events
    monkeypatch.setattr(calendar_svc, "_fetch_events", fake_fetch)
    return _text(await get_calendar_matrix(rows, cols, ical_url="x"))


async def test_short_date_and_maximized_title(monkeypatch):
    events = [{"start": _at(19), "title": "Putting Practice", "all_day": False}]
    rows = await _render(monkeypatch, events)
    assert rows[0].strip() == "UPCOMING EVENTS"
    line = rows[1]
    # Numeric date, full title (16 <= ~15 avail? fits mostly), compact time
    assert line.startswith("7/20 ")
    assert line.endswith("7P")
    assert "PUTTING PRAC" in line          # far more than the old "PUT."
    assert "JUL" not in line and "MON" not in line


async def test_short_title_fully_intact(monkeypatch):
    events = [{"start": _at(11, 15), "title": "Dentist", "all_day": False}]
    line = (await _render(monkeypatch, events))[1]
    assert line.startswith("7/20 DENTIST")
    assert line.endswith("11:15A")
    assert "." not in line.replace("11:15A", "")  # no truncation dot


async def test_long_title_truncates_with_dot(monkeypatch):
    events = [{"start": _at(12), "title": "Quarterly Budget Review Meeting", "all_day": False}]
    line = (await _render(monkeypatch, events))[1]
    assert line.startswith("7/20 QUARTERLY")
    assert line.rstrip().endswith("12P")
    assert "." in line  # truncated


async def test_all_day_event_shows_no_time(monkeypatch):
    events = [{"start": _at(0), "title": "Company Holiday", "all_day": True}]
    line = (await _render(monkeypatch, events))[1]
    assert line.startswith("7/20 COMPANY HOLIDAY")
    assert "12A" not in line          # not rendered as midnight
    assert not line.rstrip().endswith("A") and not line.rstrip().endswith("P")


async def test_no_url_message(monkeypatch):
    m = _text(await get_calendar_matrix(6, 22, ical_url=""))
    assert any("NO ICAL URL" in r for r in m)
