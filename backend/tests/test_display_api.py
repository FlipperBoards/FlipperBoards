async def test_state_snapshot(client):
    r = await client.get("/api/state?screen=main")
    assert r.status_code == 200
    s = r.json()
    assert s["rows"] == 6 and s["cols"] == 22


async def test_push_text(client):
    r = await client.post("/api/display/text?screen=main", json={"text": "HELLO"})
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "text_push"
    assert any(any(row) for row in s["matrix"])


async def test_push_matrix_does_not_resize_screen(client):
    r = await client.post("/api/display/matrix?screen=main",
                          json={"matrix": [[1, 2], [3, 4]]})
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    assert s["rows"] == 6 and s["cols"] == 22
    assert len(s["matrix"]) == 6 and len(s["matrix"][0]) == 22


async def test_push_matrix_clamps_cell_values(client):
    await client.post("/api/display/matrix?screen=main",
                      json={"matrix": [[999, -1, 77, 78]]})
    s = (await client.get("/api/state?screen=main")).json()
    assert s["matrix"][0][:4] == [0, 0, 77, 0]


async def test_push_matrix_jagged_rows_padded(client):
    r = await client.post("/api/display/matrix?screen=main",
                          json={"matrix": [[1], [1, 2, 3], []]})
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    assert all(len(row) == 22 for row in s["matrix"])


async def test_push_empty_matrix_rejected(client):
    r = await client.post("/api/display/matrix?screen=main", json={"matrix": []})
    assert r.status_code == 400


async def test_negative_duration_rejected(client):
    r = await client.post("/api/display/text?screen=main",
                          json={"text": "X", "duration": -5})
    assert r.status_code == 422
    r = await client.post("/api/display/text?screen=main",
                          json={"text": "X", "duration": 0})
    assert r.status_code == 422


async def test_blank(client):
    r = await client.post("/api/display/blank?screen=main")
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "blank"
    assert not any(any(row) for row in s["matrix"])


async def test_push_mode(client):
    r = await client.post("/api/display/mode?screen=main", json={"mode": "clock"})
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "clock"


async def test_push_unknown_mode_rejected(client):
    r = await client.post("/api/display/mode?screen=main", json={"mode": "nope"})
    assert r.status_code == 400


async def test_unknown_screen_404(client):
    r = await client.post("/api/display/text?screen=ghost", json={"text": "X"})
    assert r.status_code == 404


async def test_color_matrix_padded_to_screen(client):
    r = await client.post("/api/display/color-matrix?screen=main",
                          json={"color_matrix": [["#ff0000"]]})
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    assert s["rows"] == 6 and s["cols"] == 22
