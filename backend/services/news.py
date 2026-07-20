"""News headlines via Google News RSS (no API key).

Google News RSS gives keyword search, topic sections, and locale as plain RSS
URLs — but source (`site:`) and recency (`when:`) operators only work on the
/search endpoint, not on topic sections. So we parse each item's source domain
(`<source url>`) and publish time (`<pubDate>`) and apply the include/exclude
domain and recency filters CLIENT-SIDE, uniformly across search AND topic
results. That's the same searching/filtering the google-news-api project wraps,
without its dependency chain (which won't build on a Pi).

Per-screen config (all optional):
  keyword          free text, e.g. "Phoenix Suns"
  topics           multiselect — TOP / WORLD / BUSINESS / SPORTS / …
  include_domains  comma list — only these sources
  exclude_domains  comma list — never these sources
  when             recency (1h / 24h / 7d) — applies to search and topics
  language/country locale (ISO codes)
"""
import asyncio
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, UTC
from email.utils import parsedate_to_datetime

import httpx

from charmap import blank_matrix, text_to_matrix, text_to_row

BASE = "https://news.google.com/rss"
TOPICS = {"WORLD", "NATION", "BUSINESS", "TECHNOLOGY",
          "ENTERTAINMENT", "SPORTS", "SCIENCE", "HEALTH"}
RECENCY_SECONDS = {"1h": 3600, "24h": 86400, "7d": 604800}

CACHE_SECONDS = 300

# Emergency fallback if Google News is unreachable and nothing is cached
RSS_FALLBACK = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss",
]

_cache: dict[str, tuple[float, list[str]]] = {}
_cursor: dict[str, int] = {}


def _domains(raw) -> list[str]:
    if isinstance(raw, (list, tuple)):
        raw = ",".join(str(d) for d in raw)
    out = []
    for d in str(raw or "").split(","):
        d = d.strip().lower().removeprefix("http://").removeprefix("https://").removeprefix("www.")
        d = d.split("/")[0]
        if d:
            out.append(d)
    return out


def _parse_topics(raw, legacy_topic="") -> list[str]:
    src = raw if raw else legacy_topic
    if isinstance(src, str):
        parts = [p.strip().upper() for p in src.split(",")]
    elif isinstance(src, (list, tuple)):
        parts = [str(p).strip().upper() for p in src]
    else:
        parts = []
    # Keep TOP (top stories) plus any valid section; preserve order, dedupe
    seen, out = set(), []
    for p in parts:
        if (p == "TOP" or p in TOPICS) and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _domain_query(includes: list[str], excludes: list[str]) -> str:
    parts = []
    if len(includes) == 1:
        parts.append(f"site:{includes[0]}")
    elif includes:
        parts.append("(" + " OR ".join(f"site:{d}" for d in includes) + ")")
    parts += [f"-site:{d}" for d in excludes]
    return " ".join(parts).strip()


def _locale(language: str, country: str) -> str:
    lang = (language or "en").strip() or "en"
    ctry = (country or "US").strip().upper() or "US"
    return urllib.parse.urlencode({"hl": f"{lang}-{ctry}", "gl": ctry, "ceid": f"{ctry}:{lang}"})


def build_feeds(keyword: str, includes: list[str], topics: list[str],
                excludes: list[str], language: str, country: str) -> list[str]:
    """The RSS feed URLs to pull. Keyword → search feed; each topic → its
    section (TOP → top stories). With neither, fall back to a domain search
    (include-only) or plain top stories."""
    loc = _locale(language, country)
    feeds = []
    kw = (keyword or "").strip()
    if kw:
        feeds.append(f"{BASE}/search?q={urllib.parse.quote(kw)}&{loc}")
    for t in topics:
        if t == "TOP":
            feeds.append(f"{BASE}?{loc}")
        else:
            feeds.append(f"{BASE}/headlines/section/topic/{t}?{loc}")
    if not feeds:
        if includes:
            feeds.append(f"{BASE}/search?q={urllib.parse.quote(_domain_query(includes, excludes))}&{loc}")
        else:
            feeds.append(f"{BASE}?{loc}")
    return feeds


