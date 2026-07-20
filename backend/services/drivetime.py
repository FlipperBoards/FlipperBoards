"""Driving times via the Google Routes API (Route Matrix, live traffic).

    ■ HOME··········23 MIN
    ■ AIRPORT·······41 MIN
    ■ THE SHOP·······8 MIN

Accent tile shows traffic: green = clear, yellow = slow, red = heavy
(live duration vs free-flow duration).

Destinations come from the mode config (up to 6 lines of "Name | address"),
or over MQTT (`{base}/<screen>/drivetime/set`) with either destinations to
compute or ready-made minutes (e.g. from Home Assistant's Waze integration).

Cost note: fetches happen ONLY while a screen is actually rendering this
mode — every render goes through a shared cache (default 5 minutes), so a
board showing drive times all day makes 12 requests/hour regardless of how
many screens display it. Google bills the Route Matrix per element
(origins × destinations), so fewer destinations = cheaper.
"""
import json
import time

import httpx

from charmap import blank_matrix, char_to_code, text_to_matrix, text_to_row

MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
CACHE_SECONDS = 300
MAX_DESTINATIONS = 6

DOT = 67          # dot-leader tile
GREEN, YELLOW, RED = 74, 73, 71
TRAFFIC_TILES = {"light": GREEN, "moderate": YELLOW, "heavy": RED}

_cache: dict[str, tuple[float, list[dict]]] = {}
_override: dict[str, list[dict]] = {}   # screen_id → MQTT-provided items
_cursor: dict[str, int] = {}            # screen_id → pagination


