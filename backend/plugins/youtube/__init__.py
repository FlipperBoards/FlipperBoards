"""
YouTube plugin — shows subscriber/view counts for a channel.

Install: set FB_PLUGINS=youtube
Config: set API key and channel ID in the Modes tab of the remote control.

YouTube Data API v3 is free up to 10,000 units/day. A channel lookup costs
1 unit, so even refreshing every 30 seconds only uses ~2,880 units/day.

Get a key: https://console.cloud.google.com → APIs → YouTube Data API v3
Find channel ID: youtube.com/channel/<ID> or use @handle lookup below.
"""
from __future__ import annotations
import httpx

from plugins.base import FlipperPlugin
from mode_registry import ModeDefinition
from charmap import text_to_matrix

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


def _format_count(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class YouTubePlugin(FlipperPlugin):
    name = "youtube"
    version = "0.1.0"

    @property
    def modes(self) -> list[ModeDefinition]:
        return [
            ModeDefinition(
                id="youtube_subs",
                label="YouTube Subs",
                icon="▶️",
                description="Live subscriber count for a YouTube channel",
                config_schema={
                    "api_key": {
                        "label": "YouTube Data API v3 Key",
                        "type": "string",
                        "secret": True,
                        "placeholder": "AIzaSy...",
                        "help": "console.cloud.google.com → APIs → YouTube Data API v3",
                    },
                    "channel_id": {
                        "label": "Channel ID",
                        "type": "string",
                        "placeholder": "UCxxxxxxxxxxxxxxxxxxxxxx",
                        "help": "Found in the channel URL: youtube.com/channel/<ID>",
                    },
                    "stat": {
                        "label": "Statistic",
                        "type": "select",
                        "options": [
                            {"value": "subscriberCount", "label": "Subscribers"},
                            {"value": "viewCount",       "label": "Total Views"},
                            {"value": "videoCount",      "label": "Videos"},
                        ],
                        "default": "subscriberCount",
                    },
                },
                render=self._render,
            ),
        ]

    async def _render(
        self, rows: int, cols: int, config: dict, settings: dict
    ) -> list[list[int]]:
        api_key = config.get("api_key", "").strip()
        channel_id = config.get("channel_id", "").strip()
        stat = config.get("stat", "subscriberCount")

        if not api_key or not channel_id:
            return text_to_matrix(
                "YOUTUBE: ADD API KEY + CHANNEL ID IN MODES CONFIG", rows, cols
            )

        stat_labels = {
            "subscriberCount": "SUBSCRIBERS",
            "viewCount":       "VIEWS",
            "videoCount":      "VIDEOS",
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    f"{YOUTUBE_API}/channels",
                    params={"part": "statistics", "id": channel_id, "key": api_key},
                )
                r.raise_for_status()
                data = r.json()
                items = data.get("items", [])
                if not items:
                    return text_to_matrix("YOUTUBE: CHANNEL NOT FOUND", rows, cols)
                count = int(items[0]["statistics"].get(stat, 0))
                label = stat_labels.get(stat, stat.upper())
                return text_to_matrix(f"{_format_count(count)} {label}", rows, cols)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return text_to_matrix("YOUTUBE: INVALID API KEY", rows, cols)
            return text_to_matrix("YOUTUBE: API ERROR", rows, cols)
        except Exception:
            return text_to_matrix("YOUTUBE: ERROR", rows, cols)


plugin = YouTubePlugin()
