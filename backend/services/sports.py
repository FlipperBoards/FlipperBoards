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

from charmap import blank_matrix, char_to_code, text_to_matrix, text_to_row
from services.scoreboard import get_scoreboard_matrix

# Win/loss accent tiles for the list layout (charmap color codes)
WIN_TILE = 74    # green
LOSS_TILE = 71   # red
EVEN_TILE = 77   # white — tie, or a game not yet started

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

# Each Show option maps to the ESPN states it keeps ("all" keeps everything)
STATUS_STATES = {
    "live": ("in",),
    "live_final": ("in", "post"),
    "upcoming": ("pre",),
}
STATUS_LABELS = {"live": "LIVE", "live_final": "LIVE OR FINAL", "upcoming": "UPCOMING"}

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


def _game_tiles(away_score: int, home_score: int, state: str) -> tuple[int, int]:
    """(away_tile, home_tile) accent codes. Leader green, trailing red; a tie or
    a game that hasn't started gets white on both sides."""
    if state == "pre" or away_score == home_score:
        return EVEN_TILE, EVEN_TILE
    if away_score > home_score:
        return WIN_TILE, LOSS_TILE
    return LOSS_TILE, WIN_TILE


def _list_row(cols: int, game: dict) -> list[int]:
    """One game on a single row: [tile] AWAY score … score HOME [tile].

    Win/loss tiles sit on the far edges, each team's score hugs its name toward
    the center, so a score change flips just its own digit tiles.
    """
    row = [0] * cols
    away_score = str(game["away_score"])
    home_score = str(game["home_score"])

    if cols < 6:
        text = f"{away_score}-{home_score}"[:cols]
        for i, ch in enumerate(text):
            row[i] = char_to_code(ch)
        return row

    away_tile, home_tile = _game_tiles(game["away_score"], game["home_score"], game["state"])
    row[0] = away_tile
    row[cols - 1] = home_tile

    inner = cols - 2          # columns between the two accent tiles
    half = inner // 2

    # Left half: away name then its score, left-aligned from col 1
    away_name = _fit_name(game["away_names"], half - len(away_score) - 1)
    left = f"{away_name} {away_score}".strip().upper()[:half]
    for i, ch in enumerate(left):
        row[1 + i] = char_to_code(ch)

    # Right half: home score then its name, right-aligned up to the home tile
    home_name = _fit_name(game["home_names"], half - len(home_score) - 1)
    right = f"{home_score} {home_name}".strip().upper()[:half]
    start = (cols - 1) - len(right)
    for i, ch in enumerate(right):
        row[start + i] = char_to_code(ch)
    return row


def render_list(rows: int, cols: int, games: list[dict],
                per_page: int, cursor_key: str) -> list[list[int]]:
    """Several games at once, one per row. Shows up to `per_page` games (capped
    by the row count); when more games exist than fit, pages through them."""
    per_page = max(1, min(per_page, rows))
    matrix = blank_matrix(rows, cols)
    if len(games) <= per_page:
        page_games = games
    else:
        pages = (len(games) + per_page - 1) // per_page
        page = _cursor.get(cursor_key, 0) % pages
        _cursor[cursor_key] = page + 1
        start = page * per_page
        page_games = games[start:start + per_page]
    for i, game in enumerate(page_games):
        matrix[i] = _list_row(cols, game)
    return matrix


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
                            teams=None, layout: str = "single",
                            max_games: int = 5) -> list[list[int]]:
    league_keys = _parse_leagues(leagues, league)
    games = await get_all_games(league_keys)

    status = (status or "all").lower()
    if status in STATUS_STATES:
        keep = STATUS_STATES[status]
        games = [g for g in games if g["state"] in keep]

    tokens = _parse_teams(teams, team)
    if tokens:
        matched = [g for g in games if _game_matches_team(g, tokens)]
        games = matched  # explicit filter — empty means "none match", show message

    if not games:
        return text_to_matrix(_empty_message(league_keys, status, tokens), rows, cols)

    key = f"{screen_id}:{','.join(league_keys)}:{status}:{','.join(tokens)}"

    if (layout or "single").lower() == "list":
        # One game per row, several at once — no per-league tag (no room)
        return render_list(rows, cols, games, max_games, key + ":list")

    # Tag rows with the league only when several leagues are in play
    tag_for = (lambda g: LEAGUE_TAGS.get(g["league"], "")) if len(league_keys) > 1 else (lambda g: "")

    if len(games) == 1:
        # Single game (or filtered to one): stay on it so score digits flip live
        return render_game(rows, cols, games[0], tag_for(games[0]))

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
