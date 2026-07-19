"""Countdown mode: pure renderer math (frozen now) + mode registration."""
from datetime import datetime

import pytz

from charmap import CHARS
from services.countdown import get_countdown_matrix, _parse_target

ROWS, COLS = 6, 22
TZ = pytz.timezone("America/New_York")


def _row_text(row):
    return "".join(CHARS[c] if c < len(CHARS) else "?" for c in row).strip()


def _lines(matrix):
    return [_row_text(r) for r in matrix if _row_text(r)]


def _frozen(s):
    return TZ.localize(datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))


def test_future_countdown_days_and_clock():
    now = _frozen("2026-07-19 12:00:00")
    m = get_countdown_matrix(ROWS, COLS, target="2026-07-21 15:30",
                             label="Launch", timezone="America/New_York", now=now)
    lines = _lines(m)
    assert lines == ["LAUNCH", "2 DAYS", "03:30:00"]


def test_same_day_countdown_has_no_days_line():
    now = _frozen("2026-07-19 12:00:00")
    m = get_countdown_matrix(ROWS, COLS, target="2026-07-19 13:00",
                             timezone="America/New_York", now=now)
    assert _lines(m) == ["01:00:00"]


def test_one_day_singular():
    now = _frozen("2026-07-19 12:00:00")
    m = get_countdown_matrix(ROWS, COLS, target="2026-07-20 14:00",
                             timezone="America/New_York", now=now)
    assert "1 DAY" in _lines(m)


def test_past_target_shows_done_text():
    now = _frozen("2026-07-19 12:00:00")
    m = get_countdown_matrix(ROWS, COLS, target="2026-01-01",
                             label="New Years", timezone="America/New_York", now=now)
    lines = _lines(m)
    assert lines == ["NEW YEARS", "IT'S TIME!"]


def test_past_target_custom_done_text():
    now = _frozen("2026-07-19 12:00:00")
    m = get_countdown_matrix(ROWS, COLS, target="2026-01-01",
                             done_text="Happy 2026", timezone="America/New_York", now=now)
    assert "HAPPY 2026" in _lines(m)


def test_count_up_from_past():
    now = _frozen("2026-07-19 12:00:00")
    m = get_countdown_matrix(ROWS, COLS, target="2026-07-18 12:00",
                             label="Sober", count_up=True,
                             timezone="America/New_York", now=now)
    assert _lines(m) == ["SOBER", "1 DAY", "00:00:00"]


def test_invalid_target_prompts_config():
    m = get_countdown_matrix(ROWS, COLS, target="not-a-date")
    assert _lines(m) == ["SET A TARGET DATE"]
    m = get_countdown_matrix(ROWS, COLS, target="")
    assert _lines(m) == ["SET A TARGET DATE"]


def test_parse_target_formats():
    tz = pytz.utc
    assert _parse_target("2026-01-01 00:00:00", tz) is not None
    assert _parse_target("2026-01-01 00:00", tz) is not None
    assert _parse_target("2026-01-01T00:00", tz) is not None
    assert _parse_target("2026-01-01", tz) is not None
    assert _parse_target("jan 1", tz) is None


def test_seconds_tick_only_flips_second_digits():
    """1s later, only the seconds digits of the clock row change."""
    now1 = _frozen("2026-07-19 12:00:00")
    now2 = _frozen("2026-07-19 12:00:01")
    kwargs = dict(target="2026-07-21 15:30", label="Launch",
                  timezone="America/New_York")
    m1 = get_countdown_matrix(ROWS, COLS, now=now1, **kwargs)
    m2 = get_countdown_matrix(ROWS, COLS, now=now2, **kwargs)
    diff = [(r, c) for r in range(ROWS) for c in range(COLS)
            if m1[r][c] != m2[r][c]]
    # 03:30:00 → 03:29:59 — minute and second digits change, nothing else
    assert diff
    assert all(r == diff[0][0] for r, _ in diff)  # single row
    assert len(diff) <= 4


async def test_countdown_mode_registered(client):
    modes = (await client.get("/api/modes/available")).json()
    cd = next((m for m in modes if m["id"] == "countdown"), None)
    assert cd is not None
    assert "target" in cd["config_schema"]
