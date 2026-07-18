"""Auth flow: disabled by default; when enabled, mutations require a session
cookie, reads and the display stay open."""
import main


async def _disable(client):
    await client.post("/api/auth/configure", json={"enabled": False})


async def test_disabled_by_default_mutations_open(client):
    await _disable(client)
    r = await client.post("/api/display/text?screen=main", json={"text": "OPEN"})
    assert r.status_code == 200
    s = await client.get("/api/auth/status")
    assert s.json() == {"enabled": False, "authenticated": True}


async def test_enable_requires_password(client):
    await _disable(client)
    r = await client.post("/api/auth/configure", json={"enabled": True})
    assert r.status_code == 400  # no password ever set


async def test_full_auth_flow(client):
    await _disable(client)
    try:
        # Enable with a password — enabling client gets a session cookie
        r = await client.post("/api/auth/configure",
                              json={"enabled": True, "password": "staff123"})
        assert r.status_code == 200 and r.json()["enabled"] is True
        assert main.AUTH_COOKIE in r.cookies

        # The enabling client can still mutate
        r = await client.post("/api/display/text?screen=main", json={"text": "HI"})
        assert r.status_code == 200

        # A fresh client (no cookie) is blocked from mutations…
        client.cookies.clear()
        r = await client.post("/api/display/text?screen=main", json={"text": "NOPE"})
        assert r.status_code == 401
        r = await client.delete("/api/playlist/1?screen=main")
        assert r.status_code == 401

        # …but reads stay open (the display keeps working)
        assert (await client.get("/api/state?screen=main")).status_code == 200
        assert (await client.get("/api/screens")).status_code == 200

        # Wrong password rejected
        r = await client.post("/api/auth/login", json={"password": "wrong"})
        assert r.status_code == 401

        # Right password issues a session that unlocks mutations
        r = await client.post("/api/auth/login", json={"password": "staff123"})
        assert r.status_code == 200
        r = await client.post("/api/display/text?screen=main", json={"text": "STAFF"})
        assert r.status_code == 200

        # Logout revokes the session
        await client.post("/api/auth/logout")
        r = await client.post("/api/display/text?screen=main", json={"text": "AGAIN"})
        assert r.status_code == 401

        # Unauthenticated client cannot reconfigure auth
        r = await client.post("/api/auth/configure", json={"enabled": False})
        assert r.status_code == 401

        # Log back in to disable for the remaining tests
        await client.post("/api/auth/login", json={"password": "staff123"})
    finally:
        r = await client.post("/api/auth/configure", json={"enabled": False})
        assert r.status_code == 200


async def test_password_hash_never_leaves_server(client):
    await _disable(client)
    s = (await client.get("/api/settings")).json()
    assert "auth_password_hash" not in s


async def test_password_hashing_roundtrip():
    stored = main._hash_password("hunter2")
    assert main._verify_password("hunter2", stored)
    assert not main._verify_password("hunter3", stored)
    assert not main._verify_password("hunter2", "garbage")
    assert not main._verify_password("hunter2", "")
