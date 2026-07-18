"""Live sports scores via ESPN's public scoreboard API (no key required).

Renders games with the scoreboard layout — accent tiles, right-aligned
scores — plus a status line (quarter/period clock, FINAL, or start time).
Because the frontend only flips changed tiles, a score change mid-game flips
just the digits.
"""
import time

import httpx

from charmap import text_to_matrix, text_to_row
from services.scoreboard import get_scoreboard_matrix

LEAGUES = {
    "nfl":   ("football/nfl",                       "NFL"),
    "ncaaf": ("football/college-football",          "College Football"),
    "nba":   ("basketball/nba",                     "NBA"),
    "ncaam": ("basketball/mens-college-basketball", "College Basketball"),
    "mlb":   ("baseball/mlb",                       "MLB"),
    "nhl":   ("hockey/nhl",                         "NHL"),
    "mls":   ("soccer/usa.1",                       "MLS"),
    "epl":   ("soccer/eng.1",                       "Premier League"),
}

CACHE_SECONDS = 60

_cache: dict[str, tuple[float, list[dict]]] = {}
_cursor: dict[str, int] = {}  # per screen+league game rotation


async def _fetch_raw(league_path: str) -> dict:
    url = f"https://site.api.espn.com/apis/site/v2/sports/{league_path}/scoreboard"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def _parse_games(data: dict) -> list[dict]:
    games = []
    for event in data.get("events", []):
        try:
            comp = event["competitions"][0]
            home = away = None
            for c in comp.get("competitors", []):
                team = c.get("team") or {}
                entry = {
                    "name": team.get("abbreviation") or team.get("shortDisplayName", "?"),
                    "score": int(c.get("score") or 0),
                }
                if c.get("homeAway") == "home":
                    home = entry
                else:
                    away = entry
            if not home or not away:
                continue
            status = (event.get("status") or {}).get("type") or {}
            games.append({
                "home_name": home["name"], "home_score": home["score"],
                "away_name": away["name"], "away_score": away["score"],
                "state": status.get("state", ""),         # pre | in | post
                "detail": status.get("shortDetail", ""),  # "7:32 - 3rd", "Final", "Sat 7:00 PM"
            })
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    # Live games first, then upcoming, then finished
    order = {"in": 0, "pre": 1, "post": 2}
    games.sort(key=lambda g: order.get(g["state"], 3))
    return games


async def get_games(league: str) -> list[dict]:
    path = LEAGUES.get(league, LEAGUES["nfl"])[0]
    now = time.time()
    cached = _cache.get(path)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        games = _parse_games(await _fetch_raw(path))
        _cache[path] = (now, games)
        return games
    except Exception:
        # Serve stale data through an API blip rather than blanking the board
        return cached[1] if cached else []


def render_game(rows: int, cols: int, game: dict) -> list[list[int]]:
    m = get_scoreboard_matrix(rows, cols, game["home_name"], game["away_name"],
                              game["home_score"], game["away_score"])
    if rows >= 5:
        status = (game.get("detail") or "").upper().replace(" - ", " ")[:cols]
        pad = max(0, (cols - len(status)) // 2)
        m[rows - 1] = text_to_row(" " * pad + status, cols)
    return m


async def get_sports_matrix(rows: int, cols: int, league: str = "nfl",
                            team: str = "", screen_id: str = "main") -> list[list[int]]:
    games = await get_games(league)

    if team.strip():
        t = team.strip().upper()
        matched = [g for g in games
                   if t in g["home_name"].upper() or t in g["away_name"].upper()]
        if matched:
            games = matched

    if not games:
        label = LEAGUES.get(league, LEAGUES["nfl"])[1]
        return text_to_matrix(f"NO {label} GAMES TODAY", rows, cols)

    if len(games) == 1:
        # Single game (or filtered team): stay on it so score digits flip live
        return render_game(rows, cols, games[0])

    key = f"{screen_id}:{league}"
    idx = _cursor.get(key, 0) % len(games)
    _cursor[key] = idx + 1
    return render_game(rows, cols, games[idx])
