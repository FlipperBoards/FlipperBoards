"""Named playlist sets: CRUD, item scoping to a set, active-set resolution
(schedule window / manual / first), and switching sets reloads the rotation.

Each test runs on its own freshly-created screen so set state never leaks
between tests (the suite shares one DB file)."""
import uuid
from datetime import datetime

import pytest_asyncio

import main


@pytest_asyncio.fixture()
async def screen(client):
    """A unique screen id with its client — isolated set/playlist state."""
    sid = "s" + uuid.uuid4().hex[:8]
    r = await client.post("/api/screens", json={"id": sid, "name": "Test"})
    assert r.status_code in (200, 201), r.text
    return client, sid


async def _add(client, sid, text, set_id=None):
    qs = f"?screen={sid}" + (f"&set={set_id}" if set_id is not None else "")
    r = await client.post(f"/api/playlist{qs}",
                          json={"type": "text", "content": {"text": text}, "duration": 30})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _sets(client, sid):
    return (await client.get(f"/api/playlist/sets?screen={sid}")).json()


async def test_default_set_created(screen):
    client, sid = screen
    sets = await _sets(client, sid)
    assert len(sets) == 1
    assert sets[0]["name"] == "Playlist"
    assert sets[0]["active"] is True


async def test_sets_include_content_preview(screen):
    client, sid = screen
    set_a = (await _sets(client, sid))[0]["id"]
    await client.post(f"/api/playlist?screen={sid}&set={set_a}",
                      json={"type": "mode", "content": {"mode": "news"}, "duration": 30})
    await _add(client, sid, "HI", set_id=set_a)
    s = (await _sets(client, sid))[0]
    assert s["item_count"] == 2
    assert s["preview"][0] == {"type": "mode", "mode": "news"}
    assert s["preview"][1]["type"] == "text"


async def test_items_scoped_to_sets(screen):
    client, sid = screen
    set_a = (await _sets(client, sid))[0]["id"]
    set_b = (await client.post(f"/api/playlist/sets?screen={sid}", json={"name": "Lunch"})).json()["id"]

    await _add(client, sid, "ALPHA", set_id=set_a)
    await _add(client, sid, "BRAVO", set_id=set_b)

    items_a = (await client.get(f"/api/playlist?screen={sid}&set={set_a}")).json()
    items_b = (await client.get(f"/api/playlist?screen={sid}&set={set_b}")).json()
    assert [i["content"]["text"] for i in items_a] == ["ALPHA"]
    assert [i["content"]["text"] for i in items_b] == ["BRAVO"]


async def test_activate_switches_rotation(screen):
    client, sid = screen
    set_a = (await _sets(client, sid))[0]["id"]
    set_b = (await client.post(f"/api/playlist/sets?screen={sid}", json={"name": "Night"})).json()["id"]
    await _add(client, sid, "DAYTIME", set_id=set_a)
    await _add(client, sid, "NIGHTTIME", set_id=set_b)

    r = await client.post(f"/api/playlist/sets/{set_b}/activate?screen={sid}")
    assert r.status_code == 200
    state = main._screens[sid]
    assert state.active_set_id == set_b
    assert [i["content"]["text"] for i in state.playlist_items] == ["NIGHTTIME"]
    sets = await _sets(client, sid)
    assert next(s for s in sets if s["id"] == set_b)["active"] is True


async def test_scheduled_set_wins(screen, monkeypatch):
    client, sid = screen
    base = (await _sets(client, sid))[0]["id"]
    lunch = (await client.post(f"/api/playlist/sets?screen={sid}", json={"name": "Lunch"})).json()["id"]
    await _add(client, sid, "ALLDAY", set_id=base)
    await _add(client, sid, "LUNCHSPECIAL", set_id=lunch)

    await client.put(f"/api/playlist/sets/{lunch}?screen={sid}",
                     json={"schedule": {"enabled": True, "start_time": "11:00",
                                        "end_time": "14:00", "days": [0, 1, 2, 3, 4, 5, 6]}})

    async def noon():
        return datetime(2026, 7, 21, 12, 0, 0)
    monkeypatch.setattr(main, "_now_local", noon)
    state = main._screens[sid]
    assert await main._resolve_active_set(state) == lunch

    async def evening():
        return datetime(2026, 7, 21, 20, 0, 0)
    monkeypatch.setattr(main, "_now_local", evening)
    assert await main._resolve_active_set(state) == base  # outside window → first set


async def test_delete_set_cascades(screen):
    client, sid = screen
    extra = (await client.post(f"/api/playlist/sets?screen={sid}", json={"name": "Temp"})).json()["id"]
    item_id = await _add(client, sid, "GONE", set_id=extra)

    r = await client.delete(f"/api/playlist/sets/{extra}?screen={sid}")
    assert r.status_code == 200
    allitems = (await client.get(f"/api/playlist?screen={sid}&set={extra}")).json()
    assert not any(i["id"] == item_id for i in allitems)


async def test_cannot_delete_only_set(screen):
    client, sid = screen
    only = (await _sets(client, sid))[0]["id"]
    r = await client.delete(f"/api/playlist/sets/{only}?screen={sid}")
    assert r.status_code == 400
