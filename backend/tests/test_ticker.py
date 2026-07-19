"""Data ticker: Yahoo quote parsing, stock row layout, pagination, template
path resolution, error fallbacks — all with mocked fetches (no network)."""
import pytest

from charmap import CHARS
from services import ticker
from services.ticker import (GREEN_TILE, RED_TILE, get_data_matrix,
                             get_stocks_matrix, parse_quote, quote_row,
                             render_template, resolve_path)

ROWS, COLS = 6, 22


def _row_text(row):
    return "".join(CHARS[c] if 0 < c < 71 else " " for c in row).strip()


def _yahoo(price, prev):
    return {"chart": {"result": [{"meta": {
        "regularMarketPrice": price, "chartPreviousClose": prev}}]}}


@pytest.fixture(autouse=True)
def _clear_caches():
    ticker._quote_cache.clear()
    ticker._data_cache.clear()
    ticker._cursor.clear()
    yield
    ticker._quote_cache.clear()
    ticker._data_cache.clear()
    ticker._cursor.clear()


# ── Quote parsing ─────────────────────────────────────────────────────────────

def test_parse_quote_change_pct():
    q = parse_quote("aapl", _yahoo(220.0, 200.0))
    assert q["symbol"] == "AAPL"
    assert q["price"] == 220.0
    assert q["change_pct"] == pytest.approx(10.0)


def test_parse_quote_negative_change():
    q = parse_quote("TSLA", _yahoo(90.0, 100.0))
    assert q["change_pct"] == pytest.approx(-10.0)


def test_parse_quote_malformed():
    assert parse_quote("X", {"chart": {"result": []}}) is None
    assert parse_quote("X", {}) is None


# ── Row layout ────────────────────────────────────────────────────────────────

def test_quote_row_up_gets_green_accent():
    row = quote_row({"symbol": "AAPL", "price": 234.56, "change_pct": 1.23}, COLS)
    assert row[0] == GREEN_TILE
    assert len(row) == COLS
    assert _row_text(row).startswith("AAPL")
    assert _row_text(row).endswith("234.56 +1.2%")


def test_quote_row_down_gets_red_accent():
    row = quote_row({"symbol": "TSLA", "price": 90.0, "change_pct": -4.5}, COLS)
    assert row[0] == RED_TILE
    assert _row_text(row).endswith("90.00 -4.5%")


def test_quote_row_big_price_fits():
    row = quote_row({"symbol": "BTC-USD", "price": 117234.9, "change_pct": 2.1}, COLS)
    assert len(row) == COLS
    assert "117235" in _row_text(row)


# ── Stocks matrix ─────────────────────────────────────────────────────────────

async def test_stocks_matrix_renders_rows(monkeypatch):
    quotes = {"AAPL": _yahoo(220.0, 200.0), "TSLA": _yahoo(90.0, 100.0)}

    async def fake_fetch(sym):
        return quotes[sym]

    monkeypatch.setattr(ticker, "_fetch_quote", fake_fetch)
    m = await get_stocks_matrix(ROWS, COLS, symbols="AAPL, TSLA")
    lines = [_row_text(r) for r in m if _row_text(r)]
    assert len(lines) == 2
    assert lines[0].startswith("AAPL")
    assert lines[1].startswith("TSLA")


async def test_stocks_matrix_paginates(monkeypatch):
    async def fake_fetch(sym):
        return _yahoo(100.0, 100.0)

    monkeypatch.setattr(ticker, "_fetch_quote", fake_fetch)
    syms = ",".join(f"S{i}" for i in range(8))  # 8 symbols, 6 rows
    m1 = await get_stocks_matrix(ROWS, COLS, symbols=syms, screen_id="pg")
    m2 = await get_stocks_matrix(ROWS, COLS, symbols=syms, screen_id="pg")
    assert _row_text(m1[0]) != _row_text(m2[0])  # cursor advanced


async def test_stocks_matrix_no_symbols():
    m = await get_stocks_matrix(ROWS, COLS, symbols="")
    assert any("SYMBOLS" in _row_text(r) for r in m)


