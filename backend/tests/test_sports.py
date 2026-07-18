"""Sports mode: ESPN payload parsing, rendering, rotation, and resilience —
all with a mocked fetch, no network."""
import pytest

from charmap import CHARS
from services import sports


def _event(home, away, hs, as_, state="in", detail="7:32 - 3rd"):
    return {
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": str(hs),
                 "team": {"abbreviation": home}},
                {"homeAway": "away", "score": str(as_),
                 "team": {"abbreviation": away}},
            ],
        }],
        "status": {"type": {"state": state, "shortDetail": detail}},
    }


FIXTURE = {"events": [
    _event("KC", "BUF", 21, 17, "in", "7:32 - 3rd"),
    _event("DAL", "PHI", 0, 0, "pre", "Sun 7:20 PM"),
    _event("SF", "SEA", 27, 24, "post", "Final"),
]}


@pytest.fixture(autouse=True)
def _mock_espn(monkeypatch):
    async def fake_fetch(path):
        return FIXTURE
    monkeypatch.setattr(sports, "_fetch_raw", fake_fetch)
    sports._cache.clear()
    sports._cursor.clear()
    yield


def _text(matrix):
    return ["".join(CHARS[c] if c < 71 else "#" for c in row).strip() for row in matrix]


async def test_parse_orders_live_first():
    games = await sports.get_games("nfl")
    assert [g["state"] for g in games] == ["in", "pre", "post"]
    assert games[0]["home_name"] == "KC" and games[0]["home_score"] == 21


async def test_team_filter_stays_on_game():
    m1 = await sports.get_sports_matrix(6, 22, league="nfl", team="KC")
    m2 = await sports.get_sports_matrix(6, 22, league="nfl", team="KC")
    assert m1 == m2  # no rotation when filtered to one game
    rows = _text(m1)
    assert any("KC" in r and "21" in r for r in rows)
    assert any("BUF" in r and "17" in r for r in rows)
    assert any("7:32 3RD" in r for r in rows)  # status line


async def test_rotation_cycles_games():
    a = await sports.get_sports_matrix(6, 22, league="nfl")
    b = await sports.get_sports_matrix(6, 22, league="nfl")
    assert a != b  # advanced to the next game


async def test_score_change_flips_one_digit():
    before = await sports.get_sports_matrix(6, 22, league="nfl", team="KC")
    FIXTURE["events"][0]["competitions"][0]["competitors"][0]["score"] = "24"
    sports._cache.clear()
    after = await sports.get_sports_matrix(6, 22, league="nfl", team="KC")
    diff = [(r, c) for r in range(6) for c in range(22) if before[r][c] != after[r][c]]
    assert diff == [(1, 21)]  # 21 -> 24: only the ones digit changes
    FIXTURE["events"][0]["competitions"][0]["competitors"][0]["score"] = "21"


async def test_no_games(monkeypatch):
    async def empty(path):
        return {"events": []}
    monkeypatch.setattr(sports, "_fetch_raw", empty)
    sports._cache.clear()
    m = await sports.get_sports_matrix(6, 22, league="nba")
    assert any("NO NBA GAMES TODAY" in r for r in _text(m))


async def test_api_failure_serves_stale_then_empty(monkeypatch):
    await sports.get_games("nfl")  # warm cache

    async def boom(path):
        raise RuntimeError("ESPN down")
    monkeypatch.setattr(sports, "_fetch_raw", boom)
    sports._cache["football/nfl"] = (0, sports._cache["football/nfl"][1])  # expire
    games = await sports.get_games("nfl")
    assert games and games[0]["home_name"] == "KC"  # stale beats blank

    sports._cache.clear()
    assert await sports.get_games("nfl") == []


async def test_mode_registered(client):
    modes = (await client.get("/api/modes/available")).json()
    sports_mode = next((m for m in modes if m["id"] == "sports"), None)
    assert sports_mode is not None
    assert "league" in sports_mode["config_schema"]
