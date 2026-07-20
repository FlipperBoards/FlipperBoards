"""News headlines via Google News RSS (no API key).

Google News RSS exposes the same search and filtering the google-news-api
project wraps — free-text keyword search, `site:` / `-site:` domain filters,
topic sections, recency (`when:`), and locale — but as plain RSS URLs, so we
hit them directly with httpx and stdlib XML (no extra dependency to build on
a Raspberry Pi).

Per-screen config (all optional):
  keyword          free text, e.g. "Phoenix Suns"
  include_domains  comma list — only these sources (site:espn.com OR …)
  exclude_domains  comma list — never these sources (-site:…)
  topic            section browse when no keyword/domains are set
  when             recency for searches (1h / 24h / 7d)
  language/country locale (ISO codes)
"""
import time
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

from charmap import blank_matrix, text_to_matrix, text_to_row

BASE = "https://news.google.com/rss"
TOPICS = {"WORLD", "NATION", "BUSINESS", "TECHNOLOGY",
          "ENTERTAINMENT", "SPORTS", "SCIENCE", "HEALTH"}

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


def build_query(keyword: str, include_domains, exclude_domains, when: str) -> str:
    """Combine the per-screen filters into a Google News search query."""
    parts = []
    keyword = (keyword or "").strip()
    if keyword:
        parts.append(keyword)
    inc = _domains(include_domains)
    if len(inc) == 1:
        parts.append(f"site:{inc[0]}")
    elif inc:
        parts.append("(" + " OR ".join(f"site:{d}" for d in inc) + ")")
    for d in _domains(exclude_domains):
        parts.append(f"-site:{d}")
    if when:
        parts.append(f"when:{when}")
    return " ".join(parts).strip()


def _locale(language: str, country: str) -> str:
    lang = (language or "en").strip() or "en"
    ctry = (country or "US").strip().upper() or "US"
    return urllib.parse.urlencode({"hl": f"{lang}-{ctry}", "gl": ctry, "ceid": f"{ctry}:{lang}"})


def build_url(keyword: str, include_domains, exclude_domains, topic: str,
              when: str, language: str, country: str) -> str:
    loc = _locale(language, country)
    query = build_query(keyword, include_domains, exclude_domains, when)
    if query:
        return f"{BASE}/search?q={urllib.parse.quote(query)}&{loc}"
    topic = (topic or "TOP").strip().upper()
    if topic in TOPICS:
        return f"{BASE}/headlines/section/topic/{topic}?{loc}"
    return f"{BASE}?{loc}"


def parse_rss(xml_text: str) -> list[str]:
    """Item titles, with the trailing ' - Source' that Google appends removed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    titles = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        if source and title.endswith(f" - {source}"):
            title = title[: -(len(source) + 3)].strip()
        if len(title) > 3:
            titles.append(title)
    return titles


async def _fetch(url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return parse_rss(resp.text)


async def _fallback() -> list[str]:
    for feed in RSS_FALLBACK:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(feed)
                resp.raise_for_status()
            titles = parse_rss(resp.text)
            if titles:
                return titles
        except Exception:
            continue
    return []


async def get_headlines(url: str) -> list[str]:
    now = time.time()
    cached = _cache.get(url)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        titles = await _fetch(url)
        if titles:
            _cache[url] = (now, titles)
            return titles
    except Exception:
        pass
    if cached:
        return cached[1]  # stale beats blank
    return await _fallback()


async def get_news_matrix(rows: int, cols: int, keyword: str = "",
                          include_domains="", exclude_domains="", topic: str = "TOP",
                          when: str = "", language: str = "en", country: str = "US",
                          screen_id: str = "main") -> list[list[int]]:
    url = build_url(keyword, include_domains, exclude_domains, topic, when, language, country)
    headlines = await get_headlines(url)
    if not headlines:
        return _message(rows, cols, "NO NEWS AVAILABLE")
    key = f"{screen_id}:{url}"
    idx = _cursor.get(key, 0) % len(headlines)
    _cursor[key] = idx + 1
    return text_to_matrix(headlines[idx], rows, cols)


def _message(rows: int, cols: int, msg: str) -> list[list[int]]:
    matrix = blank_matrix(rows, cols)
    pad = max(0, (cols - len(msg)) // 2)
    matrix[0] = text_to_row(" " * pad + msg, cols)
    return matrix
