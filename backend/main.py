import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import mimetypes

import anyio
from fastapi import (FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query,
                     UploadFile, File, Form, Request, Response)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("flipperboards")

import database
import mode_registry
import plugins as plugin_registry
from websocket_manager import manager
from charmap import blank_matrix, text_to_matrix, text_to_matrix_colored
from config import settings


# ── Org resolution ────────────────────────────────────────────────────────────
# Self-hosted: always org 1. SaaS: swap this dependency for JWT middleware.

def get_org_id() -> int:
    return database.DEFAULT_ORG_ID

async def _effective_settings() -> dict:
    """DB settings with env-var fallbacks (FB_WEATHER_API_KEY / FB_NEWS_API_KEY)
    applied when the DB value is empty — so docker-compose env config works."""
    s = await database.get_settings()
    if not s.get("weather_api_key") and settings.weather_api_key:
        s["weather_api_key"] = settings.weather_api_key
    if not s.get("news_api_key") and settings.news_api_key:
        s["news_api_key"] = settings.news_api_key
    return s


# ── Authentication ────────────────────────────────────────────────────────────
# Single shared password for control surfaces (think: bar staff). The display
# and all reads stay open — a wall-mounted TV can't log in. Off by default.

AUTH_COOKIE = "fb_session"
SESSION_DAYS = 30

# Cached so the middleware doesn't hit the DB on every request; kept in sync
# by lifespan startup and /api/auth/configure.
_auth_state = {"enabled": False}


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"{salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
        return secrets.compare_digest(candidate, digest)
    except (ValueError, AttributeError):
        return False


async def _request_authenticated(request: Request) -> bool:
    token = request.cookies.get(AUTH_COOKIE)
    return bool(token) and await database.get_session(token)