async def test_stocks_matrix_all_fetches_fail(monkeypatch):
    async def boom(sym):
        raise RuntimeError("offline")

    monkeypatch.setattr(ticker, "_fetch_quote", boom)
    m = await get_stocks_matrix(ROWS, COLS, symbols="AAPL")
    assert any("UNAVAILABLE" in _row_text(r) for r in m)


async def test_stocks_stale_cache_survives_outage(monkeypatch):
    async def ok(sym):
        return _yahoo(220.0, 200.0)

    monkeypatch.setattr(ticker, "_fetch_quote", ok)
    await get_stocks_matrix(ROWS, COLS, symbols="AAPL")
    ticker._quote_cache["AAPL"] = (0.0, ticker._quote_cache["AAPL"][1])  # expire

    async def boom(sym):
        raise RuntimeError("offline")

    monkeypatch.setattr(ticker, "_fetch_quote", boom)
    m = await get_stocks_matrix(ROWS, COLS, symbols="AAPL")
    assert any(_row_text(r).startswith("AAPL") for r in m)


# ── Template resolution ───────────────────────────────────────────────────────

def test_resolve_path_dicts_lists():
    data = {"a": {"b": [{"c": 42}]}}
    assert resolve_path(data, "a.b.0.c") == 42
    assert resolve_path(data, "a.b.1.c") is None
    assert resolve_path(data, "a.x") is None
    assert resolve_path(data, "a.b.zz") is None


def test_render_template():
    data = {"stats": {"followers": 1234, "rating": 4.5}}
    assert render_template("SUBS {stats.followers}", data) == "SUBS 1234"
    assert render_template("{stats.rating} STARS", data) == "4.5 STARS"
    assert render_template("{stats.missing}", data) == "?"
    assert render_template("NO PLACEHOLDERS", data) == "NO PLACEHOLDERS"


# ── Data matrix ───────────────────────────────────────────────────────────────

async def test_data_matrix_renders(monkeypatch):
    async def fake_json(url):
        return {"temp": {"f": 72.5}}

    monkeypatch.setattr(ticker, "_fetch_json", fake_json)
    m = await get_data_matrix(ROWS, COLS, url="http://x/api",
                              template="GARAGE {temp.f} DEG")
    assert any("GARAGE 72.5 DEG" in _row_text(r) for r in m)


async def test_data_matrix_unconfigured():
    m = await get_data_matrix(ROWS, COLS, url="", template="")
    assert any("SET A URL" in _row_text(r) for r in m)


async def test_data_matrix_error_fallback(monkeypatch):
    async def boom(url):
        raise RuntimeError("down")

    monkeypatch.setattr(ticker, "_fetch_json", boom)
    m = await get_data_matrix(ROWS, COLS, url="http://x/api", template="{v}")
    assert any("DATA UNAVAILABLE" in _row_text(r) for r in m)


async def test_data_matrix_stale_cache(monkeypatch):
    async def ok(url):
        return {"v": 7}

    monkeypatch.setattr(ticker, "_fetch_json", ok)
    await get_data_matrix(ROWS, COLS, url="http://x/api", template="COUNT {v}")
    ticker._data_cache["http://x/api"] = (0.0, ticker._data_cache["http://x/api"][1])

    async def boom(url):
        raise RuntimeError("down")

    monkeypatch.setattr(ticker, "_fetch_json", boom)
    m = await get_data_matrix(ROWS, COLS, url="http://x/api", template="COUNT {v}")
    assert any("COUNT 7" in _row_text(r) for r in m)


# ── Registration ──────────────────────────────────────────────────────────────

async def test_modes_registered(client):
    modes = (await client.get("/api/modes/available")).json()
    by_id = {m["id"]: m for m in modes}
    assert "symbols" in by_id["stocks"]["config_schema"]
    assert "url" in by_id["data"]["config_schema"]
    assert "template" in by_id["data"]["config_schema"]
