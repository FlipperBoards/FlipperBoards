import httpx
import re
from charmap import text_to_matrix, blank_matrix

NEWS_API_URL = "https://newsapi.org/v2/top-headlines"

# Fallback RSS feeds when no API key is set
RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss",
    "https://feeds.reuters.com/reuters/topNews",
]

_cached_headlines: list[str] = []
_cache_idx: int = 0


async def get_news_matrix(rows: int, cols: int, api_key: str = "",
                           categories: list = None, sources: list = None) -> list[list[int]]:
    global _cached_headlines, _cache_idx

    if not _cached_headlines or _cache_idx >= len(_cached_headlines):
        _cached_headlines = await _fetch_headlines(api_key, categories, sources)
        _cache_idx = 0

    if not _cached_headlines:
        return _error_matrix(rows, cols, "NO NEWS AVAILABLE")

    headline = _cached_headlines[_cache_idx % len(_cached_headlines)]
    _cache_idx += 1

    return text_to_matrix(headline, rows, cols)


async def _fetch_headlines(api_key: str, categories: list, sources: list) -> list[str]:
    headlines = []

    if api_key:
        try:
            params = {"apiKey": api_key, "pageSize": 20, "language": "en"}
            if sources:
                params["sources"] = ",".join(sources)
            elif categories:
                params["category"] = categories[0]
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(NEWS_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            headlines = [a["title"].split(" - ")[0].strip()
                         for a in data.get("articles", []) if a.get("title")]
            return headlines
        except Exception:
            pass

    # Fallback: RSS (simple XML parsing)
    try:
        for feed_url in RSS_FEEDS[:2]:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(feed_url, follow_redirects=True)
                resp.raise_for_status()
                xml = resp.text
            titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', xml)
            for groups in titles:
                title = (groups[0] or groups[1]).strip()
                if title and len(title) > 10:
                    headlines.append(title)
            if len(headlines) >= 5:
                break
    except Exception:
        pass

    return headlines


def _center(text: str, cols: int) -> str:
    pad = max(0, (cols - len(text)) // 2)
    return " " * pad + text


def _error_matrix(rows: int, cols: int, msg: str) -> list[list[int]]:
    matrix = blank_matrix(rows, cols)
    from charmap import text_to_row
    matrix[0] = text_to_row(_center(msg, cols), cols)
    return matrix
