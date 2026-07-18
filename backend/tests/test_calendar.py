from datetime import datetime

import pytz

from services.calendar_svc import _parse_ical_dt


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
