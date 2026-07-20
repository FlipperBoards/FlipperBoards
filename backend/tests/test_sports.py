"""Sports mode: ESPN payload parsing, rendering, multi-league merge, status
and team filtering, full-name fitting, and resilience — mocked fetch, no
network."""
import pytest

from charmap import CHARS
from services import sports


def _team(abbr, short, full):
    return {"abbreviation": abbr, "shortDisplayName": short, "displayName": full}


def _event(home, away, hs, as_, state="in", detail="7:32 - 3rd"):
    return {
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": str(hs), "team": home},
                {"homeAway": "away", "score": str(as_), "team": away},
            ],
        }],
        "status": {"type": {"state": state, "shortDetail": detail}},
    }


KC = _team("KC", "Chiefs", "Kansas City Chiefs")
BUF = _team("BUF", "Bills", "Buffalo Bills")
DAL = _team("DAL", "Cowboys", "Dallas Cowboys")
PHI = _team("PHI", "Eagles", "Philadelphia Eagles")
SF = _team("SF", "49ers", "San Francisco 49ers")
SEA = _team("SEA", "Seahawks", "Seattle Seahawks")

NFL_FIXTURE = {"events": [
    _event(KC, BUF, 21, 17, "in", "7:32 - 3rd"),
    _event(DAL, PHI, 0, 0, "pre", "Sun 7:20 PM"),
    _event(SF, SEA, 27, 24, "post", "Final"),
]}

LAL = _team("LAL", "Lakers", "Los Angeles Lakers")
BOS = _team("BOS", "Celtics", "Boston Celtics")
NBA_FIXTURE = {"events": [
    _event(LAL, BOS, 88, 90, "in", "4:10 - 4th"),
]}


@pytest.fixture(autouse=True)
def _mock_espn(monkeypatch):
    async def fake_fetch(path):
        if "basketball/nba" in path:
            return NBA_FIXTURE
        return NFL_FIXTURE
    monkeypatch.setattr(sports, "_fetch_raw", fake_fetch)
    sports._cache.clear()
    sports._cursor.clear()
    yield


def _text(matrix):
    return ["".join(CHARS[c] if c < 71 else "#" for c in row).strip() for row in matrix]


# ── Parsing / ordering ────────────────────────────────────────────────────────

async def test_parse_orders_live_first():
    games = await sports.get_games("nfl")
    assert [g["state"] for g in games] == ["in", "pre", "post"]
    assert games[0]["home_names"]["abbr"] == "KC"
    assert games[0]["home_names"]["full"] == "Kansas City Chiefs"
    assert games[0]["home_score"] == 21


# ── Full team names, best-fit by width ────────────────────────────────────────

async def test_full_name_when_it_fits():
    # 22-wide board fits "BUFFALO BILLS" (13 <= 17 name width) but not
    # "KANSAS CITY CHIEFS" (18) — that one falls back to "CHIEFS"
    m = await sports.get_sports_matrix(6, 22, leagues=["nfl"], teams="Chiefs")
    rows = _text(m)
    assert any("BUFFALO BILLS" in r for r in rows)
    assert any("CHIEFS" in r for r in rows)
    assert not any("KANSAS CITY" in r for r in rows)


async def test_full_name_on_wide_board():
    # A wider board fits the whole "KANSAS CITY CHIEFS"
    m = await sports.get_sports_matrix(6, 30, leagues=["nfl"], teams="Chiefs")
    assert any("KANSAS CITY CHIEFS" in r for r in _text(m))


async def test_falls_back_to_short_name_on_narrow_board():
    # 12-wide can't fit the full name; "CHIEFS" should win over "KC"
    m = await sports.get_sports_matrix(6, 12, leagues=["nfl"], teams="Chiefs")
    rows = _text(m)
    assert any("CHIEFS" in r for r in rows)
    assert not any("KANSAS CITY" in r for r in rows)


# ── Status filter ─────────────────────────────────────────────────────────────

async def test_status_live_only():
    m = await sports.get_sports_matrix(6, 22, leagues=["nfl"], status="live")
    rows = _text(m)
    assert any("CHIEFS" in r for r in rows)  # the only live NFL game
    # not the upcoming or final games
    assert not any("COWBOYS" in r for r in rows)


async def test_status_upcoming_only():
    m = await sports.get_sports_matrix(6, 22, leagues=["nfl"], status="upcoming")
    assert any("COWBOYS" in r for r in _text(m))


