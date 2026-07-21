"""Exercise the MQTT command dispatch directly — no broker needed.
The dispatch calls the same handler functions as REST, so we assert on
resulting screen state via the API."""
import json

import main


async def test_text_command(client):
    await main._mqtt_dispatch("main", "text", None, "HELLO MQTT")
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "text_push"


async def test_text_command_json_payload(client):
    await main._mqtt_dispatch("main", "text", None,
                              json.dumps({"text": "HI", "duration": 30}))
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "text_push"


async def test_mode_command(client):
    await main._mqtt_dispatch("main", "mode", None, "clock")
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "clock"


def test_ha_set_selector_config():
    from mqtt_bridge import MQTTBridge

    class _S:
        screen_id = "main"
        name = "Main"
    bridge = MQTTBridge(dispatch=None, screens_provider=dict, modes_provider=list)
    topic, payload = bridge._set_select_config(_S(), ["Playlist", "Happy Hour"])
    assert topic.endswith("/select/flipperboards_main/set/config")
    assert payload["command_topic"] == "flipperboards/main/set/set"
    assert payload["state_topic"] == "flipperboards/main/set/state"
    assert payload["options"] == ["Playlist", "Happy Hour"]


async def test_set_command_activates_by_name(client):
    import uuid
    sid = "mq" + uuid.uuid4().hex[:8]
    await client.post("/api/screens", json={"id": sid, "name": "MQ"})
    # A second set named "Night" with an item
    night = (await client.post(f"/api/playlist/sets?screen={sid}",
                               json={"name": "Night"})).json()["id"]
    await client.post(f"/api/playlist?screen={sid}&set={night}",
                      json={"type": "text", "content": {"text": "CLOSED"}, "duration": 30})

    await main._mqtt_dispatch(sid, "set", None, "Night")   # activate by name
    assert main._screens[sid].active_set_id == night

    # Unknown set name is ignored (no crash, active set unchanged)
    await main._mqtt_dispatch(sid, "set", None, "Nonexistent")
    assert main._screens[sid].active_set_id == night


async def test_blank_command(client):
    await main._mqtt_dispatch("main", "blank", None, "blank")
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "blank"


async def test_matrix_command_normalized(client):
    await main._mqtt_dispatch("main", "matrix", None,
                              json.dumps({"matrix": [[999, 1]]}))
    s = (await client.get("/api/state?screen=main")).json()
    assert s["rows"] == 6 and s["cols"] == 22
    assert s["matrix"][0][0] == 0  # clamped


async def test_scoreboard_command(client):
    r = await client.post("/api/playlist?screen=main",
                          json={"type": "scoreboard",
                                "content": {"home_name": "A", "away_name": "B",
                                            "home_score": 0, "away_score": 0},
                                "duration": 60})
    item_id = r.json()["id"]
    try:
        await main._mqtt_dispatch("main", "scoreboard", None,
                                  json.dumps({"home_score": 5}))
        items = (await client.get("/api/playlist?screen=main")).json()
        sb = next(i for i in items if i["id"] == item_id)
        assert sb["content"]["home_score"] == 5
    finally:
        await client.delete(f"/api/playlist/{item_id}?screen=main")


async def test_malformed_payloads_do_not_raise(client):
    # None of these may raise — a bad MQTT message must never kill the loop
    await main._mqtt_dispatch("main", "matrix", None, "not json")
    await main._mqtt_dispatch("main", "matrix", None, json.dumps({"nope": 1}))
    await main._mqtt_dispatch("main", "scoreboard", None, "garbage")
    await main._mqtt_dispatch("main", "playlist", None, "fly to the moon")
    await main._mqtt_dispatch("main", "design", None, "no such design")
    await main._mqtt_dispatch("main", "image", None, "999999")
    await main._mqtt_dispatch("main", "mode", None, "not-a-mode")
    await main._mqtt_dispatch("ghost-screen", "text", None, "HI")
    await main._mqtt_dispatch("main", "unknown-command", None, "x")


async def test_playlist_next_command(client):
    r = await client.post("/api/playlist?screen=main",
                          json={"type": "text", "content": {"text": "1"}, "duration": 30})
    id1 = r.json()["id"]
    r = await client.post("/api/playlist?screen=main",
                          json={"type": "text", "content": {"text": "2"}, "duration": 30})
    id2 = r.json()["id"]
    try:
        await client.post("/api/playlist/play?screen=main")
        pos0 = (await client.get("/api/state?screen=main")).json()["playlist_pos"]
        await main._mqtt_dispatch("main", "playlist", None, "next")
        pos1 = (await client.get("/api/state?screen=main")).json()["playlist_pos"]
        assert pos1 == (pos0 + 1) % 2
    finally:
        await client.delete(f"/api/playlist/{id1}?screen=main")
        await client.delete(f"/api/playlist/{id2}?screen=main")
