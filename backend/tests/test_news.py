"""Google News mode: feed routing (search / topics / top), RSS parsing with
source domain + pubDate, uniform client-side domain + recency filtering across
search AND topics, multiselect topics, rotation, resilience — mocked, no net."""
from datetime import datetime, timedelta, UTC
from email.utils import format_datetime

import pytest

from charmap import CHARS
from services import news
from services.news import build_feeds, filter_items, parse_items


def _text(matrix):
    return ["".join(CHARS[c] if c < 71 else "#" for c in row).strip() for row in matrix]


def _item(title, source, url, age_hours=1):
    dt = datetime.now(UTC) - timedelta(hours=age_hours)
    return (f"<item><title>{title} - {source}</title>"
            f"<source url=\"{url}\">{source}</source>"
            f"<pubDate>{format_datetime(dt)}</pubDate></item>")


def _rss(*items):
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{"".join(items)}</channel></rss>'


RSS = _rss(
    _item("Suns beat Lakers 120-118", "ESPN", "https://www.espn.com", age_hours=1),
    _item("Markets rally on tech earnings", "Reuters", "https://www.reuters.com", age_hours=50),
    _item("Local election results are in", "AP News", "https://apnews.com", age_hours=2),
)


@pytest.fixture(autouse=True)
def _clean():
    news._cache.clear()
    news._cursor.clear()
    yield
    news._cache.clear()
    news._cursor.clear()


# ── Feed routing ──────────────────────────────────────────────────────────────

def test_feeds_keyword_and_topics():
    feeds = build_feeds("suns", [], ["TOP", "BUSINESS"], [], "en", "US")
    assert any("/search?q=suns" in f for f in feeds)
    assert any(f.startswith("https://news.google.com/rss?") for f in feeds)      # TOP
    assert any("/topic/BUSINESS" in f for f in feeds)


def test_feeds_topic_only():
    feeds = build_feeds("", [], ["TECHNOLOGY"], [], "en", "US")
    assert feeds == ["https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?"
                     "hl=en-US&gl=US&ceid=US%3Aen"]


def test_feeds_domain_only_uses_search():
    feeds = build_feeds("", ["espn.com"], [], [], "en", "US")
    assert "/search?q=site%3Aespn.com" in feeds[0]


def test_feeds_default_top_stories():
    feeds = build_feeds("", [], [], [], "en", "US")
    assert feeds[0].startswith("https://news.google.com/rss?")


# ── Parsing ───────────────────────────────────────────────────────────────────

def test_parse_extracts_title_domain_date():
    items = parse_items(RSS)
    assert items[0]["title"] == "Suns beat Lakers 120-118"
    assert items[0]["domain"] == "espn.com"
    assert items[0]["published"] is not None


# ── Filtering (uniform, client-side) ──────────────────────────────────────────

def test_filter_include_domain():
    titles = filter_items(parse_items(RSS), ["espn.com"], [], "")
    assert titles == ["Suns beat Lakers 120-118"]


def test_filter_exclude_domain():
    titles = filter_items(parse_items(RSS), [], ["reuters.com"], "")
    assert "Markets rally on tech earnings" not in titles
    assert "Suns beat Lakers 120-118" in titles


def test_filter_recency_drops_old():
    # Reuters item is 50h old → excluded by a 24h window
    titles = filter_items(parse_items(RSS), [], [], "24h")
    assert "Markets rally on tech earnings" not in titles
    assert "Suns beat Lakers 120-118" in titles


def test_filter_dedupes_titles():
    dup = _rss(_item("Same Story", "ESPN", "https://espn.com"),
               _item("Same Story", "CBS", "https://cbssports.com"))
    assert filter_items(parse_items(dup), [], [], "") == ["Same Story"]


# ── Rendering: filters apply across topic feeds too ───────────────────────────

async def test_domain_filter_applies_to_topics(monkeypatch):
    async def fake_fetch(url):
        return parse_items(RSS)   # every feed returns the same 3 items
    monkeypatch.setattr(news, "_fetch_items", fake_fetch)

    # Topic browse (no keyword) + include espn.com → only the ESPN headline
    m = _text(await news.get_news_matrix(6, 22, topics=["SPORTS", "BUSINESS"],
                                         include_domains="espn.com", screen_id="t"))
    assert any("SUNS BEAT LAKERS" in r for r in m)


async def test_recency_applies_to_topics(monkeypatch):
    async def fake_fetch(url):
        return parse_items(RSS)
    monkeypatch.setattr(news, "_fetch_items", fake_fetch)
    # 24h recency on a topic drops the 50h-old Reuters story across the board
    seen = set()
    for _ in range(6):
        joined = " ".join(_text(await news.get_news_matrix(
            6, 22, topics=["BUSINESS"], when="24h", screen_id="r")))
        for kw in ("SUNS", "ELECTION", "MARKETS"):
            if kw in joined:
                seen.add(kw)
    assert "MARKETS" not in seen
    assert {"SUNS", "ELECTION"} <= seen


async def test_rotation_cycles(monkeypatch):
    async def fake_fetch(url):
        return parse_items(RSS)
    monkeypatch.setattr(news, "_fetch_items", fake_fetch)
    a = _text(await news.get_news_matrix(6, 22, keyword="suns", screen_id="s"))
    b = _text(await news.get_news_matrix(6, 22, keyword="suns", screen_id="s"))
    assert a != b


async def test_no_matches_shows_message(monkeypatch):
    async def fake_fetch(url):
        return parse_items(RSS)
    monkeypatch.setattr(news, "_fetch_items", fake_fetch)
    m = _text(await news.get_news_matrix(6, 22, include_domains="nonexistent.com"))
    assert any("NO NEWS" in r for r in m)


async def test_stale_cache_on_outage(monkeypatch):
    async def ok(url):
        return parse_items(RSS)
    monkeypatch.setattr(news, "_fetch_items", ok)
    await news.get_news_matrix(6, 22, topics=["SPORTS"], screen_id="s")
    key = next(iter(news._cache))
    news._cache[key] = (0.0, news._cache[key][1])  # expire

    async def boom(url):
        raise RuntimeError("google down")
    monkeypatch.setattr(news, "_fetch_items", boom)

    async def no_fallback():
        return []
    monkeypatch.setattr(news, "_fallback", no_fallback)
    m = _text(await news.get_news_matrix(6, 22, topics=["SPORTS"], screen_id="s"))
    assert not any("NO NEWS" in r for r in m)  # served stale


async def test_mode_registered(client):
    modes = (await client.get("/api/modes/available")).json()
    news_mode = next((m for m in modes if m["id"] == "news"), None)
    assert news_mode is not None
    schema = news_mode["config_schema"]
    assert schema["topics"]["type"] == "multiselect"
    assert {"keyword", "include_domains", "exclude_domains", "when"} <= set(schema)
