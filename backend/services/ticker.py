"""Data ticker modes.

Stocks — Yahoo Finance chart API (no key required): price + % change vs
previous close, one row per symbol with a green/red accent tile per
direction. Diff-flipping means a price tick only flips its digits.

Generic data — poll any JSON URL and render a template with
{dot.path.0.notation} placeholders. Covers follower counts, sensors,
home-automation values, anything with a JSON endpoint. The URL is
operator-configured behind auth and fetched by the server — deploy on a
trusted network (see README) since the server will fetch whatever URL an
authenticated operator enters.
"""
import time

import httpx

from charmap import char_to_code, text_to_matrix

CACHE_SECONDS = 120

GREEN_TILE = 74
RED_TILE = 71
WHITE_TILE = 77

_quote_cache: dict[str, tuple[float, dict]] = {}
_data_cache: dict[str, tuple[float, dict]] = {}
_cursor: dict[str, int] = {}  # per screen — page rotation when symbols > rows


# ── Stocks ────────────────────────────────────────────────────────────────────

async def _fetch_quote(symbol: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    async with httpx.AsyncClient(timeout=10,
                                 headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get(url, params={"interval": "1d", "range": "1d"})
        resp.raise_for_status()
        return resp.json()


def parse_quote(symbol: str, data: dict) -> dict | None:
    try:
        meta = data["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        prev = float(meta.get("chartPreviousClose")
                     or meta.get("previousClose") or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    change_pct = ((price - prev) / prev * 100) if prev else 0.0
    return {"symbol": symbol.upper(), "price": price, "change_pct": change_pct}


async def get_quote(symbol: str) -> dict | None:
    symbol = symbol.strip().upper()
    if not symbol:
        return None
    now = time.time()
    cached = _quote_cache.get(symbol)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        quote = parse_quote(symbol, await _fetch_quote(symbol))
        if quote:
            _quote_cache[symbol] = (now, quote)
            return quote
    except Exception:
        pass
    # Serve stale data through an API blip rather than blanking the board
    return cached[1] if cached else None


def _fmt_price(price: float) -> str:
    if price >= 100000:
        return f"{price:,.0f}".replace(",", "")
    if price >= 1000:
        return f"{price:.0f}"
    return f"{price:.2f}"


def quote_row(quote: dict, cols: int) -> list[int]:
    """`■ AAPL      234.56 +1.2%` — accent tile colored by direction,
    price+change right-aligned, symbol left."""
    up = quote["change_pct"] >= 0
    change = f"{'+' if up else ''}{quote['change_pct']:.1f}%"
    price = _fmt_price(quote["price"])
    sym = quote["symbol"][: max(1, cols - len(price) - len(change) - 4)]
    right = f"{price} {change}"
    gap = cols - 2 - len(sym) - len(right)
    text = sym + " " * max(1, gap) + right
    row = [GREEN_TILE if up else RED_TILE, 0]
    for ch in text:
        row.append(char_to_code(ch))
        if len(row) >= cols:
            break
    while len(row) < cols:
        row.append(0)
    return row[:cols]


async def get_stocks_matrix(rows: int, cols: int, symbols: str = "",
                            screen_id: str = "main") -> list[list[int]]:
    syms = [s.strip().upper() for s in (symbols or "").split(",") if s.strip()]
    if not syms:
        return text_to_matrix("ADD STOCK SYMBOLS IN MODE SETTINGS", rows, cols)

    quotes = [q for q in [await get_quote(s) for s in syms] if q]
    if not quotes:
        return text_to_matrix("QUOTES UNAVAILABLE", rows, cols)

    if len(quotes) <= rows:
        page = quotes
    else:
        key = f"{screen_id}:stocks"
        start = _cursor.get(key, 0) % len(quotes)
        _cursor[key] = (start + rows) % len(quotes)
        page = [quotes[(start + i) % len(quotes)] for i in range(rows)]

    matrix = []
    top = max(0, (rows - len(page)) // 2)
    matrix.extend([[0] * cols for _ in range(top)])
    for q in page:
        matrix.append(quote_row(q, cols))
    while len(matrix) < rows:
        matrix.append([0] * cols)
    return matrix


# ── Generic JSON data ─────────────────────────────────────────────────────────

def resolve_path(data, path: str):
    """Walk `a.b.0.c` through nested dicts/lists. None when any hop fails."""
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def render_template(template: str, data) -> str:
    """Replace {dot.path} placeholders with values from the JSON payload.
    Floats are trimmed to 2 decimals; missing paths render as `?`."""
    import re

    def _sub(m):
        val = resolve_path(data, m.group(1))
        if val is None:
            return "?"
        if isinstance(val, float):
            return f"{val:.2f}".rstrip("0").rstrip(".")
        return str(val)

    return re.sub(r"\{([A-Za-z0-9_.\-]+)\}", _sub, template)


async def _fetch_json(url: str) -> dict:
    async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                 headers={"User-Agent": "FlipperBoards"}) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def get_data_matrix(rows: int, cols: int, url: str = "",
                          template: str = "", label: str = "") -> list[list[int]]:
    url = (url or "").strip()
    template = (template or "").strip()
    if not url or not template:
        return text_to_matrix("SET A URL AND TEMPLATE IN MODE SETTINGS", rows, cols)

    now = time.time()
    cached = _data_cache.get(url)
    if cached and now - cached[0] < CACHE_SECONDS:
        data = cached[1]
    else:
        try:
            data = await _fetch_json(url)
            _data_cache[url] = (now, data)
        except Exception:
            if cached:
                data = cached[1]  # stale beats blank
            else:
                return text_to_matrix(f"{label} DATA UNAVAILABLE".strip(), rows, cols)

    text = render_template(template, data)
    if label.strip():
        text = f"{label.strip()} {text}"
    return text_to_matrix(text, rows, cols)
