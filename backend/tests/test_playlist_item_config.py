"""Per-item mode config: a mode playlist item carries its own config, so two
items of the same mode can render with different settings, and the live tick
loop honors the item's config."""
import main


async def _add_mode(client, mode, config, duration=30, screen="main"):
    r = await client.post(f"/api/playlist?screen={screen}",
                          json={"type": "mode",
                                "content": {"mode": mode, "config": config},
                                "duration": duration})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def test_item_config_persists(clean_playlist):
    client = clean_playlist
    await _add_mode(client, "news", {"keyword": "Suns", "topics": ["SPORTS"]})
    items = (await client.get("/api/playlist?screen=main")).json()
    cfg = items[-1]["content"]["config"]
    assert cfg["keyword"] == "Suns"
    assert cfg["topics"] == ["SPORTS"]


async def test_two_countdown_items_render_differently(clean_playlist):
    client = clean_playlist
    # Two countdown items with different targets/labels — different output
    await _add_mode(client, "countdown", {"target": "2030-01-01 00:00", "label": "ALPHA"})
    await _add_mode(client, "countdown", {"target": "2031-06-15 00:00", "label": "BRAVO"})
    await client.post("/api/playlist/play?screen=main")

    from charmap import CHARS

    def board_text():
        m = main._screens["main"].matrix
        return " ".join("".join(CHARS[c] if c < 71 else "#" for c in row) for row in m)

    # play lands on item 0 (ALPHA)
    first = board_text()
    await client.post("/api/display/next?screen=main")
    second = board_text()
    assert ("ALPHA" in first) != ("ALPHA" in second)  # the two items differ
    assert "ALPHA" in first or "BRAVO" in first
    assert "ALPHA" in second or "BRAVO" in second


async def test_mode_config_tracks_active_item(clean_playlist):
    client = clean_playlist
    await _add_mode(client, "countdown", {"target": "2030-01-01 00:00", "label": "ALPHA"})
    await _add_mode(client, "countdown", {"target": "2031-06-15 00:00", "label": "BRAVO"})
    await client.post("/api/playlist/play?screen=main")
    state = main._screens["main"]
    # state.mode_config mirrors the on-screen item so the 1s tick re-renders it right
    assert state.mode == "countdown"
    assert state.mode_config.get("label") in ("ALPHA", "BRAVO")
    label_before = state.mode_config["label"]
    await client.post("/api/display/next?screen=main")
    assert state.mode_config["label"] != label_before


async def test_legacy_item_without_config_uses_screen_config(clean_playlist):
    client = clean_playlist
    # An item saved the old way — no "config" key — must still render (falls
    # back to the screen's mode config, no crash)
    r = await client.post("/api/playlist?screen=main",
                          json={"type": "mode", "content": {"mode": "clock"}, "duration": 30})
    assert r.status_code in (200, 201)
    await client.post("/api/playlist/play?screen=main")
    assert main._screens["main"].mode == "clock"
