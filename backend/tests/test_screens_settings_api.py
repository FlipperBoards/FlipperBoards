async def test_screen_crud(client):
    r = await client.post("/api/screens", json={"id": "t1", "name": "T1", "rows": 4, "cols": 10})
    assert r.status_code == 201
    try:
        screens = (await client.get("/api/screens")).json()
        t1 = next(s for s in screens if s["id"] == "t1")
        assert t1["rows"] == 4 and t1["cols"] == 10

        r = await client.put("/api/screens/t1", json={"name": "T1b", "rows": 5, "cols": 12})
        assert r.status_code == 200
        s = (await client.get("/api/state?screen=t1")).json()
        assert s["rows"] == 5 and s["cols"] == 12
    finally:
        assert (await client.delete("/api/screens/t1")).status_code == 200


async def test_screen_dimension_bounds(client):
    r = await client.post("/api/screens", json={"id": "big", "name": "B", "rows": 100000, "cols": 5})
    assert r.status_code == 422
    r = await client.post("/api/screens", json={"id": "zero", "name": "Z", "rows": 0, "cols": 5})
    assert r.status_code == 422


async def test_invalid_screen_id_rejected(client):
    r = await client.post("/api/screens", json={"id": "Bad Name!", "name": "X"})
    assert r.status_code == 400


async def test_cannot_delete_main(client):
    r = await client.delete("/api/screens/main")
    assert r.status_code == 400


async def test_rotation_interval_floor(client):
    r = await client.put("/api/settings", json={"rotation_interval": 0})
    assert r.status_code == 422
    r = await client.put("/api/settings", json={"rotation_interval": 30})
    assert r.status_code == 200


async def test_settings_roundtrip(client):
    r = await client.put("/api/settings", json={"tile_color": "#123456"})
    assert r.status_code == 200
    s = (await client.get("/api/settings")).json()
    assert s["tile_color"] == "#123456"


async def test_api_404_is_json_not_spa(client):
    r = await client.get("/api/does-not-exist")
    assert r.status_code == 404