async def _issue_session(response: Response) -> None:
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(days=SESSION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    await database.add_session(token, expires)
    response.set_cookie(AUTH_COOKIE, token, max_age=SESSION_DAYS * 86400,
                        httponly=True, samesite="lax")


def _public_settings(s: dict) -> dict:
    """Settings as sent to clients — never the password hash."""
    return {k: v for k, v in s.items() if k != "auth_password_hash"}


# ── Upload directory ──────────────────────────────────────────────────────────

_upload_setting = settings.upload_dir
UPLOAD_DIR = _upload_setting if os.path.isabs(_upload_setting) else os.path.join(os.path.dirname(__file__), _upload_setting)
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Per-screen runtime state ──────────────────────────────────────────────────

class ScreenState:
    def __init__(self, screen_id: str, name: str, rows: int, cols: int):
        self.screen_id = screen_id
        self.name = name
        self.rows = rows
        self.cols = cols
        self.matrix: list[list[int]] = blank_matrix(rows, cols)
        self.color_matrix: list[list[str]] | None = None
        self.text_colors: list | None = None  # per-tile text color overrides (markup)
        self.photo_url: str | None = None
        # Universal playlist — drives rotation when non-empty
        self.playlist_items: list[dict] = []
        self.playlist_pos: int = 0
        self.mode: str = "clock"
        self.mode_idx: int = 0
        self.rotation_task: asyncio.Task | None = None
        self.push_timer: asyncio.Task | None = None
        # Quiet-hours schedule: {enabled, off_time "HH:MM", on_time "HH:MM", days [0-6]}
        self.schedule: dict = {}
        self.sleeping: bool = False
        self.sched_prev: bool | None = None  # last computed in-window value (edge detection)


_screens: dict[str, ScreenState] = {}

# MQTT bridge instance — created in lifespan when enabled in settings
_mqtt = None


def get_screen_state(screen_id: str) -> ScreenState:
    if screen_id not in _screens:
        raise HTTPException(404, f"Screen '{screen_id}' not found")
    return _screens[screen_id]


# ── Built-in mode registration ────────────────────────────────────────────────

def _register_builtin_modes():
    from services.clock import get_clock_matrix
    from services.weather import get_weather_matrix
    from services.news import get_news_matrix
    from services.quotes import get_quote_matrix
    from services.calendar_svc import get_calendar_matrix
    from mode_registry import ModeDefinition

    async def render_clock(rows, cols, config, s):
        return get_clock_matrix(rows, cols,
            fmt=s.get("clock_format", "12h"),
            show_date=s.get("show_date", "true") == "true",
            timezone=s.get("timezone", "UTC"))

    async def render_weather(rows, cols, config, s):
        return await get_weather_matrix(rows, cols,
            api_key=s.get("weather_api_key", ""),
            location=s.get("weather_location", ""),
            units=s.get("weather_units", "imperial"))

    async def render_news(rows, cols, config, s):
        cats = json.loads(s.get("news_categories", '["general"]'))
        srcs = json.loads(s.get("news_sources", "[]"))
        return await get_news_matrix(rows, cols,
            api_key=s.get("news_api_key", ""), categories=cats, sources=srcs,
            screen_id=config.get("_screen_id", "main"))

    async def render_quotes(rows, cols, config, s):
        return await get_quote_matrix(rows, cols, custom_quotes=config.get("custom_quotes", ""),
                                      screen_id=config.get("_screen_id", "main"))

    async def render_calendar(rows, cols, config, s):
        return await get_calendar_matrix(rows, cols,
            ical_url=s.get("calendar_ical_url", ""),
            timezone=s.get("timezone", "UTC"))

    async def render_sports(rows, cols, config, s):
        from services.sports import get_sports_matrix
        return await get_sports_matrix(rows, cols,
            league=config.get("league", "nfl"),
            team=config.get("team", ""),
            screen_id=config.get("_screen_id", "main"))

    async def render_countdown(rows, cols, config, s):
        from services.countdown import get_countdown_matrix
        return get_countdown_matrix(rows, cols,
            target=config.get("target", ""),
            label=config.get("label", ""),
            done_text=config.get("done_text", ""),
            count_up=config.get("count_up", "no") == "yes",
            timezone=s.get("timezone", "UTC"))

    async def render_stocks(rows, cols, config, s):
        from services.ticker import get_stocks_matrix
        return await get_stocks_matrix(rows, cols,
            symbols=config.get("symbols", ""),
            screen_id=config.get("_screen_id", "main"))

    async def render_data(rows, cols, config, s):
        from services.ticker import get_data_matrix
        return await get_data_matrix(rows, cols,
            url=config.get("url", ""),
            template=config.get("template", ""),
            label=config.get("label", ""))

    _text_schema = {
        "message": {
            "type": "textarea",
            "label": "Message",
            "placeholder": "Enter text to display…",
            "help": "Single message. Leave blank to use the Text tab rotation queue.",
        }
    }
    _quotes_schema = {
        "custom_quotes": {
            "type": "textarea",
            "label": "Custom Quotes (one per line)",
            "placeholder": "Enter one quote per line…\nLeave blank to use built-in quotes.",
            "help": "Optional. Overrides built-in quotes when filled in.",
        }
    }
    _countdown_schema = {
        "target": {
            "type": "text",
            "label": "Target Date & Time",
            "placeholder": "2027-01-01 00:00",
            "help": "YYYY-MM-DD HH:MM in your configured timezone.",
        },
        "label": {
            "type": "text",
            "label": "Label",
            "placeholder": "NEW YEARS",
        },
        "done_text": {
            "type": "text",
            "label": "When Finished",
            "placeholder": "IT'S TIME!",
        },
        "count_up": {
            "type": "select",
            "label": "Direction",
            "options": [{"value": "no", "label": "Count down to the date"},
                        {"value": "yes", "label": "Count up since the date"}],
            "default": "no",
        },
    }
    from services.sports import LEAGUES
    _sports_schema = {
        "league": {
            "type": "select",
            "label": "League",
            "options": [{"value": key, "label": label} for key, (_, label) in LEAGUES.items()],
            "default": "nfl",
        },
        "team": {
            "type": "text",
            "label": "Team Filter",
            "placeholder": "e.g. KC — abbreviation or name",
            "help": "Optional. Stay on one team's game (scores update live) instead of rotating through all games.",
        },
    }
    _stocks_schema = {
        "symbols": {
            "type": "text",
            "label": "Symbols",
            "placeholder": "AAPL, MSFT, BTC-USD",
            "help": "Comma-separated Yahoo Finance symbols. Crypto works too (BTC-USD, ETH-USD).",
        },
    }
    _data_schema = {
        "url": {
            "type": "text",
            "label": "JSON URL",
            "placeholder": "https://api.example.com/stats",
            "help": "Any JSON endpoint — polled every 2 minutes by the server.",
        },
        "template": {
            "type": "text",
            "label": "Template",
            "placeholder": "SUBS {data.followers}",
            "help": "Placeholders use {dot.path.0.notation} into the JSON response.",
        },
        "label": {
            "type": "text",
            "label": "Label",
            "placeholder": "Optional prefix",
        },
    }
    builtin = [
        ModeDefinition("clock",    "Clock",         "🕐", "Live time & date",       render=render_clock),
        ModeDefinition("weather",  "Weather",       "🌤", "Current conditions",      render=render_weather),
        ModeDefinition("news",     "News",          "📰", "Top headlines",           render=render_news),
        ModeDefinition("quotes",   "Quotes",        "💬", "Inspirational quotes",    config_schema=_quotes_schema, render=render_quotes),
        ModeDefinition("calendar", "Calendar",      "📅", "Upcoming events",         render=render_calendar),
        ModeDefinition("sports",   "Sports",        "🏆", "Live game scores",        config_schema=_sports_schema, render=render_sports),
        ModeDefinition("countdown", "Countdown",     "⏳", "Count down to a date",    config_schema=_countdown_schema, render=render_countdown),
        ModeDefinition("stocks",   "Stocks",        "📈", "Stock & crypto prices",   config_schema=_stocks_schema, render=render_stocks),
        ModeDefinition("data",     "Data Feed",     "🔌", "Poll any JSON URL",       config_schema=_data_schema, render=render_data),
        ModeDefinition("text",     "Text Messages", "✏️", "Custom messages",         config_schema=_text_schema, render=None),
    ]
    for m in builtin:
        mode_registry.register(m)


# ── Content rendering ─────────────────────────────────────────────────────────

async def _render_mode(mode: str, rows: int, cols: int, db_settings: dict, screen_id: str = "main", mode_config: dict | None = None) -> list:
    # text mode is special: config inline message overrides the DB rotation queue
    if mode == "text":
        config = mode_config or {}
        if config.get("message", "").strip():
            return text_to_matrix(config["message"], rows, cols)
        messages = await database.get_text_messages(screen_id)
        from services.text_svc import get_text_matrix
        return await get_text_matrix(rows, cols, messages, screen_id=screen_id)

    # all other modes (built-in and plugin) go through the registry.
    # _screen_id rides along in config so per-screen renderers (news/quotes
    # cursors) know which board they're feeding without changing the plugin API.
    cfg = dict(mode_config or {})
    cfg["_screen_id"] = screen_id
    matrix = await mode_registry.render(mode, rows, cols, cfg, db_settings)
    if matrix is not None:
        return matrix
    return blank_matrix(rows, cols)


async def _render_playlist_item(state: ScreenState, transition: str | None = None):
    """Render and broadcast the current playlist item."""
    if not state.playlist_items:
        return

    item = state.playlist_items[state.playlist_pos]
    item_type = item["type"]
    content = item.get("content", {})

    state.color_matrix = None
    state.text_colors = None
    state.photo_url = None

    if item_type == "mode":
        mode = content.get("mode", "clock")
        state.mode = mode
        db_settings = await _effective_settings()
        mode_entries = await database.get_modes(state.screen_id)
        mode_entry = next((m for m in mode_entries if m["mode"] == mode), None)
        mode_config = mode_entry.get("config", {}) if mode_entry else {}
        state.matrix = await _render_mode(mode, state.rows, state.cols, db_settings,
                                          screen_id=state.screen_id, mode_config=mode_config)

    elif item_type == "text":
        state.mode = "text_push"
        state.matrix, state.text_colors = text_to_matrix_colored(
            content.get("text", ""), state.rows, state.cols)

    elif item_type == "photo":
        state.mode = "photo_push"
        state.photo_url = content.get("url", "")

    elif item_type == "color":
        state.mode = "image_push"
        state.color_matrix = content.get("color_matrix")

    elif item_type == "matrix":
        state.mode = "matrix_push"
        stored = content.get("matrix") or blank_matrix(state.rows, state.cols)
        state.matrix = _normalize_matrix(stored, state.rows, state.cols)

    elif item_type == "scoreboard":
        from services.scoreboard import get_scoreboard_matrix
        state.mode = "scoreboard"
        state.matrix = get_scoreboard_matrix(
            state.rows, state.cols,
            content.get("home_name", "HOME"), content.get("away_name", "AWAY"),
            content.get("home_score", 0), content.get("away_score", 0),
        )

    elif item_type == "menu":
        from services.menu import get_menu_matrix
        state.mode = "menu"
        state.matrix = get_menu_matrix(
            state.rows, state.cols,
            title=content.get("title", ""),
            entries=content.get("entries", []),
            screen_id=state.screen_id,
        )

    await _broadcast_screen(state, transition=transition)


async def advance_screen_mode(screen_id: str):
    """Advance to the next content item and broadcast."""
    if screen_id not in _screens:
        return

    state = _screens[screen_id]
    _cancel_push_timer(state)

    # Universal playlist takes priority when items exist
    if state.playlist_items:
        old_pos = state.playlist_pos
        n = len(state.playlist_items)
        now = await _now_local()
        for step in range(1, n + 1):
            pos = (old_pos + step) % n
            if _item_eligible(state.playlist_items[pos], now):
                state.playlist_pos = pos
                # Full-board sweep only when the displayed item actually changes
                await _render_playlist_item(
                    state, transition="sweep" if pos != old_pos else None)
                return
        # Every item is outside its time window — fall back to the clock
        db_settings = await _effective_settings()
        from services.clock import get_clock_matrix
        state.mode = "clock"
        state.color_matrix = None
        state.photo_url = None
        state.matrix = get_clock_matrix(
            state.rows, state.cols,
            fmt=db_settings.get("clock_format", "12h"),
            show_date=db_settings.get("show_date", "true") == "true",
            timezone=db_settings.get("timezone", "UTC"),
        )
        await _broadcast_screen(state)
        return

    # Fallback: rotate through enabled modes
    db_settings = await _effective_settings()
    modes = await database.get_modes(screen_id)
    enabled = [m for m in modes if m["enabled"]]
    if not enabled:
        return

    state.mode_idx = (state.mode_idx + 1) % len(enabled)
    mode_entry = enabled[state.mode_idx]
    mode_name = mode_entry["mode"]
    state.mode = mode_name
    state.color_matrix = None
    state.text_colors = None
    state.photo_url = None

    state.matrix = await _render_mode(
        mode_name, state.rows, state.cols, db_settings,
        screen_id=screen_id, mode_config=mode_entry.get("config", {}),
    )
    await _broadcast_screen(state, transition="sweep" if len(enabled) > 1 else None)


async def _broadcast_screen(state: ScreenState, transition: str | None = None):
    if state.photo_url is not None:
        await manager.broadcast(state.screen_id, {
            "type": "photo_split",
            "image_url": state.photo_url,
            "rows": state.rows,
            "cols": state.cols,
            "screen_id": state.screen_id,
        })
    elif state.color_matrix is not None:
        await manager.broadcast(state.screen_id, {
            "type": "image_update",
            "color_matrix": state.color_matrix,
            "rows": state.rows,
            "cols": state.cols,
            "screen_id": state.screen_id,
        })
    else:
        msg = {
            "type": "display_update",
            "matrix": state.matrix,
            "rows": state.rows,
            "cols": state.cols,
            "mode": state.mode,
            "screen_id": state.screen_id,
        }
        # Per-tile text colors only apply to text content — gating by mode
        # means stale color maps can never leak into other modes
        if state.text_colors and state.mode in ("text_push", "text"):
            msg["text_colors"] = state.text_colors
        if transition:
            msg["transition"] = transition
        await manager.broadcast(state.screen_id, msg)

    if _mqtt:
        await _mqtt.publish_screen_state(state)

    await _persist_screen_state(state)


# Dedupe cache so the 1s clock tick doesn't write the DB every second
_last_persisted: dict[str, str] = {}


async def _persist_screen_state(state: ScreenState) -> None:
    """Snapshot what's on screen so a restart restores it. Clock persists as a
    bare mode marker — its matrix re-renders on boot anyway."""
    if state.mode == "clock":
        snapshot = {"mode": "clock"}
    else:
        snapshot = {
            "mode": state.mode,
            "matrix": state.matrix,
            "color_matrix": state.color_matrix,
            "photo_url": state.photo_url,
            "playlist_pos": state.playlist_pos,
        }
        if state.text_colors and state.mode in ("text_push", "text"):
            snapshot["text_colors"] = state.text_colors
    blob = json.dumps(snapshot)
    if _last_persisted.get(state.screen_id) == blob:
        return
    _last_persisted[state.screen_id] = blob
    try:
        await database.save_screen_state(state.screen_id, snapshot)
    except Exception:
        logger.debug("screen state persist failed for '%s'", state.screen_id, exc_info=True)


# ── Quiet hours ───────────────────────────────────────────────────────────────

def _parse_hhmm(value: str) -> int | None:
    try:
        h, m = value.split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return h * 60 + m
    except (ValueError, AttributeError):
        pass
    return None


def _time_in_window(now, start_hhmm: str, end_hhmm: str, days: list[int]) -> bool:
    """True when `now` (aware local datetime) is inside [start, end). `days`
    are weekdays (0=Mon) the START applies to; overnight windows (22:00 →
    06:00) spill into the next morning."""
    start = _parse_hhmm(start_hhmm)
    end = _parse_hhmm(end_hhmm)
    if start is None or end is None or start == end:
        return False
    minutes = now.hour * 60 + now.minute
    if start < end:  # same-day window
        return now.weekday() in days and start <= minutes < end
    # overnight: after start today, or before end following a start-day
    if now.weekday() in days and minutes >= start:
        return True
    return (now.weekday() - 1) % 7 in days and minutes < end


def _in_quiet_window(now, schedule: dict) -> bool:
    if not schedule.get("enabled"):
        return False
    return _time_in_window(now, schedule.get("off_time", ""), schedule.get("on_time", ""),
                           schedule.get("days") or list(range(7)))


async def _now_local():
    import pytz
    db_settings = await database.get_settings()
    try:
        tz = pytz.timezone(db_settings.get("timezone", "UTC"))
    except Exception:
        tz = pytz.utc
    return datetime.now(tz)


def _item_eligible(item: dict, now) -> bool:
    """A playlist item without a window (or with it disabled) always plays;
    a windowed item only plays inside its time window."""
    w = item.get("window") or {}
    if not w.get("enabled"):
        return True
    return _time_in_window(now, w.get("start_time", ""), w.get("end_time", ""),
                           w.get("days") or list(range(7)))


async def _sleep_screen(state: ScreenState) -> None:
    _cancel_push_timer(state)
    _stop_screen_rotation(state.screen_id)
    state.sleeping = True
    state.mode = "sleep"
    state.matrix = blank_matrix(state.rows, state.cols)
    state.color_matrix = None
    state.text_colors = None
    state.photo_url = None
    await _broadcast_screen(state)


async def _wake_screen(state: ScreenState) -> None:
    state.sleeping = False
    if state.playlist_items:
        await _render_playlist_item(state, transition="sweep")
    else:
        db_settings = await _effective_settings()
        from services.clock import get_clock_matrix
        state.mode = "clock"
        state.matrix = get_clock_matrix(
            state.rows, state.cols,
            fmt=db_settings.get("clock_format", "12h"),
            show_date=db_settings.get("show_date", "true") == "true",
            timezone=db_settings.get("timezone", "UTC"),
        )
        await _broadcast_screen(state, transition="sweep")
    _ensure_screen_rotation(state.screen_id)


async def _schedule_tick_loop():
    """Every 30s: sleep/wake screens whose quiet window boundary was crossed.
    Edge-triggered after the first pass, so manual overrides stick until the
    next scheduled boundary."""
    import pytz
    while True:
        try:
            await asyncio.sleep(30)
            db_settings = await database.get_settings()
            try:
                tz = pytz.timezone(db_settings.get("timezone", "UTC"))
            except Exception:
                tz = pytz.utc
            now = datetime.now(tz)
            for state in list(_screens.values()):
                if not state.schedule.get("enabled"):
                    state.sched_prev = None
                    continue
                in_window = _in_quiet_window(now, state.schedule)
                first_pass = state.sched_prev is None
                crossed = state.sched_prev is not None and in_window != state.sched_prev
                state.sched_prev = in_window
                if (first_pass or crossed) and in_window and not state.sleeping:
                    logger.info("quiet hours: sleeping screen '%s'", state.screen_id)
                    await _sleep_screen(state)
                elif (first_pass or crossed) and not in_window and state.sleeping:
                    logger.info("quiet hours: waking screen '%s'", state.screen_id)
                    await _wake_screen(state)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("schedule tick loop error")
            await asyncio.sleep(5)


MIN_ROTATION_SECONDS = 2


async def _rotation_loop(screen_id: str):
    """Per-screen loop — respects per-item durations when a playlist is active.

    Must never die: a transient failure (DB lock, renderer bug) pauses one
    iteration, not the display, so a 24/7 board keeps rotating.
    """
    while True:
        try:
            state = _screens[screen_id]
            db_settings = await _effective_settings()
            default_interval = int(db_settings.get("rotation_interval", 30))

            if state.playlist_items:
                item = state.playlist_items[state.playlist_pos]
                duration = item.get("duration") or default_interval
            else:
                duration = default_interval

            await asyncio.sleep(max(MIN_ROTATION_SECONDS, duration))
            await advance_screen_mode(screen_id)
        except asyncio.CancelledError:
            raise
        except KeyError:
            return  # screen deleted
        except Exception:
            logger.exception("rotation loop error for screen '%s'", screen_id)
            await asyncio.sleep(5)


async def _clock_tick_loop():
    """Global 1-second tick — live-updates clock and countdown screens."""
    while True:
        try:
            await asyncio.sleep(1)
            db_settings = await _effective_settings()
            for sid, state in list(_screens.items()):
                if state.mode == "clock":
                    from services.clock import get_clock_matrix
                    state.matrix = get_clock_matrix(
                        state.rows, state.cols,
                        fmt=db_settings.get("clock_format", "12h"),
                        show_date=db_settings.get("show_date", "true") == "true",
                        timezone=db_settings.get("timezone", "UTC"),
                    )
                    state.color_matrix = None
                    state.photo_url = None
                    await _broadcast_screen(state)
                elif state.mode == "countdown":
                    # Re-render each second so the seconds digits flip live
                    mode_entries = await database.get_modes(sid)
                    entry = next((m for m in mode_entries if m["mode"] == "countdown"), None)
                    state.matrix = await _render_mode(
                        "countdown", state.rows, state.cols, db_settings,
                        screen_id=sid, mode_config=entry.get("config", {}) if entry else {})
                    state.color_matrix = None
                    state.photo_url = None
                    await _broadcast_screen(state)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("clock tick loop error")
            await asyncio.sleep(5)


def _start_screen_rotation(screen_id: str):
    task = asyncio.create_task(_rotation_loop(screen_id))
    _screens[screen_id].rotation_task = task
    return task


def _stop_screen_rotation(screen_id: str):
    state = _screens.get(screen_id)
    if state and state.rotation_task:
        _cancel_task(state.rotation_task)
        state.rotation_task = None


def _restart_all_rotations():
    for sid in list(_screens.keys()):
        _stop_screen_rotation(sid)
        _start_screen_rotation(sid)


# ── Lifespan ──────────────────────────────────────────────────────────────────

_clock_task: asyncio.Task | None = None
_sched_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _clock_task

    # Load plugins before DB init so they can register tables via on_db_init
    loaded_plugins = plugin_registry.load(settings.plugins)
    await database.init_db()

    _boot_settings = await database.get_settings()
    _auth_state["enabled"] = (_boot_settings.get("auth_enabled") == "true"
                              and bool(_boot_settings.get("auth_password_hash")))

    # Register built-in modes first, then plugin modes
    _register_builtin_modes()
    await plugin_registry.startup(app, loaded_plugins)

    db_settings = await _effective_settings()
    screens = await database.get_screens()

    from services.clock import get_clock_matrix

    _restored_push_screens: set[str] = set()

    for screen in screens:
        sid = screen["id"]
        state = ScreenState(sid, screen["name"], screen["rows"], screen["cols"])
        state.schedule = screen.get("schedule") or {}

        items = await database.get_playlist_items(sid)
        state.playlist_items = items
        saved = await database.load_screen_state(sid)

        if items:
            # Resume the playlist where it left off (rendered after tasks start)
            state.playlist_pos = min(saved.get("playlist_pos", 0), len(items) - 1) \
                if saved else 0
            state.mode = "playlist"
        elif saved and saved.get("mode") not in (None, "clock"):
            # Restore pushed content; treat it as "until changed" — the user
            # can advance manually, rather than losing the push to a reboot
            state.mode = saved["mode"]
            state.photo_url = saved.get("photo_url")
            state.color_matrix = saved.get("color_matrix")
            state.text_colors = saved.get("text_colors")
            if saved.get("matrix"):
                state.matrix = _normalize_matrix(saved["matrix"], state.rows, state.cols)
            _restored_push_screens.add(sid)
        else:
            state.matrix = get_clock_matrix(
                screen["rows"], screen["cols"],
                fmt=db_settings.get("clock_format", "12h"),
                show_date=db_settings.get("show_date", "true") == "true",
                timezone=db_settings.get("timezone", "UTC"),
            )

        _screens[sid] = state

    for sid in _screens:
        if sid not in _restored_push_screens:
            _start_screen_rotation(sid)

    # Render initial playlist item for screens that have one
    for sid, state in _screens.items():
        if state.playlist_items:
            await _render_playlist_item(state)

    _clock_task = asyncio.create_task(_clock_tick_loop())
    global _sched_task
    _sched_task = asyncio.create_task(_schedule_tick_loop())

    global _mqtt
    from mqtt_bridge import MQTTBridge
    _mqtt = MQTTBridge(dispatch=_mqtt_dispatch,
                       screens_provider=lambda: _screens,
                       modes_provider=mode_registry.all_modes)
    await _mqtt.start()

    yield

    await _mqtt.stop()
    _mqtt = None

    # Cancel AND await every background task (including previously cancelled
    # ones in _dying_tasks) so their async-with cleanup runs before the loop
    # closes — otherwise aiosqlite worker threads stay alive and block exit.
    pending: list[asyncio.Task] = [_clock_task]
    _clock_task.cancel()
    if _sched_task:
        _sched_task.cancel()
        pending.append(_sched_task)
    for state in _screens.values():
        for task in (state.rotation_task, state.push_timer):
            if task and not task.done():
                task.cancel()
                pending.append(task)
        state.rotation_task = None
        state.push_timer = None
    pending.extend(_dying_tasks)
    await asyncio.gather(*pending, return_exceptions=True)
    _dying_tasks.clear()
    _screens.clear()
    _last_persisted.clear()

    await plugin_registry.shutdown()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="FlipperBoards", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    """When auth is enabled, every mutating API call requires a session.
    Reads and the WebSocket stay open so displays keep working unauthenticated."""
    if (_auth_state["enabled"]
            and request.method in ("POST", "PUT", "DELETE", "PATCH")
            and request.url.path.startswith("/api/")
            and not request.url.path.startswith("/api/auth/")):
        if not await _request_authenticated(request):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
    return await call_next(request)


# ── Auth endpoints ────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    password: str


class AuthConfigure(BaseModel):
    enabled: bool
    password: str | None = Field(default=None, min_length=4, max_length=128)


@app.get("/api/auth/status")
async def auth_status(request: Request):
    enabled = _auth_state["enabled"]
    return {
        "enabled": enabled,
        "authenticated": (not enabled) or await _request_authenticated(request),
    }


@app.post("/api/auth/login")
async def auth_login(body: LoginBody, response: Response):
    if not _auth_state["enabled"]:
        return {"status": "ok", "note": "authentication is disabled"}
    db_settings = await database.get_settings()
    if not _verify_password(body.password, db_settings.get("auth_password_hash", "")):
        # Small constant delay blunts brute-force attempts from the LAN
        await asyncio.sleep(0.5)
        raise HTTPException(401, "Wrong password")
    await _issue_session(response)
    return {"status": "ok"}


@app.post("/api/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get(AUTH_COOKIE)
    if token:
        await database.remove_session(token)
    response.delete_cookie(AUTH_COOKIE)
    return {"status": "ok"}


@app.post("/api/auth/configure")
async def auth_configure(body: AuthConfigure, request: Request, response: Response):
    """Enable/disable auth or change the password. Once auth is on, changing
    it requires a logged-in session (the middleware exempts /api/auth/*)."""
    if _auth_state["enabled"] and not await _request_authenticated(request):
        raise HTTPException(401, "Authentication required")

    if body.enabled:
        db_settings = await database.get_settings()
        if body.password:
            await database.update_setting("auth_password_hash", _hash_password(body.password))
            await database.clear_sessions()  # password change logs everyone out
        elif not db_settings.get("auth_password_hash"):
            raise HTTPException(400, "A password is required to enable authentication")
        await database.update_setting("auth_enabled", "true")
        _auth_state["enabled"] = True
        await _issue_session(response)  # keep the enabling client logged in
    else:
        await database.update_setting("auth_enabled", "false")
        await database.clear_sessions()
        _auth_state["enabled"] = False

    return {"status": "ok", "enabled": _auth_state["enabled"]}


# ── Pydantic models ───────────────────────────────────────────────────────────

class DisplayContent(BaseModel):
    text: str
    duration: int | None = Field(default=None, ge=1)  # None = until manually changed

class MatrixContent(BaseModel):
    matrix: list[list[int]]
    duration: int | None = Field(default=None, ge=1)

class ColorMatrixContent(BaseModel):
    color_matrix: list[list[str]]
    duration: int | None = Field(default=None, ge=1)

class SettingsUpdate(BaseModel):
    rotation_interval: int | None = Field(default=None, ge=MIN_ROTATION_SECONDS, le=86400)
    tile_color: str | None = None
    bg_color: str | None = None
    tile_bg_color: str | None = None
    timezone: str | None = None
    clock_format: str | None = None
    show_date: bool | None = None
    weather_location: str | None = None
    weather_units: str | None = None
    weather_api_key: str | None = None
    news_api_key: str | None = None
    news_categories: list[str] | None = None
    news_sources: list[str] | None = None
    calendar_ical_url: str | None = None
    sound_enabled: bool | None = None
    divider_width: int | None = None
    divider_color: str | None = None
    physical_mode: bool | None = None
    flip_duration: int | None = None
    mqtt_enabled: bool | None = None
    mqtt_host: str | None = None
    mqtt_port: int | None = None
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_base_topic: str | None = None
    mqtt_ha_discovery: bool | None = None

class ModeContent(BaseModel):
    mode: str
    duration: int | None = Field(default=None, ge=1)

class PlaylistJump(BaseModel):
    pos: int

class ImageUpdate(BaseModel):
    name: str | None = None
    folder: str | None = None


class ScreenCreate(BaseModel):
    id: str
    name: str
    rows: int = Field(default_factory=lambda: settings.default_rows, ge=1, le=16)
    cols: int = Field(default_factory=lambda: settings.default_cols, ge=1, le=48)

class ScheduleConfig(BaseModel):
    enabled: bool = False
    off_time: str = "22:00"    # display sleeps at this local time…
    on_time: str = "08:00"     # …and wakes at this one (overnight OK)
    days: list[int] = Field(default_factory=lambda: list(range(7)))  # 0=Mon

    @field_validator("off_time", "on_time")
    @classmethod
    def _valid_time(cls, v):
        if _parse_hhmm(v) is None:
            raise ValueError("must be HH:MM (24h)")
        return v

    @field_validator("days")
    @classmethod
    def _valid_days(cls, v):
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("days must be 0-6 (Monday=0)")
        return sorted(set(v))


class ScreenUpdate(BaseModel):
    name: str
    rows: int = Field(ge=1, le=16)
    cols: int = Field(ge=1, le=48)
    schedule: ScheduleConfig | None = None


class SleepBody(BaseModel):
    sleeping: bool

class ModeUpdate(BaseModel):
    mode: str
    enabled: bool
    sort_order: int
    config: dict | None = {}

class TextMessage(BaseModel):
    text: str
    duration: int = 30

class PlaylistWindow(BaseModel):
    """Optional dayparting: the item only plays inside this time window."""
    enabled: bool = False
    start_time: str = "11:00"
    end_time: str = "22:00"
    days: list[int] = Field(default_factory=lambda: list(range(7)))  # 0=Mon

    @field_validator("start_time", "end_time")
    @classmethod
    def _valid_time(cls, v):
        if _parse_hhmm(v) is None:
            raise ValueError("must be HH:MM (24h)")
        return v

    @field_validator("days")
    @classmethod
    def _valid_days(cls, v):
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("days must be 0-6 (Monday=0)")
        return sorted(set(v))


class PlaylistItemCreate(BaseModel):
    type: str              # 'mode', 'text', 'photo', 'color', 'matrix', 'scoreboard', 'menu'
    content: dict          # varies by type
    duration: int = Field(default=30, ge=1, le=86400)
    window: PlaylistWindow | None = None

class PlaylistItemUpdate(BaseModel):
    type: str
    content: dict
    duration: int = Field(ge=1, le=86400)
    window: PlaylistWindow | None = None

class PlaylistReorder(BaseModel):
    ids: list[int]

class DesignCreate(BaseModel):
    name: str
    matrix: list[list[int]]

class DesignUpdate(BaseModel):
    name: str
    matrix: list[list[int]]

class DesignQueueAdd(BaseModel):
    duration: int = 30


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_screen_id(sid: str) -> bool:
    return bool(re.match(r'^[a-z0-9_-]{1,64}$', sid))


ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _save_upload(file_bytes: bytes, original_filename: str) -> str:
    """Write bytes to UPLOAD_DIR and return the bare filename (no path prefix)."""
    ext = os.path.splitext(original_filename or "image.jpg")[1].lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(file_bytes)
    return filename


async def _register_upload(file_bytes: bytes, original_filename: str,
                            name: str = '', folder: str = '') -> dict:
    """Save to disk, record in image_library, return {id, url, name, folder}."""
    ext = os.path.splitext(original_filename or "image.jpg")[1].lower() or ".jpg"
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(415, f"Unsupported file type '{ext}' — use jpg/png/gif/webp")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_BYTES // (1024*1024)} MB)")
    filename = await anyio.to_thread.run_sync(_save_upload, file_bytes, original_filename)
    ct = mimetypes.guess_type(original_filename)[0] or 'image/jpeg'
    img_id = await database.add_image(
        filename=filename,
        name=name.strip(),
        folder=folder.strip(),
        size=len(file_bytes),
        content_type=ct,
    )
    return {'id': img_id, 'url': f'/api/uploads/{img_id}/image',
            'name': name.strip(), 'folder': folder.strip()}


# ── Screen management ─────────────────────────────────────────────────────────

@app.get("/api/screens")
async def list_screens():
    screens = await database.get_screens()
    result = []
    for s in screens:
        state = _screens.get(s["id"])
        result.append({
            **s,
            "mode": state.mode if state else "unknown",
            "online": state is not None,
            "sleeping": state.sleeping if state else False,
        })
    return result


@app.post("/api/screens", status_code=201)
async def create_screen(body: ScreenCreate):
    if not _valid_screen_id(body.id):
        raise HTTPException(400, "Screen ID must be lowercase alphanumeric, hyphens, underscores, max 64 chars")
    if body.id in _screens:
        raise HTTPException(409, f"Screen '{body.id}' already exists")

    await database.create_screen(body.id, body.name, body.rows, body.cols)

    db_settings = await _effective_settings()
    from services.clock import get_clock_matrix
    state = ScreenState(body.id, body.name, body.rows, body.cols)
    state.matrix = get_clock_matrix(body.rows, body.cols,
        fmt=db_settings.get("clock_format", "12h"),
        show_date=db_settings.get("show_date", "true") == "true",
        timezone=db_settings.get("timezone", "UTC"),
    )
    _screens[body.id] = state
    _start_screen_rotation(body.id)

    await manager.broadcast_all({"type": "screens_update", "screens": await _screens_payload()})
    if _mqtt:
        await _mqtt.refresh_discovery()
    return {"status": "created", "id": body.id}


@app.put("/api/screens/{screen_id}")
async def update_screen(screen_id: str, body: ScreenUpdate):
    if screen_id not in _screens:
        raise HTTPException(404, f"Screen '{screen_id}' not found")

    schedule = body.schedule.model_dump() if body.schedule is not None else None
    await database.update_screen(screen_id, body.name, body.rows, body.cols, schedule=schedule)
    state = _screens[screen_id]
    state.name = body.name
    if schedule is not None:
        state.schedule = schedule
        state.sched_prev = None  # re-evaluate on the next scheduler tick
    if state.rows != body.rows or state.cols != body.cols:
        state.rows = body.rows
        state.cols = body.cols
        # Old-dimension content is invalid at the new size — clear and re-render
        state.color_matrix = None
        state.photo_url = None
        state.matrix = blank_matrix(body.rows, body.cols)
        if state.playlist_items:
            await _render_playlist_item(state)
        else:
            await _broadcast_screen(state)

    await manager.broadcast_all({"type": "screens_update", "screens": await _screens_payload()})
    if _mqtt:
        await _mqtt.refresh_discovery()
    return {"status": "updated"}


@app.delete("/api/screens/{screen_id}")
async def delete_screen(screen_id: str):
    if screen_id == "main":
        raise HTTPException(400, "Cannot delete the main screen")
    if screen_id not in _screens:
        raise HTTPException(404)
    _stop_screen_rotation(screen_id)
    del _screens[screen_id]
    await database.delete_screen(screen_id)
    await database.delete_screen_state(screen_id)
    _last_persisted.pop(screen_id, None)
    await manager.broadcast_all({"type": "screens_update", "screens": await _screens_payload()})
    if _mqtt:
        await _mqtt.remove_screen_discovery(screen_id)
    return {"status": "deleted"}


@app.post("/api/screens/{screen_id}/sleep")
async def set_screen_sleep(screen_id: str, body: SleepBody):
    """Manual sleep/wake — holds until the next scheduled quiet-hours boundary."""
    state = get_screen_state(screen_id)
    if body.sleeping and not state.sleeping:
        await _sleep_screen(state)
    elif not body.sleeping and state.sleeping:
        await _wake_screen(state)
    return {"status": "ok", "sleeping": state.sleeping}


async def _screens_payload():
    screens = await database.get_screens()
    return [
        {**s, "mode": _screens[s["id"]].mode if s["id"] in _screens else "unknown",
         "online": s["id"] in _screens,
         "sleeping": _screens[s["id"]].sleeping if s["id"] in _screens else False}
        for s in screens
    ]


def _normalize_matrix(matrix, rows: int, cols: int) -> list[list[int]]:
    """Fit a client-supplied matrix to the screen: pad/truncate to rows×cols,
    clamp every cell to a valid tile code (0-77). Never trust the input shape —
    a push must not be able to change the screen's configured dimensions."""
    if not isinstance(matrix, list) or not matrix:
        raise HTTPException(400, "Matrix must be a non-empty list of rows")
    result = []
    for r in range(rows):
        src = matrix[r] if r < len(matrix) and isinstance(matrix[r], list) else []
        row = []
        for c in range(cols):
            try:
                v = int(src[c]) if c < len(src) else 0
            except (TypeError, ValueError):
                v = 0
            row.append(v if 0 <= v <= 77 else 0)
        result.append(row)
    return result


# Every cancelled task must eventually be awaited: a task cancelled mid-DB-call
# whose cancellation never gets processed before loop close strands a live
# (non-daemon) aiosqlite worker thread and blocks interpreter exit.
_dying_tasks: set[asyncio.Task] = set()


def _cancel_task(task: asyncio.Task | None) -> None:
    if task and not task.done():
        task.cancel()
        _dying_tasks.add(task)
        task.add_done_callback(_dying_tasks.discard)


def _cancel_push_timer(state: ScreenState) -> None:
    _cancel_task(state.push_timer)
    state.push_timer = None


def _ensure_screen_rotation(screen_id: str) -> None:
    state = _screens.get(screen_id)
    if state and (state.rotation_task is None or state.rotation_task.done()):
        _start_screen_rotation(screen_id)


def _schedule_revert(state: ScreenState, screen_id: str, duration: int | None) -> None:
    """Coordinate pushed content with the rotation loop.

    Rotation is paused while a push is showing so it can't preempt the pushed
    content. With a duration, a revert timer advances and resumes rotation;
    with None ("until changed"), rotation stays paused until the user acts.
    """
    state.sleeping = False  # pushing content to a sleeping board wakes it
    _cancel_push_timer(state)
    _stop_screen_rotation(screen_id)
    if duration is not None and duration > 0:
        async def _revert():
            try:
                await asyncio.sleep(duration)
                state.push_timer = None
                await advance_screen_mode(screen_id)
                _ensure_screen_rotation(screen_id)
            except asyncio.CancelledError:
                pass
        state.push_timer = asyncio.create_task(_revert())


# ── Display control (immediate push) ─────────────────────────────────────────

@app.get("/api/state")
async def get_state(screen: str = Query(default="main")):
    state = get_screen_state(screen)
    return {
        "screen_id": state.screen_id,
        "name": state.name,
        "matrix": state.matrix,
        "rows": state.rows,
        "cols": state.cols,
        "mode": state.mode,
        "photo_url": state.photo_url,
        "playlist_active": bool(state.playlist_items),
        "playlist_pos": state.playlist_pos,
        "text_colors": state.text_colors if state.mode in ("text_push", "text") else None,
    }


@app.post("/api/display/text")
async def push_text(content: DisplayContent, screen: str = Query(default="main")):
    state = get_screen_state(screen)
    state.matrix, state.text_colors = text_to_matrix_colored(
        content.text, state.rows, state.cols)
    state.color_matrix = None
    state.photo_url = None
    state.mode = "text_push"
    _schedule_revert(state, screen, content.duration)
    await _broadcast_screen(state)
    return {"status": "ok", "screen": screen}


@app.post("/api/display/matrix")
async def push_matrix(content: MatrixContent, screen: str = Query(default="main")):
    state = get_screen_state(screen)
    state.matrix = _normalize_matrix(content.matrix, state.rows, state.cols)
    state.color_matrix = None
    state.text_colors = None
    state.photo_url = None
    state.mode = "matrix_push"
    _schedule_revert(state, screen, content.duration)
    await _broadcast_screen(state)
    return {"status": "ok", "screen": screen}


@app.post("/api/display/color-matrix")
async def push_color_matrix(content: ColorMatrixContent, screen: str = Query(default="main")):
    if not content.color_matrix:
        raise HTTPException(400, "Empty color matrix")
    state = get_screen_state(screen)
    # Pad/truncate to the screen's configured dimensions — never resize the screen
    state.color_matrix = [
        [(content.color_matrix[r][c]
          if r < len(content.color_matrix) and c < len(content.color_matrix[r])
          else "#1a1a1a")
         for c in range(state.cols)]
        for r in range(state.rows)
    ]
    state.photo_url = None
    state.mode = "image_push"
    _schedule_revert(state, screen, content.duration)
    await _broadcast_screen(state)
    return {"status": "ok", "screen": screen}


@app.post("/api/display/photo")
async def push_photo(
    file: UploadFile = File(...),
    name: str = Form(default=''),
    folder: str = Form(default=''),
    duration: int | None = Form(default=None),
    screen: str = Query(default="main"),
):
    state = get_screen_state(screen)
    content = await file.read()
    img = await _register_upload(content, file.filename or "photo.jpg", name=name, folder=folder)
    state.photo_url = img['url']
    state.color_matrix = None
    state.mode = "photo_push"
    _schedule_revert(state, screen, duration)
    await _broadcast_screen(state)
    return {"status": "ok", "screen": screen, **img}


@app.post("/api/display/photo/push/{image_id}")
async def push_library_photo(image_id: int, screen: str = Query(default="main"), duration: int | None = Query(default=None)):
    """Push an already-uploaded library image to the display without re-uploading."""
    img = await database.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    path = os.path.join(UPLOAD_DIR, img['filename'])
    if not os.path.isfile(path):
        raise HTTPException(404, "File not found on disk")
    state = get_screen_state(screen)
    state.photo_url = f"/api/uploads/{image_id}/image"
    state.color_matrix = None
    state.mode = "photo_push"
    _schedule_revert(state, screen, duration)
    await _broadcast_screen(state)
    return {"status": "ok", "image_url": state.photo_url}


@app.post("/api/display/blank")
async def blank_display(screen: str = Query(default="main")):
    state = get_screen_state(screen)
    state.matrix = blank_matrix(state.rows, state.cols)
    state.color_matrix = None
    state.text_colors = None
    state.photo_url = None
    state.mode = "blank"
    # Blank behaves like a push with no duration: rotation pauses so the
    # board stays blank until the user advances or plays something.
    _schedule_revert(state, screen, None)
    await _broadcast_screen(state)
    return {"status": "ok"}


@app.post("/api/display/next")
async def next_mode(screen: str = Query(default="main")):
    if screen not in _screens:
        raise HTTPException(404)
    await advance_screen_mode(screen)
    _ensure_screen_rotation(screen)
    return {"status": "ok", "mode": _screens[screen].mode}


@app.post("/api/display/mode")
async def push_mode(content: ModeContent, screen: str = Query(default="main")):
    """Switch the display to a specific mode immediately."""
    state = get_screen_state(screen)
    mode = content.mode.strip().lower()
    if mode_registry.get(mode) is None:
        raise HTTPException(400, f"Unknown mode '{mode}'")
    db_settings = await _effective_settings()
    mode_entries = await database.get_modes(screen)
    mode_entry = next((m for m in mode_entries if m["mode"] == mode), None)
    mode_config = mode_entry.get("config", {}) if mode_entry else {}
    state.mode = mode
    state.color_matrix = None
    state.text_colors = None
    state.photo_url = None
    state.matrix = await _render_mode(mode, state.rows, state.cols, db_settings,
                                      screen_id=screen, mode_config=mode_config)
    _schedule_revert(state, screen, content.duration)
    await _broadcast_screen(state)
    return {"status": "ok", "mode": mode}


# ── File upload / image library ────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    name: str = Form(default=''),
    folder: str = Form(default=''),
):
    """Save an uploaded file, register in image library, return id + url."""
    content = await file.read()
    img = await _register_upload(content, file.filename or "image.jpg", name=name, folder=folder)
    return img


@app.get("/api/uploads")
async def list_uploads():
    images = await database.get_images()
    return [
        {'id': img['id'], 'name': img['name'], 'folder': img['folder'],
         'size': img['size'], 'created_at': img['created_at'],
         'url': f'/api/uploads/{img["id"]}/image'}
        for img in images
    ]


@app.get("/api/uploads/{image_id}/image")
async def serve_upload(image_id: int):
    img = await database.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    path = os.path.join(UPLOAD_DIR, img['filename'])
    if not os.path.isfile(path):
        raise HTTPException(404, "File not found on disk")
    return FileResponse(path, media_type=img['content_type'])


@app.patch("/api/uploads/{image_id}")
async def update_upload_meta(image_id: int, body: ImageUpdate):
    img = await database.get_image(image_id)
    if not img:
        raise HTTPException(404, "Image not found")
    await database.update_image(image_id, name=body.name, folder=body.folder)
    return {"status": "ok"}


@app.delete("/api/uploads/{image_id}")
async def delete_upload(image_id: int):
    filename = await database.delete_image(image_id)
    if filename is None:
        raise HTTPException(404, "Image not found")
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.isfile(path):
        os.remove(path)
    # Remove playlist items that reference this image so queue entries don't 404
    await database.remove_playlist_items_by_image_url(f"/api/uploads/{image_id}/image")
    return {"status": "deleted"}


# ── Universal content playlist ────────────────────────────────────────────────

@app.get("/api/playlist")
async def get_playlist(screen: str = Query(default="main")):
    return await database.get_playlist_items(screen)


@app.post("/api/playlist", status_code=201)
async def add_playlist_item(body: PlaylistItemCreate, screen: str = Query(default="main")):
    state = get_screen_state(screen)
    item_id = await database.add_playlist_item(
        screen, body.type, body.content, body.duration,
        window=body.window.model_dump() if body.window else None)
    state.playlist_items = await database.get_playlist_items(screen)
    return {"status": "created", "id": item_id}


def _screen_playlist_item(state: ScreenState, item_id: int) -> dict:
    """404 unless the item belongs to this screen's playlist — item ids are
    global autoincrement, so without this check one screen can mutate another's."""
    item = next((i for i in state.playlist_items if i["id"] == item_id), None)
    if item is None:
        raise HTTPException(404, f"Playlist item {item_id} not found on screen '{state.screen_id}'")
    return item


@app.put("/api/playlist/{item_id}")
async def update_playlist_item(item_id: int, body: PlaylistItemUpdate, screen: str = Query(default="main")):
    state = get_screen_state(screen)
    state.playlist_items = await database.get_playlist_items(screen)
    _screen_playlist_item(state, item_id)
    await database.update_playlist_item(
        item_id, body.type, body.content, body.duration,
        window=body.window.model_dump() if body.window else None)
    state.playlist_items = await database.get_playlist_items(screen)
    # Live-update: if the edited item is on screen now, re-render in place.
    # No transition — only tiles whose character changed will flip.
    if state.playlist_items:
        cur = state.playlist_items[state.playlist_pos % len(state.playlist_items)]
        if cur["id"] == item_id:
            await _render_playlist_item(state)
    return {"status": "updated"}


@app.delete("/api/playlist/{item_id}")
async def remove_playlist_item(item_id: int, screen: str = Query(default="main")):
    state = get_screen_state(screen)
    state.playlist_items = await database.get_playlist_items(screen)
    _screen_playlist_item(state, item_id)
    was_current = (state.playlist_items
                   and state.playlist_items[state.playlist_pos % len(state.playlist_items)]["id"] == item_id)
    await database.remove_playlist_item(item_id)
    state.playlist_items = await database.get_playlist_items(screen)
    if state.playlist_items:
        state.playlist_pos = min(state.playlist_pos, len(state.playlist_items) - 1)
        if was_current:
            await _render_playlist_item(state)
    else:
        state.playlist_pos = 0
    return {"status": "deleted"}


@app.post("/api/playlist/reorder")
async def reorder_playlist(body: PlaylistReorder, screen: str = Query(default="main")):
    state = get_screen_state(screen)
    await database.reorder_playlist_items(screen, body.ids)
    state.playlist_items = await database.get_playlist_items(screen)
    return {"status": "ok"}


@app.post("/api/playlist/clear")
async def clear_playlist(screen: str = Query(default="main")):
    state = get_screen_state(screen)
    await database.clear_playlist_items(screen)
    state.playlist_items = []
    state.playlist_pos = 0
    return {"status": "ok"}


@app.post("/api/playlist/play")
async def play_playlist(screen: str = Query(default="main")):
    """Jump to the start of the playlist and restart the rotation timer."""
    state = get_screen_state(screen)
    state.playlist_items = await database.get_playlist_items(screen)
    if not state.playlist_items:
        raise HTTPException(400, "Playlist is empty")
    state.playlist_pos = 0
    _cancel_push_timer(state)
    await _render_playlist_item(state, transition="sweep")
    # Restart rotation so timer starts fresh from now
    _stop_screen_rotation(screen)
    _start_screen_rotation(screen)
    return {"status": "ok", "screen": screen}


@app.post("/api/playlist/jump")
async def jump_playlist(body: PlaylistJump, screen: str = Query(default="main")):
    """Jump to a specific playlist position and restart the rotation timer."""
    state = get_screen_state(screen)
    state.playlist_items = await database.get_playlist_items(screen)
    if not state.playlist_items:
        raise HTTPException(400, "Playlist is empty")
    if not 0 <= body.pos < len(state.playlist_items):
        raise HTTPException(400, f"pos must be 0..{len(state.playlist_items) - 1}")
    state.playlist_pos = body.pos
    _cancel_push_timer(state)
    await _render_playlist_item(state, transition="sweep")
    _stop_screen_rotation(screen)
    _start_screen_rotation(screen)
    return {"status": "ok", "screen": screen, "pos": body.pos}


# ── Screen designs ────────────────────────────────────────────────────────────

@app.get("/api/designs")
async def list_designs(screen: str = Query(default="main")):
    return await database.get_designs(screen)


@app.post("/api/designs", status_code=201)
async def create_design(body: DesignCreate, screen: str = Query(default="main")):
    design_id = await database.add_design(screen, body.name, body.matrix)
    return {"id": design_id, "name": body.name}


@app.put("/api/designs/{design_id}")
async def update_design(design_id: int, body: DesignUpdate):
    await database.update_design(design_id, body.name, body.matrix)
    return {"status": "ok"}


@app.delete("/api/designs/{design_id}")
async def delete_design(design_id: int):
    await database.delete_design(design_id)
    return {"status": "ok"}


@app.post("/api/designs/{design_id}/push")
async def push_design(design_id: int, screen: str = Query(default="main"),
                      duration: int | None = Query(default=None)):
    design = await database.get_design(design_id)
    if not design:
        raise HTTPException(404, "Design not found")
    state = get_screen_state(screen)
    state.matrix = _normalize_matrix(design["matrix"], state.rows, state.cols)
    state.color_matrix = None
    state.text_colors = None
    state.photo_url = None
    state.mode = "matrix_push"
    _schedule_revert(state, screen, duration)
    await _broadcast_screen(state)
    return {"status": "ok"}


@app.post("/api/designs/{design_id}/queue")
async def queue_design(design_id: int, body: DesignQueueAdd, screen: str = Query(default="main")):
    design = await database.get_design(design_id)
    if not design:
        raise HTTPException(404, "Design not found")
    state = get_screen_state(screen)
    item_id = await database.add_playlist_item(
        screen, "matrix", {"matrix": design["matrix"], "name": design["name"]}, body.duration
    )
    state.playlist_items = await database.get_playlist_items(screen)
    return {"status": "ok", "item_id": item_id}


# ── Global settings ───────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    return _public_settings(await database.get_settings())


@app.put("/api/settings")
async def update_settings(body: SettingsUpdate):
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        if isinstance(value, bool):
            await database.update_setting(key, "true" if value else "false")
        elif isinstance(value, list):
            await database.update_setting(key, json.dumps(value))
        else:
            await database.update_setting(key, str(value))

    if "rotation_interval" in updates:
        _restart_all_rotations()

    if _mqtt and any(k.startswith("mqtt_") for k in updates):
        await _mqtt.restart()

    new_settings = _public_settings(await database.get_settings())
    await manager.broadcast_all({"type": "settings_update", "settings": new_settings})
    return new_settings


# ── Per-screen modes ──────────────────────────────────────────────────────────

@app.get("/api/modes/available")
async def list_available_modes():
    """Full mode catalog — built-in + all plugin modes."""
    return mode_registry.all_modes()


def _merge_modes(db_modes: list[dict]) -> list[dict]:
    """Merge per-screen DB state with the full mode catalog.

    Modes registered by plugins that aren't yet in the DB appear as disabled.
    Each entry includes label/icon/description from the registry.
    """
    db_by_id = {m["mode"]: m for m in db_modes}
    result = []
    for i, reg in enumerate(mode_registry.all_modes()):
        db_state = db_by_id.get(reg["id"])
        result.append({
            "mode": reg["id"],
            "label": reg["label"],
            "icon": reg["icon"],
            "description": reg["description"],
            "config_schema": reg["config_schema"],
            "enabled": db_state["enabled"] if db_state else False,
            "sort_order": db_state["sort_order"] if db_state else 1000 + i,
            "config": db_state["config"] if db_state else {},
        })
    result.sort(key=lambda m: m["sort_order"])
    return result


@app.get("/api/modes")
async def get_modes(screen: str = Query(default="main")):
    db_modes = await database.get_modes(screen)
    return _merge_modes(db_modes)


@app.put("/api/modes/{mode}")
async def update_mode(mode: str, body: ModeUpdate, screen: str = Query(default="main")):
    await database.update_mode(screen, mode, body.enabled, body.sort_order, body.config or {})
    db_modes = await database.get_modes(screen)
    await manager.broadcast(screen, {"type": "modes_update", "modes": _merge_modes(db_modes)})
    return {"status": "ok"}


# ── Per-screen text messages ──────────────────────────────────────────────────

@app.get("/api/messages")
async def get_messages(screen: str = Query(default="main")):
    return await database.get_text_messages(screen)


@app.post("/api/messages")
async def add_message(msg: TextMessage, screen: str = Query(default="main")):
    msg_id = await database.add_text_message(screen, msg.text, msg.duration)
    return {"id": msg_id, "text": msg.text, "duration": msg.duration}


@app.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: int):
    await database.delete_text_message(msg_id)
    return {"status": "ok"}