async def test_status_live_plus_final():
    # Keeps live (Chiefs) and final (49ers), drops upcoming (Cowboys)
    seen = set()
    for _ in range(4):
        rows = " ".join(_text(await sports.get_sports_matrix(
            6, 22, leagues=["nfl"], status="live_final", screen_id="lf")))
        if "CHIEFS" in rows:
            seen.add("live")
        if "49ERS" in rows or "SAN FRANCISCO" in rows:
            seen.add("final")
        assert "COWBOYS" not in rows  # upcoming excluded
    assert seen == {"live", "final"}


async def test_status_none_matching_shows_message():
    # NBA fixture has only a live game — live_final on... upcoming yields nothing
    m = await sports.get_sports_matrix(6, 22, leagues=["nba"], status="upcoming")
    assert any("NO UPCOMING" in r for r in _text(m))


# ── Multi-league merge + league tag ───────────────────────────────────────────

async def test_multi_league_merges_and_tags():
    seen = set()
    for _ in range(4):
        m = await sports.get_sports_matrix(6, 22, leagues=["nfl", "nba"],
                                           status="live", screen_id="multi")
        rows = _text(m)
        joined = " ".join(rows)
        if "LAKERS" in joined:
            seen.add("nba")
            assert any("NBA" in r for r in rows)  # tagged status line
        if "CHIEFS" in joined:
            seen.add("nfl")
            assert any("NFL" in r for r in rows)
    assert seen == {"nfl", "nba"}  # both leagues appeared in the rotation


async def test_single_league_has_no_tag():
    m = await sports.get_sports_matrix(6, 22, leagues=["nba"], status="live")
    rows = _text(m)
    # status line is the game clock only, no "NBA" prefix
    assert any("4:10 4TH" in r for r in rows)
    assert not any(r.startswith("NBA") for r in rows)


# ── Team filter ───────────────────────────────────────────────────────────────

async def test_multi_team_filter_across_leagues():
    # Chiefs (NFL) + Lakers (NBA), both live — filter keeps only those
    got = set()
    for _ in range(4):
        m = await sports.get_sports_matrix(6, 22, leagues=["nfl", "nba"],
                                           teams="Chiefs, Lakers", screen_id="mt")
        joined = " ".join(_text(m))
        if "CHIEFS" in joined:
            got.add("kc")
        if "LAKERS" in joined:
            got.add("lal")
        assert "COWBOYS" not in joined  # not in the filter
    assert got == {"kc", "lal"}


async def test_legacy_single_league_and_team():
    m = await sports.get_sports_matrix(6, 22, league="nfl", team="KC")
    assert any("CHIEFS" in r for r in _text(m))


# ── Live digit isolation ──────────────────────────────────────────────────────

async def test_score_change_flips_one_digit():
    before = await sports.get_sports_matrix(6, 22, leagues=["nfl"], teams="Chiefs")
    NFL_FIXTURE["events"][0]["competitions"][0]["competitors"][0]["score"] = "24"
    sports._cache.clear()
    after = await sports.get_sports_matrix(6, 22, leagues=["nfl"], teams="Chiefs")
    diff = [(r, c) for r in range(6) for c in range(22) if before[r][c] != after[r][c]]
    assert diff == [(1, 21)]  # 21 -> 24: only the ones digit changes
    NFL_FIXTURE["events"][0]["competitions"][0]["competitors"][0]["score"] = "21"


# ── Resilience ────────────────────────────────────────────────────────────────

async def test_no_games(monkeypatch):
    async def empty(path):
        return {"events": []}
    monkeypatch.setattr(sports, "_fetch_raw", empty)
    sports._cache.clear()
    m = await sports.get_sports_matrix(6, 22, leagues=["nba"])
    assert any("NO NBA GAMES TODAY" in r for r in _text(m))


async def test_api_failure_serves_stale_then_empty(monkeypatch):
    await sports.get_games("nfl")  # warm cache

    async def boom(path):
        raise RuntimeError("ESPN down")
    monkeypatch.setattr(sports, "_fetch_raw", boom)
    sports._cache["football/nfl"] = (0, sports._cache["football/nfl"][1])  # expire
    games = await sports.get_games("nfl")
    assert games and games[0]["home_names"]["abbr"] == "KC"  # stale beats blank

    sports._cache.clear()
    assert await sports.get_games("nfl") == []


async def test_mode_registered(client):
    modes = (await client.get("/api/modes/available")).json()
    sports_mode = next((m for m in modes if m["id"] == "sports"), None)
    assert sports_mode is not None
    assert "leagues" in sports_mode["config_schema"]
    assert sports_mode["config_schema"]["leagues"]["type"] == "multiselect"
    assert "status" in sports_mode["config_schema"]