def parse_destinations(text: str) -> list[dict]:
    """Config format: one per line, `Name | address` (or just an address)."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            name, dest = line.split("|", 1)
        else:
            name = dest = line
        if name.strip() and dest.strip():
            out.append({"name": name.strip(), "dest": dest.strip()})
    return out[:MAX_DESTINATIONS]


def set_override(screen_id: str, items) -> bool:
    """MQTT override. Items: [{"name", "dest"}] to compute, or
    [{"name", "minutes", "traffic"?}] ready-made. Empty/None clears.
    Returns True if the payload was usable."""
    if not items:
        _override.pop(screen_id, None)
        return True
    if not isinstance(items, list):
        return False
    cleaned = []
    for it in items[:MAX_DESTINATIONS]:
        if not isinstance(it, dict) or not it.get("name"):
            continue
        if "minutes" in it:
            try:
                cleaned.append({"name": str(it["name"]).strip(),
                                "minutes": max(0, int(it["minutes"])),
                                "traffic": str(it.get("traffic", "")).lower()})
            except (TypeError, ValueError):
                continue
        elif it.get("dest"):
            cleaned.append({"name": str(it["name"]).strip(),
                            "dest": str(it["dest"]).strip()})
    if not cleaned:
        return False
    _override[screen_id] = cleaned
    return True


def get_override(screen_id: str):
    return _override.get(screen_id)


async def _fetch_matrix(api_key: str, origin: str, dests: list[str]) -> list[dict]:
    body = {
        "origins": [{"waypoint": {"address": origin}}],
        "destinations": [{"waypoint": {"address": d}} for d in dests],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask":
            "originIndex,destinationIndex,duration,staticDuration,condition",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(MATRIX_URL, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _seconds(v) -> int:
    # Durations arrive as "1380s"
    try:
        return int(str(v).rstrip("s"))
    except (TypeError, ValueError):
        return 0


def parse_matrix(elements: list[dict], names: list[str]) -> list[dict]:
    """Route Matrix response → [{name, minutes, tile}] in destination order."""
    by_index: dict[int, dict] = {}
    for el in elements or []:
        if not isinstance(el, dict):
            continue
        if el.get("condition") and el["condition"] != "ROUTE_EXISTS":
            continue
        idx = el.get("destinationIndex", 0)
        secs = _seconds(el.get("duration"))
        if secs <= 0:
            continue
        static = _seconds(el.get("staticDuration")) or secs
        ratio = secs / static if static else 1.0
        tile = RED if ratio >= 1.5 else YELLOW if ratio >= 1.15 else GREEN
        by_index[idx] = {"minutes": max(1, round(secs / 60)), "tile": tile}
    out = []
    for i, name in enumerate(names):
        el = by_index.get(i)
        if el:
            out.append({"name": name, **el})
        else:
            out.append({"name": name, "minutes": None, "tile": 0})
    return out


async def get_times(api_key: str, origin: str, dests: list[dict]) -> list[dict]:
    """Cached (CACHE_SECONDS) + stale-on-error live times for computed items."""
    key = json.dumps([origin] + [d["dest"] for d in dests])
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        elements = await _fetch_matrix(api_key, origin, [d["dest"] for d in dests])
        result = parse_matrix(elements, [d["name"] for d in dests])
        _cache[key] = (now, result)
        return result
    except Exception:
        # Serve stale data through an API blip rather than blanking the board
        return cached[1] if cached else [
            {"name": d["name"], "minutes": None, "tile": 0} for d in dests]


def _fmt_minutes(minutes) -> str:
    if minutes is None:
        return "--"
    if minutes >= 100:
        h, m = divmod(minutes, 60)
        return f"{h}H{m:02d}"
    return f"{minutes} MIN"


def entry_row(entry: dict, cols: int) -> list[int]:
    """`■ NAME········23 MIN` — accent tile, dot leaders, right-aligned time."""
    right = _fmt_minutes(entry.get("minutes"))
    tile = entry.get("tile") or 0
    row = [tile, 0] if tile else [0, 0]
    name = entry["name"].upper()[: max(1, cols - 2 - len(right) - 1)]
    for ch in name:
        row.append(char_to_code(ch))
    while len(row) < cols - len(right):
        row.append(DOT)
    for ch in right:
        row.append(char_to_code(ch))
    return row[:cols]


async def get_drivetime_matrix(rows: int, cols: int, api_key: str = "",
                               origin: str = "", destinations: str = "",
                               screen_id: str = "main") -> list[list[int]]:
    items = _override.get(screen_id) or parse_destinations(destinations)
    if not items:
        return _message(rows, cols, "ADD DESTINATIONS IN MODE SETTINGS")

    to_compute = [i for i in items if "minutes" not in i]

    computed: dict[str, dict] = {}
    if to_compute:
        if not api_key.strip():
            return _message(rows, cols, "SET GOOGLE MAPS API KEY IN SETTINGS")
        if not origin.strip():
            return _message(rows, cols, "SET ORIGIN IN MODE SETTINGS")
        for e in await get_times(api_key.strip(), origin.strip(), to_compute):
            computed[e["name"]] = e

    entries = []
    for it in items:
        if "minutes" in it:
            entries.append({"name": it["name"], "minutes": it["minutes"],
                            "tile": TRAFFIC_TILES.get(it.get("traffic", ""), GREEN)})
        else:
            entries.append(computed.get(it["name"],
                           {"name": it["name"], "minutes": None, "tile": 0}))

    # Pagination if more entries than rows (config caps at 6, but 4-row
    # boards exist); title shown when there's a spare row
    show_title = len(entries) < rows
    per_page = rows - (1 if show_title else 0)
    if len(entries) > per_page:
        pos = _cursor.get(screen_id, 0) % len(entries)
        _cursor[screen_id] = (pos + per_page) % len(entries)
        entries = [entries[(pos + i) % len(entries)] for i in range(per_page)]

    lines = []
    if show_title:
        title = "DRIVE TIMES"
        pad = max(0, (cols - len(title)) // 2)
        lines.append(text_to_row(" " * pad + title, cols))
    for e in entries:
        lines.append(entry_row(e, cols))

    matrix = blank_matrix(rows, cols)
    top = max(0, (rows - len(lines)) // 2)
    for i, line in enumerate(lines[:rows]):
        matrix[top + i] = line
    return matrix


def _message(rows: int, cols: int, msg: str) -> list[list[int]]:
    return text_to_matrix(msg, rows, cols)   # word-wraps and centers