# ── WebSocket (per-screen) ────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, screen: str = Query(default="main")):
    await manager.connect(ws, screen)

    state = _screens.get(screen)
    db_settings = await _effective_settings()
    screens_list = await _screens_payload()

    initial_msgs = [
        {"type": "settings_update", "settings": _public_settings(db_settings)},
        {"type": "screens_update", "screens": screens_list},
        {"type": "modes_update", "modes": _merge_modes(await database.get_modes(screen))},
    ]
    if state:
        if state.photo_url is not None:
            initial_msgs.insert(0, {
                "type": "photo_split",
                "image_url": state.photo_url,
                "rows": state.rows,
                "cols": state.cols,
                "screen_id": screen,
            })
        elif state.color_matrix is not None:
            initial_msgs.insert(0, {
                "type": "image_update",
                "color_matrix": state.color_matrix,
                "rows": state.rows,
                "cols": state.cols,
                "screen_id": screen,
            })
        else:
            initial = {
                "type": "display_update",
                "matrix": state.matrix,
                "rows": state.rows,
                "cols": state.cols,
                "mode": state.mode,
                "screen_id": screen,
            }
            if state.text_colors and state.mode in ("text_push", "text"):
                initial["text_colors"] = state.text_colors
            initial_msgs.insert(0, initial)

    import json as _json
    for msg in initial_msgs:
        try:
            await ws.send_text(_json.dumps(msg))
        except Exception:
            break

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("websocket receive error on screen '%s'", screen, exc_info=True)
    finally:
        manager.disconnect(ws, screen)


