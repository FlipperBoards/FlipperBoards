async def _add(client, screen="main", type="text", content=None, duration=30):
    r = await client.post(f"/api/playlist?screen={screen}",
                          json={"type": type,
                                "content": content or {"text": "HI"},
                                "duration": duration})
    assert r.status_code == 200 or r.status_code == 201, r.text
    return r.json()["id"]


async def test_crud_roundtrip(clean_playlist):
    client = clean_playlist
    item_id = await _add(client)
    items = (await client.get("/api/playlist?screen=main")).json()
    assert any(i["id"] == item_id for i in items)

    r = await client.put(f"/api/playlist/{item_id}?screen=main",
                         json={"type": "text", "content": {"text": "BYE"}, "duration": 45})
    assert r.status_code == 200
    items = (await client.get("/api/playlist?screen=main")).json()
    updated = next(i for i in items if i["id"] == item_id)
    assert updated["content"]["text"] == "BYE" and updated["duration"] == 45

    r = await client.delete(f"/api/playlist/{item_id}?screen=main")
    assert r.status_code == 200


async def test_cross_screen_mutation_blocked(clean_playlist):
    client = clean_playlist
    r = await client.post("/api/screens",
                          json={"id": "scopetest", "name": "Scope"})
    assert r.status_code in (201, 409)
    item_id = await _add(client, screen="scopetest")
    try:
        # Editing/deleting another screen's item via ?screen=main must 404
        r = await client.put(f"/api/playlist/{item_id}?screen=main",
                             json={"type": "text", "content": {"text": "X"}, "duration": 30})
        assert r.status_code == 404
        r = await client.delete(f"/api/playlist/{item_id}?screen=main")
        assert r.status_code == 404
        # Still deletable through its own screen
        r = await client.delete(f"/api/playlist/{item_id}?screen=scopetest")
        assert r.status_code == 200
    finally:
        await client.delete("/api/screens/scopetest")


async def test_play_and_jump(clean_playlist):
    client = clean_playlist
    await _add(client, content={"text": "ONE"})
    await _add(client, content={"text": "TWO"})

    r = await client.post("/api/playlist/play?screen=main")
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    assert s["playlist_pos"] == 0

    r = await client.post("/api/playlist/jump?screen=main", json={"pos": 1})
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    assert s["playlist_pos"] == 1

    r = await client.post("/api/playlist/jump?screen=main", json={"pos": 9})
    assert r.status_code == 400


async def test_scoreboard_item_and_live_update(clean_playlist):
    client = clean_playlist
    item_id = await _add(client, type="scoreboard",
                         content={"home_name": "HAWKS", "away_name": "OWLS",
                                  "home_score": 0, "away_score": 0},
                         duration=60)
    await client.post("/api/playlist/play?screen=main")
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "scoreboard"
    before = s["matrix"]

    r = await client.put(f"/api/playlist/{item_id}?screen=main",
                         json={"type": "scoreboard",
                               "content": {"home_name": "HAWKS", "away_name": "OWLS",
                                           "home_score": 1, "away_score": 0},
                               "duration": 60})
    assert r.status_code == 200
    after = (await client.get("/api/state?screen=main")).json()["matrix"]
    diff = [(r_, c) for r_ in range(6) for c in range(22) if before[r_][c] != after[r_][c]]
    assert len(diff) == 1  # only the bumped digit changed


async def test_delete_current_item_rerenders(clean_playlist):
    client = clean_playlist
    first = await _add(client, content={"text": "FIRST"})
    await _add(client, content={"text": "SECOND"})
    await client.post("/api/playlist/play?screen=main")

    r = await client.delete(f"/api/playlist/{first}?screen=main")
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    # remaining item is rendered, pos clamped
    assert s["playlist_pos"] == 0
    assert s["mode"] == "text_push"


async def test_playlist_duration_validation(clean_playlist):
    client = clean_playlist
    r = await client.post("/api/playlist?screen=main",
                          json={"type": "text", "content": {"text": "X"}, "duration": 0})
    assert r.status_code == 422
