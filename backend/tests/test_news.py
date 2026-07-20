"""Google News mode: query building (keyword + domain filters), URL routing
(search vs topic vs top), RSS parsing, rotation, and resilience — mocked
fetch, no network."""
import pytest

from charmap import CHARS
from services import news
from services.news import build_query, build_url, parse_rss


def _text(matrix):
    return ["".join(CHARS[c] if c < 71 else "#" for c in row).strip() for row in matrix]


RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>Suns beat Lakers 120-118 - ESPN</title><source url="http://espn.com">ESPN</source></item>
  <item><title>Markets rally on tech earnings - Reuters</title><source>Reuters</source></item>
  <item><title>Local election results are in - AP News</title><source>AP News</source></item>
</channel></rss>"""


@pytest.fixture(autouse=True)
def _clean():
    news._cache.clear()
    news._cursor.clear()
    yield
    news._cache.clear()
    news._cursor.clear()


# ── Query building ────────────────────────────────────────────────────────────

def test_query_keyword_only():
    assert build_query("Phoenix Suns", "", "", "") == "Phoenix Suns"


def test_query_single_include_domain():
    assert build_query("suns", "espn.com", "", "") == "suns site:espn.com"


def test_query_multiple_include_domains_use_or():
    q = build_query("", "espn.com, cbssports.com", "", "")
    assert q == "(site:espn.com OR site:cbssports.com)"


def test_query_exclude_domains():
    assert build_query("ai", "", "example.com, spam.net", "") == "ai -site:example.com -site:spam.net"


def test_query_strips_scheme_and_www():
    assert build_query("", "https://www.espn.com/nba", "", "") == "site:espn.com"


def test_query_appends_when():
    assert build_query("ai", "", "", "24h") == "ai when:24h"


def test_query_blank_when_nothing_set():
    assert build_query("", "", "", "") == ""


# ── URL routing ───────────────────────────────────────────────────────────────

def test_url_search_when_keyword_or_domains():
    url = build_url("suns", "espn.com", "", "TOP", "", "en", "US")
    assert "/rss/search?q=" in url
    assert "site%3Aespn.com" in url  # url-encoded


def test_url_topic_when_no_query():
    url = build_url("", "", "", "TECHNOLOGY", "", "en", "US")
    assert "/rss/headlines/section/topic/TECHNOLOGY" in url


def test_url_top_stories_default():
    url = build_url("", "", "", "TOP", "", "en", "US")
    assert url.startswith("https://news.google.com/rss?")
    assert "hl=en-US" in url and "ceid=US%3Aen" in url


def test_url_locale():
    url = build_url("", "", "", "TOP", "", "fr", "FR")
    assert "hl=fr-FR" in url and "gl=FR" in url


# ── RSS parsing ───────────────────────────────────────────────────────────────

def test_parse_strips_source_suffix():
    titles = parse_rss(RSS)
    assert titles == [
        "Suns beat Lakers 120-118",
        "Markets rally on tech earnings",
        "Local election results are in",
    ]


def test_parse_bad_xml_returns_empty():
    assert parse_rss("<not xml") == []


# ── Rendering + rotation ──────────────────────────────────────────────────────

async def test_renders_and_rotates(monkeypatch):
    async def fake_fetch(url):
        return parse_rss(RSS)
    monkeypatch.setattr(news, "_fetch", fake_fetch)

    a = _text(await news.get_news_matrix(6, 22, keyword="suns", screen_id="s"))
    b = _text(await news.get_news_matrix(6, 22, keyword="suns", screen_id="s"))
    assert any("SUNS BEAT LAKERS" in " ".join(a) for a in [a])
    assert a != b  # cursor advanced to the next headline


async def test_stale_cache_survives_outage(monkeypatch):
    async def ok(url):
        return parse_rss(RSS)
    monkeypatch.setattr(news, "_fetch", ok)
    await news.get_news_matrix(6, 22, topic="SPORTS", screen_id="s")
    key = next(iter(news._cache))
    news._cache[key] = (0.0, news._cache[key][1])  # expire

    async def boom(url):
        raise RuntimeError("google down")
    monkeypatch.setattr(news, "_fetch", boom)

    async def no_fallback():
        return []
    monkeypatch.setattr(news, "_fallback", no_fallback)
    m = _text(await news.get_news_matrix(6, 22, topic="SPORTS", screen_id="s"))
    assert not any("NO NEWS" in r for r in m)  # served stale, not the empty message


async def test_no_news_message(monkeypatch):
    async def empty(url):
        return []
    monkeypatch.setattr(news, "_fetch", empty)

    async def no_fallback():
        return []
    monkeypatch.setattr(news, "_fallback", no_fallback)
    m = _text(await news.get_news_matrix(6, 22))
    assert any("NO NEWS" in r for r in m)


async def test_mode_registered(client):
    modes = (await client.get("/api/modes/available")).json()
    news_mode = next((m for m in modes if m["id"] == "news"), None)
    assert news_mode is not None
    schema = news_mode["config_schema"]
    assert {"keyword", "include_domains", "exclude_domains", "topic"} <= set(schema)
