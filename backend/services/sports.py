"""Live sports scores via ESPN's public scoreboard API (no key required).

Fetches one or more leagues' current-day slates, filters by game status and
team, merges everything into a single rotation, and renders each game with the
scoreboard layout — accent tiles, right-aligned scores, full team names where
they fit, and a status line (quarter/period clock, FINAL, or start time),
optionally tagged with the league. Because the frontend only flips changed
tiles, a score change mid-game flips just the digits.
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

# Compact tags for the status line when several leagues are merged
LEAGUE_TAGS = {
    "nfl": "NFL", "ncaaf": "NCAAF", "nba": "NBA", "ncaam": "NCAAM",
    "mlb": "MLB", "nhl": "NHL", "mls": "MLS", "epl": "EPL",
}

STATUS_STATES = {"live": "in", "upcoming": "pre", "final": "post"}
STATUS_LABELS = {"live": "LIVE", "upcoming": "UPCOMING", "final": "FINAL"}

CACHE_SECONDS = 60

_cache: dict[str, tuple[float, list[dict]]] = {}
_cursor: dict[str, int] = {}  # per screen+filters game rotation


async def _fetch_raw(league_path: str) -> dict:
    url = f"https://site.api.espn.com/apis/site/v2/sports/{league_path}/scoreboard"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def _team_names(team: dict) -> dict:
    """Every name variant ESPN offers, longest → shortest, for best-fit."""
    abbr = team.get("abbreviation") or team.get("shortDisplayName") or "?"
    short = team.get("shortDisplayName") or team.get("name") or abbr
    full = team.get("displayName") or team.get("name") or short
    return {"full": full, "short": short, "abbr": abbr}


def _parse_games(data: dict, league: str) -> list[dict]:
    games = []
    for event in data.get("events", []):
        try:
            comp = event["competitions"][0]
            home = away = None
            for c in comp.get("competitors", []):
                entry = {
                    "names": _team_names(c.get("team") or {}),
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
                "league": league,
                "home_names": home["names"], "home_score": home["score"],
                "away_names": away["names"], "away_score": away["score"],
                "state": status.get("state", ""),         # pre | in | post
                "detail": status.get("shortDetail", ""),  # "7:32 - 3rd", "Final", "Sat 7:00 PM"
            })
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return games


_ORDER = {"in": 0, "pre": 1, "post": 2}


async def get_games(league: str) -> list[dict]:
    """One league's games, live-first. Cached, stale-on-error."""
    path = LEAGUES.get(league, LEAGUES["nfl"])[0]
    now = time.time()
    cached = _cache.get(path)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        games = _parse_games(await _fetch_raw(path), league)
        games.sort(key=lambda g: _ORDER.get(g["state"], 3))
        _cache[path] = (now, games)
        return games
    except Exception:
        # Serve stale data through an API blip rather than blanking the board
        return cached[1] if cached else []


async def get_all_games(leagues: list[str]) -> list[dict]:
    """Merge several leagues' slates into one live-first rotation."""
    merged = []
    for lg in leagues:
        merged.extend(await get_games(lg))
    merged.sort(key=lambda g: _ORDER.get(g["state"], 3))
    return merged


def _fit_name(names: dict, max_len: int) -> str:
    """Longest name variant that fits max_len, falling back to the abbreviation."""
    if max_len <= 0:
        return names["abbr"]
    for key in ("full", "short", "abbr"):
        candidate = (names[key] or "").strip()
        if candidate and len(candidate) <= max_len:
            return candidate
    return names["abbr"]


def _name_width(cols: int, score: int) -> int:
    # Mirrors scoreboard._team_row: accent + gap before name, gap before score
    return cols - len(str(score)) - 3


def render_game(rows: int, cols: int, game: dict, tag: str = "") -> list[list[int]]:
    home = _fit_name(game["home_names"], _name_width(cols, game["home_score"]))
    away = _fit_name(game["away_names"], _name_width(cols, game["away_score"]))
    m = get_scoreboard_matrix(rows, cols, home, away,
                              game["home_score"], game["away_score"])
    if rows >= 5:
        status = (game.get("detail") or "").upper().replace(" - ", " ")
        if tag:
            status = f"{tag}  {status}".strip()
        status = status[:cols]
        pad = max(0, (cols - len(status)) // 2)
        m[rows - 1] = text_to_row(" " * pad + status, cols)
    return m


def _parse_leagues(leagues, legacy_league: str) -> list[str]:
    """Config → ordered list of valid league keys. Accepts a list, a comma
    string, or the legacy single `league` field; defaults to NFL."""
    raw = leagues if leagues else legacy_league
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.split(",")]
    elif isinstance(raw, (list, tuple)):
        parts = [str(p).strip().lower() for p in raw]
    else:
        parts = []
    valid = [p for p in parts if p in LEAGUES]
    return valid or ["nfl"]


def _parse_teams(teams, legacy_team: str) -> list[str]:
    raw = teams if teams else legacy_team
    if isinstance(raw, (list, tuple)):
        raw = ",".join(str(t) for t in raw)
    return [t.strip().upper() for t in str(raw or "").split(",") if t.strip()]


def _game_matches_team(game: dict, tokens: list[str]) -> bool:
    haystack = " ".join(
        v.upper()
        for names in (game["home_names"], game["away_names"])
        for v in names.values()
    )
    return any(tok in haystack for tok in tokens)


async def get_sports_matrix(rows: int, cols: int, league: str = "nfl",
                            team: str = "", screen_id: str = "main",
                            leagues=None, status: str = "all",
                            teams=None) -> list[list[int]]:
    league_keys = _parse_leagues(leagues, league)
    games = await get_all_games(league_keys)

    status = (status or "all").lower()
    if status in STATUS_STATES:
        games = [g for g in games if g["state"] == STATUS_STATES[status]]

    tokens = _parse_teams(teams, team)
    if tokens:
        matched = [g for g in games if _game_matches_team(g, tokens)]
        games = matched  # explicit filter — empty means "none match", show message

    if not games:
        return text_to_matrix(_empty_message(league_keys, status, tokens), rows, cols)

    # Tag rows with the league only when several leagues are in play
    tag_for = (lambda g: LEAGUE_TAGS.get(g["league"], "")) if len(league_keys) > 1 else (lambda g: "")

    if len(games) == 1:
        # Single game (or filtered to one): stay on it so score digits flip live
        return render_game(rows, cols, games[0], tag_for(games[0]))

    key = f"{screen_id}:{','.join(league_keys)}:{status}:{','.join(tokens)}"
    idx = _cursor.get(key, 0) % len(games)
    _cursor[key] = idx + 1
    game = games[idx]
    return render_game(rows, cols, game, tag_for(game))


def _empty_message(league_keys: list[str], status: str, tokens: list[str]) -> str:
    if tokens:
        return f"NO GAMES FOR {', '.join(tokens)}"
    scope = LEAGUES[league_keys[0]][1] if len(league_keys) == 1 else "SELECTED"
    if status in STATUS_LABELS:
        return f"NO {STATUS_LABELS[status]} {scope} GAMES"
    return f"NO {scope} GAMES TODAY"
