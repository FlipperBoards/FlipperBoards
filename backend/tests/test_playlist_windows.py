"""Playlist dayparting: item time windows, eligibility skipping, menu items."""
from datetime import datetime

import pytz

import main
from charmap import CHARS
from services.menu import get_menu_matrix


def _dt(weekday: int, hour: int, minute: int = 0):
    # 2026-07-13 is a Monday
    return pytz.utc.localize(datetime(2026, 7, 13 + weekday, hour, minute))


def _text(matrix):
    return ["".join(CHARS[c] if c < 71 else "#" for c in row) for row in matrix]


def test_item_eligibility():
    lunch = {"window": {"enabled": True, "start_time": "11:00", "end_time": "16:00",
                        "days": [0, 1, 2, 3, 4]}}
    always = {"window": {}}
    assert main._item_eligible(lunch, _dt(0, 12))
    assert not main._item_eligible(lunch, _dt(0, 17))
    assert not main._item_eligible(lunch, _dt(5, 12))  # Saturday
    assert main._item_eligible(always, _dt(5, 3))


def test_overnight_item_window():
    late = {"window": {"enabled": True, "start_time": "22:00", "end_time": "02:00",
                       "days": [4]}}  # Friday night
    assert main._item_eligible(late, _dt(4, 23))
    assert main._item_eligible(late, _dt(5, 1))   # Saturday 1am (Friday spillover)
    assert not main._item_eligible(late, _dt(5, 3))


async def test_windowed_item_skipped_in_rotation(clean_playlist, monkeypatch):
    client = clean_playlist
    # Freeze "now" at noon so the 03:00-03:01 window is deterministically
    # outside — days=[] is NOT impossible (empty coerces to every day)
    import main
    frozen = datetime(2026, 7, 21, 12, 0, 0)   # a Tuesday, 12:00

    async def _fixed_now():
        return frozen
    monkeypatch.setattr(main, "_now_local", _fixed_now)

    r = await client.post("/api/playlist?screen=main",
                          json={"type": "text", "content": {"text": "ALWAYS"}, "duration": 60})
    assert r.status_code in (200, 201)
    r = await client.post("/api/playlist?screen=main",
                          json={"type": "text", "content": {"text": "NEVER"}, "duration": 60,
                                "window": {"enabled": True, "start_time": "03:00",
                                           "end_time": "03:01", "days": []}})
    assert r.status_code in (200, 201)

    await client.post("/api/playlist/play?screen=main")
    # Advance twice: must land on ALWAYS both times, never on NEVER
    for _ in range(2):
        await client.post("/api/display/next?screen=main")
        s = (await client.get("/api/state?screen=main")).json()
        assert s["playlist_pos"] == 0


async def test_all_items_windowed_out_falls_back_to_clock(clean_playlist, monkeypatch):
    client = clean_playlist
    import main
    frozen = datetime(2026, 7, 21, 12, 0, 0)

    async def _fixed_now():
        return frozen
    monkeypatch.setattr(main, "_now_local", _fixed_now)

    r = await client.post("/api/playlist?screen=main",
                          json={"type": "text", "content": {"text": "GHOST"}, "duration": 60,
                                "window": {"enabled": True, "start_time": "03:00",
                                           "end_time": "03:01", "days": []}})
    assert r.status_code in (200, 201)
    await client.post("/api/display/next?screen=main")
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "clock"


async def test_window_roundtrip_and_validation(clean_playlist):
    client = clean_playlist
    r = await client.post("/api/playlist?screen=main",
                          json={"type": "text", "content": {"text": "LUNCH"}, "duration": 60,
                                "window": {"enabled": True, "start_time": "11:00",
                                           "end_time": "16:00", "days": [0, 1]}})
    items = (await client.get("/api/playlist?screen=main")).json()
    assert items[0]["window"]["start_time"] == "11:00"
    assert items[0]["window"]["days"] == [0, 1]

    r = await client.post("/api/playlist?screen=main",
                          json={"type": "text", "content": {"text": "X"}, "duration": 60,
                                "window": {"enabled": True, "start_time": "25:00",
                                           "end_time": "16:00", "days": [0]}})
    assert r.status_code == 422


def test_menu_layout():
    m = get_menu_matrix(6, 22, title="HAPPY HOUR",
                        entries=[{"name": "IPA Draft", "price": "6.50"},
                                 {"name": "House Red", "price": "8.00"}])
    rows = _text(m)
    assert "HAPPY HOUR" in rows[0]
    assert rows[1].strip() == ""  # spacer
    assert rows[2].startswith("IPA DRAFT")
    assert rows[2].endswith("6.50")
    assert "·" in rows[2]  # dot leaders
    assert rows[3].endswith("8.00")


def test_menu_price_change_flips_digits_only():
    a = get_menu_matrix(6, 22, "", [{"name": "IPA", "price": "6.50"}])
    b = get_menu_matrix(6, 22, "", [{"name": "IPA", "price": "7.50"}])
    diff = [(r, c) for r in range(6) for c in range(22) if a[r][c] != b[r][c]]
    assert len(diff) == 1


def test_menu_pagination():
    from services import menu as menu_svc
    menu_svc._cursor.clear()
    entries = [{"name": f"ITEM {i}", "price": str(i)} for i in range(1, 11)]
    a = get_menu_matrix(4, 22, "", entries, screen_id="pg")
    b = get_menu_matrix(4, 22, "", entries, screen_id="pg")
    assert a != b  # second render shows the next page


async def test_menu_playlist_item(clean_playlist):
    client = clean_playlist
    r = await client.post("/api/playlist?screen=main",
                          json={"type": "menu",
                                "content": {"title": "DRINKS",
                                            "entries": [{"name": "BEER", "price": "5"}]},
                                "duration": 60})
    assert r.status_code in (200, 201)
    await client.post("/api/playlist/play?screen=main")
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "menu"
    rows = _text(s["matrix"])
    assert any("DRINKS" in r_ for r_ in rows)
    assert any(r_.strip().endswith("5") and "BEER" in r_ for r_ in rows)
