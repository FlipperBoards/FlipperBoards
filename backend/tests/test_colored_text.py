"""Colored text markup: {red}...{/} parsing, color-map alignment with the
word-wrap, API round-trip, mode-gated clearing, and restart persistence."""
import httpx
from asgi_lifespan import LifespanManager

import main
from charmap import (MARKUP_COLORS, char_to_code, parse_colored_text,
                     text_to_matrix, text_to_matrix_colored)

ROWS, COLS = 6, 22
RED = MARKUP_COLORS["red"]
GREEN = MARKUP_COLORS["green"]


# ── parse_colored_text ────────────────────────────────────────────────────────

def test_parse_plain_text_no_colors():
    clean, colors = parse_colored_text("HELLO WORLD")
    assert clean == "HELLO WORLD"
    assert colors == [None] * len(clean)


def test_parse_single_span():
    clean, colors = parse_colored_text("{red}HOT{/} DEAL")
    assert clean == "HOT DEAL"
    assert colors == [RED, RED, RED, None, None, None, None, None]


def test_parse_multiple_spans_and_case():
    clean, colors = parse_colored_text("{RED}A{/}B{Green}C{/}")
    assert clean == "ABC"
    assert colors == [RED, None, GREEN]


def test_parse_unclosed_span_runs_to_end():
    clean, colors = parse_colored_text("X {blue}YZ")
    assert clean == "X YZ"
    assert colors[-2:] == [MARKUP_COLORS["blue"]] * 2


def test_parse_unknown_tag_left_verbatim():
    clean, colors = parse_colored_text("{pink}HI{/}")
    assert clean == "{pink}HI"
    assert all(c is None for c in colors)


# ── text_to_matrix_colored ────────────────────────────────────────────────────

def test_no_markup_returns_none_map_and_matches_plain():
    matrix, cmap = text_to_matrix_colored("BACK IN 5", ROWS, COLS)
    assert cmap is None
    assert matrix == text_to_matrix("BACK IN 5", ROWS, COLS)


def test_color_map_aligns_with_characters():
    matrix, cmap = text_to_matrix_colored("{red}HOT{/}", ROWS, COLS)
    assert cmap is not None
    for r in range(ROWS):
        for c in range(COLS):
            if cmap[r][c] == RED:
                assert matrix[r][c] != 0
    colored = [(r, c) for r in range(ROWS) for c in range(COLS)
               if cmap[r][c] == RED]
    assert len(colored) == 3
    codes = [matrix[r][c] for r, c in colored]
    assert codes == [char_to_code("H"), char_to_code("O"), char_to_code("T")]


def test_color_map_survives_word_wrap():
    # Two words that cannot share a 22-col line — color must follow its word
    text = "{green}AAAAAAAAAAAA{/} BBBBBBBBBBBB"
    matrix, cmap = text_to_matrix_colored(text, ROWS, COLS)
    green_rows = {r for r in range(ROWS) for c in range(COLS)
                  if cmap[r][c] == GREEN}
    assert len(green_rows) == 1
    (gr,) = green_rows
    a_code = char_to_code("A")
    for c in range(COLS):
        if matrix[gr][c] == a_code:
            assert cmap[gr][c] == GREEN


def test_layout_matches_plain_matrix():
    """Markup must not disturb wrapping/centering — same matrix as clean text."""
    marked = "{yellow}HAPPY{/} HOUR 5-7PM WELLS HALF OFF"
    plain = "HAPPY HOUR 5-7PM WELLS HALF OFF"
    m1, _ = text_to_matrix_colored(marked, ROWS, COLS)
    assert m1 == text_to_matrix(plain, ROWS, COLS)


# ── API round-trip ────────────────────────────────────────────────────────────

async def test_push_text_with_markup_exposes_colors(client):
    r = await client.post("/api/display/text?screen=main",
                          json={"text": "{red}HOT{/} DEAL"})
    assert r.status_code == 200
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "text_push"
    tc = s["text_colors"]
    assert tc is not None
    assert sum(1 for row in tc for c in row if c == RED) == 3


async def test_plain_push_has_no_colors(client):
    await client.post("/api/display/text?screen=main", json={"text": "PLAIN"})
    s = (await client.get("/api/state?screen=main")).json()
    assert s["text_colors"] is None


async def test_other_push_clears_colors(client):
    await client.post("/api/display/text?screen=main",
                      json={"text": "{red}X{/}"})
    await client.post("/api/display/matrix?screen=main",
                      json={"matrix": [[1] * COLS for _ in range(ROWS)]})
    s = (await client.get("/api/state?screen=main")).json()
    assert s["mode"] == "matrix_push"
    assert s["text_colors"] is None


# ── Persistence ───────────────────────────────────────────────────────────────

async def test_text_colors_survive_restart():
    async with LifespanManager(main.app) as m:
        transport = httpx.ASGITransport(app=m.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await c.post("/api/playlist/clear?screen=main")
            await c.post("/api/display/text?screen=main",
                         json={"text": "{violet}VIP{/} ONLY"})
            before = (await c.get("/api/state?screen=main")).json()
            assert before["text_colors"] is not None

    async with LifespanManager(main.app) as m:
        transport = httpx.ASGITransport(app=m.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            after = (await c.get("/api/state?screen=main")).json()
            assert after["mode"] == "text_push"
            assert after["text_colors"] == before["text_colors"]
            await c.post("/api/display/next?screen=main")