def _host(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host.removeprefix("www.")


def parse_items(xml_text: str) -> list[dict]:
    """RSS → [{title, domain, published}] with Google's ' - Source' suffix
    stripped from titles and the source's real domain extracted."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        if source and title.endswith(f" - {source}"):
            title = title[: -(len(source) + 3)].strip()
        if len(title) <= 3:
            continue
        domain = _host(source_el.get("url", "")) if source_el is not None else ""
        published = None
        raw_date = item.findtext("pubDate")
        if raw_date:
            try:
                published = parsedate_to_datetime(raw_date)
            except (TypeError, ValueError):
                published = None
        items.append({"title": title, "domain": domain, "published": published})
    return items


def _domain_match(domain: str, filters: list[str]) -> bool:
    domain = (domain or "").lower()
    return any(domain == f or domain.endswith(f".{f}") for f in filters)


def _within(published, when: str) -> bool:
    if when not in RECENCY_SECONDS:
        return True
    if published is None:
        return True  # keep undated items rather than hide everything
    now = datetime.now(UTC)
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    return (now - published).total_seconds() <= RECENCY_SECONDS[when]


def filter_items(items: list[dict], includes: list[str], excludes: list[str],
                 when: str) -> list[str]:
    """Apply domain + recency filters uniformly, dedupe titles, keep order."""
    seen, out = set(), []
    for it in items:
        if includes and not _domain_match(it["domain"], includes):
            continue
        if excludes and _domain_match(it["domain"], excludes):
            continue
        if not _within(it["published"], when):
            continue
        if it["title"] not in seen:
            seen.add(it["title"])
            out.append(it["title"])
    return out


async def _fetch_items(url: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return parse_items(resp.text)


async def _fallback() -> list[str]:
    for feed in RSS_FALLBACK:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(feed)
                resp.raise_for_status()
            titles = [it["title"] for it in parse_items(resp.text)]
            if titles:
                return titles
        except Exception:
            continue
    return []


async def get_headlines(cache_key: str, feeds: list[str], includes: list[str],
                        excludes: list[str], when: str) -> list[str]:
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    results = await asyncio.gather(*[_fetch_items(u) for u in feeds],
                                   return_exceptions=True)
    items = []
    for r in results:
        if isinstance(r, list):
            items.extend(r)
    if items:
        headlines = filter_items(items, includes, excludes, when)
        _cache[cache_key] = (now, headlines)  # cache even if filters emptied it
        return headlines
    if cached:
        return cached[1]  # every feed errored — stale beats blank
    return await _fallback()


async def get_news_matrix(rows: int, cols: int, keyword: str = "",
                          include_domains="", exclude_domains="", topics=None,
                          topic: str = "", when: str = "", language: str = "en",
                          country: str = "US", screen_id: str = "main") -> list[list[int]]:
    includes = _domains(include_domains)
    excludes = _domains(exclude_domains)
    topic_list = _parse_topics(topics, topic)
    feeds = build_feeds(keyword, includes, topic_list, excludes, language, country)

    cache_key = "|".join([keyword.strip(), ",".join(topic_list), ",".join(includes),
                          ",".join(excludes), when, language, country])
    headlines = await get_headlines(cache_key, feeds, includes, excludes, when)
    if not headlines:
        return _message(rows, cols, "NO NEWS AVAILABLE")

    key = f"{screen_id}:{cache_key}"
    idx = _cursor.get(key, 0) % len(headlines)
    _cursor[key] = idx + 1
    return text_to_matrix(headlines[idx], rows, cols)


def _message(rows: int, cols: int, msg: str) -> list[list[int]]:
    matrix = blank_matrix(rows, cols)
    pad = max(0, (cols - len(msg)) // 2)
    matrix[0] = text_to_row(" " * pad + msg, cols)
    return matrix