# ── MQTT command dispatch ─────────────────────────────────────────────────────
# Maps MQTT command topics onto the same handlers the REST API uses.

def _mqtt_json(payload: str) -> dict | None:
    try:
        data = json.loads(payload)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


async def _mqtt_dispatch(screen_id: str, command: str, arg: str | None, payload: str):
    if screen_id not in _screens:
        logger.warning(f"MQTT: unknown screen '{screen_id}'")
        return
    state = _screens[screen_id]
    data = _mqtt_json(payload)

    try:
        if command == "text":
            text = data.get("text", "") if data else payload
            duration = data.get("duration") if data else None
            await push_text(DisplayContent(text=text, duration=duration), screen=screen_id)
            if _mqtt:
                await _mqtt.publish_screen_state(state, text=text)

        elif command == "matrix":
            if not data or "matrix" not in data:
                return
            await push_matrix(MatrixContent(matrix=data["matrix"],
                                            duration=data.get("duration")), screen=screen_id)

        elif command == "design":
            ref = data.get("design") if data else payload
            duration = data.get("duration") if data else None
            designs = await database.get_designs(screen_id)
            design = next(
                (d for d in designs
                 if str(d["id"]) == str(ref) or d["name"].lower() == str(ref).lower()),
                None)
            if design:
                await push_design(design["id"], screen=screen_id, duration=duration)
            else:
                logger.warning(f"MQTT: design '{ref}' not found")

        elif command == "image":
            ref = data.get("image") if data else payload
            duration = data.get("duration") if data else None
            images = await database.get_images()
            img = next(
                (i for i in images
                 if str(i["id"]) == str(ref) or (i.get("name") or "").lower() == str(ref).lower()),
                None)
            if img:
                await push_library_photo(img["id"], screen=screen_id, duration=duration)
            else:
                logger.warning(f"MQTT: image '{ref}' not found")

        elif command == "mode":
            await push_mode(ModeContent(mode=payload), screen=screen_id)

        elif command == "blank":
            await blank_display(screen=screen_id)

        elif command == "sleep":
            wants_sleep = payload.strip().lower() in ("on", "1", "true", "sleep")
            await set_screen_sleep(screen_id, SleepBody(sleeping=wants_sleep))

        elif command == "playlist":
            action = payload.lower()
            if action == "next":
                await advance_screen_mode(screen_id)
            elif action == "play":
                await play_playlist(screen=screen_id)
            else:
                try:
                    await jump_playlist(PlaylistJump(pos=int(action)), screen=screen_id)
                except ValueError:
                    logger.warning(f"MQTT: unknown playlist action '{payload}'")

        elif command == "scoreboard":
            if not data:
                return
            item_ref = arg or data.get("id")
            item = None
            if item_ref is not None:
                item = next((i for i in state.playlist_items
                             if str(i["id"]) == str(item_ref)), None)
            else:
                item = next((i for i in state.playlist_items
                             if i["type"] == "scoreboard"), None)
            if not item:
                logger.warning(f"MQTT: scoreboard item '{item_ref}' not found on '{screen_id}'")
                return
            content = dict(item.get("content", {}))
            for key in ("home_score", "away_score", "home_name", "away_name"):
                if key in data:
                    content[key] = data[key]
            await database.update_playlist_item(item["id"], "scoreboard",
                                                content, item.get("duration"))
            state.playlist_items = await database.get_playlist_items(screen_id)
            cur = state.playlist_items[state.playlist_pos % len(state.playlist_items)]
            if cur["id"] == item["id"]:
                await _render_playlist_item(state)  # no transition — digits only

        else:
            logger.warning(f"MQTT: unknown command '{command}'")
    except HTTPException as e:
        logger.warning(f"MQTT: command '{command}' rejected: {e.detail}")


# ── Serve frontend ────────────────────────────────────────────────────────────

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # API/asset paths that reach the catch-all are genuinely missing —
        # return a real 404 instead of masking them with index.html
        if full_path.startswith(("api/", "ws", "uploads/")):
            raise HTTPException(404, "Not found")
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
