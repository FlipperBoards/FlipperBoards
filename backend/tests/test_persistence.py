"""Restart recovery: pushed content and playlist position survive a full
lifespan teardown + restart (same DB file)."""
import httpx
from asgi_lifespan import LifespanManager

import main


async def _client(manager):
    transport = httpx.ASGITransport(app=manager.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_pushed_text_survives_restart():
    async with LifespanManager(main.app) as m:
        async with await _client(m) as c:
            await c.post("/api/playlist/clear?screen=main")
            r = await c.post("/api/display/text?screen=main",
                             json={"text": "BACK IN 5"})
            assert r.status_code == 200
            before = (await c.get("/api/state?screen=main")).json()

    # "Restart" — fresh lifespan, same DB
    async with LifespanManager(main.app) as m:
        async with await _client(m) as c:
            after = (await c.get("/api/state?screen=main")).json()
            assert after["mode"] == "text_push"
            assert after["matrix"] == before["matrix"]
            # Restored pushes hold until changed — a manual next resumes rotation
            r = await c.post("/api/display/next?screen=main")
            assert r.status_code == 200


async def test_playlist_position_survives_restart():
    async with LifespanManager(main.app) as m:
        async with await _client(m) as c:
            await c.post("/api/playlist/clear?screen=main")
            for label in ("ONE", "TWO", "THREE"):
                await c.post("/api/playlist?screen=main",
                             json={"type": "text", "content": {"text": label},
                                   "duration": 60})
            await c.post("/api/playlist/play?screen=main")
            await c.post("/api/playlist/jump?screen=main", json={"pos": 2})
            assert (await c.get("/api/state?screen=main")).json()["playlist_pos"] == 2

    async with LifespanManager(main.app) as m:
        async with await _client(m) as c:
            s = (await c.get("/api/state?screen=main")).json()
            assert s["playlist_pos"] == 2
            await c.post("/api/playlist/clear?screen=main")


async def test_clock_screen_restarts_to_clock():
    async with LifespanManager(main.app) as m:
        async with await _client(m) as c:
            await c.post("/api/playlist/clear?screen=main")
            await c.post("/api/display/mode?screen=main", json={"mode": "clock"})

    async with LifespanManager(main.app) as m:
        async with await _client(m) as c:
            s = (await c.get("/api/state?screen=main")).json()
            assert s["mode"] == "clock"
