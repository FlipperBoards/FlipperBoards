import asyncio
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import mimetypes

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import database
import mode_registry
import plugins as plugin_registry
from websocket_manager import manager
from charmap import blank_matrix, text_to_matrix
from config import settings


# ── Org resolution ────────────────────────────────────────────────────────────
# Self-hosted: always org 1. SaaS: swap this dependency for JWT middleware.

def get_org_id() -> int:
    return database.DEFAULT_ORG_ID

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
        self.photo_url: str | None = None
        # Universal playlist — drives rotation when non-empty
        self.playlist_items: list[dict] = []
        self.playlist_pos: int = 0
        self.mode: str = "clock"
        self.mode_idx: int = 0
        self.rotation_task: asyncio.Task | None = None
        self.push_timer: asyncio.Task | None = None


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
            api_key=s.get("news_api_key", ""), categories=cats, sources=srcs)

    async def render_quotes(rows, cols, config, s):
        return await get_quote_matrix(rows, cols, custom_quotes=config.get("custom_quotes", ""))

    async def render_calendar(rows, cols, config, s):
        return await get_calendar_matrix(rows, cols,
            ical_url=s.get("calendar_ical_url", ""),
            timezone=s.get("timezone", "UTC"))

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
    builtin = [
        ModeDefinition("clock",    "Clock",         "🕐", "Live time & date",       render=render_clock),
        ModeDefinition("weather",  "Weather",       "🌤", "Current conditions",      render=render_weather),
        ModeDefinition("news",     "News",          "📰", "Top headlines",           render=render_news),
        ModeDefinition("quotes",   "Quotes",        "💬", "Inspirational quotes",    config_schema=_quotes_schema, render=render_quotes),
        ModeDefinition("calendar", "Calendar",      "📅", "Upcoming events",         render=render_calendar),
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
        return await get_text_matrix(rows, cols, messages)

    # all other modes (built-in and plugin) go through the registry
    matrix = await mode_registry.render(mode, rows, cols, mode_config or {}, db_settings)
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
    state.photo_url = None

    if item_type == "mode":
        mode = content.get("mode", "clock")
        state.mode = mode
        db_settings = await database.get_settings()
        mode_entries = await database.get_modes(state.screen_id)
        mode_entry = next((m for m in mode_entries if m["mode"] == mode), None)
        mode_config = mode_entry.get("config", {}) if mode_entry else {}
        state.matrix = await _render_mode(mode, state.rows, state.cols, db_settings,
                                          screen_id=state.screen_id, mode_config=mode_config)

    elif item_type == "text":
        state.mode = "text_push"
        state.matrix = text_to_matrix(content.get("text", ""), state.rows, state.cols)

    elif item_type == "photo":
        state.mode = "photo_push"
        state.photo_url = content.get("url", "")

    elif item_type == "color":
        state.mode = "image_push"
        state.color_matrix = content.get("color_matrix")

    elif item_type == "matrix":
        state.mode = "matrix_push"
        state.matrix = content.get("matrix", blank_matrix(state.rows, state.cols))

    elif item_type == "scoreboard":
        from services.scoreboard import get_scoreboard_matrix
        state.mode = "scoreboard"
        state.matrix = get_scoreboard_matrix(
            state.rows, state.cols,
            content.get("home_name", "HOME"), content.get("away_name", "AWAY"),
            content.get("home_score", 0), content.get("away_score", 0),
        )

    await _broadcast_screen(state, transition=transition)


async def advance_screen_mode(screen_id: str):
    """Advance to the next content item and broadcast."""
    if screen_id not in _screens:
        return

    state = _screens[screen_id]

    # Universal playlist takes priority when items exist
    if state.playlist_items:
        old_pos = state.playlist_pos
        state.playlist_pos = (state.playlist_pos + 1) % len(state.playlist_items)
        # Full-board sweep only when the displayed item actually changes
        await _render_playlist_item(
            state, transition="sweep" if state.playlist_pos != old_pos else None)
        return

    # Fallback: rotate through enabled modes
    db_settings = await database.get_settings()
    modes = await database.get_modes(screen_id)
    enabled = [m for m in modes if m["enabled"]]
    if not enabled:
        return

    state.mode_idx = (state.mode_idx + 1) % len(enabled)
    mode_entry = enabled[state.mode_idx]
    mode_name = mode_entry["mode"]
    state.mode = mode_name
    state.color_matrix = None
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
        if transition:
            msg["transition"] = transition
        await manager.broadcast(state.screen_id, msg)

    if _mqtt:
        await _mqtt.publish_screen_state(state)


async def _rotation_loop(screen_id: str):
    """Per-screen loop — respects per-item durations when a playlist is active."""
    try:
        while True:
            state = _screens[screen_id]
            db_settings = await database.get_settings()
            default_interval = int(db_settings.get("rotation_interval", 30))

            if state.playlist_items:
                item = state.playlist_items[state.playlist_pos]
                duration = item.get("duration", default_interval)
            else:
                duration = default_interval

            await asyncio.sleep(duration)
            await advance_screen_mode(screen_id)
    except asyncio.CancelledError:
        pass


async def _clock_tick_loop():
    """Global 1-second tick — updates all screens currently in clock mode."""
    try:
        while True:
            await asyncio.sleep(1)
            db_settings = await database.get_settings()
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
    except asyncio.CancelledError:
        pass


def _start_screen_rotation(screen_id: str):
    task = asyncio.create_task(_rotation_loop(screen_id))
    _screens[screen_id].rotation_task = task
    return task


def _stop_screen_rotation(screen_id: str):
    state = _screens.get(screen_id)
    if state and state.rotation_task:
        state.rotation_task.cancel()
        state.rotation_task = None


def _restart_all_rotations():
    for sid in list(_screens.keys()):
        _stop_screen_rotation(sid)
        _start_screen_rotation(sid)


# ── Lifespan ──────────────────────────────────────────────────────────────────

_clock_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _clock_task

    # Load plugins before DB init so they can register tables via on_db_init
    loaded_plugins = plugin_registry.load(settings.plugins)
    await database.init_db()
    await database.migrate_existing_uploads(UPLOAD_DIR)

    # Register built-in modes first, then plugin modes
    _register_builtin_modes()
    await plugin_registry.startup(app, loaded_plugins)

    db_settings = await database.get_settings()
    screens = await database.get_screens()

    from services.clock import get_clock_matrix

    for screen in screens:
        sid = screen["id"]
        state = ScreenState(sid, screen["name"], screen["rows"], screen["cols"])

        # Load universal playlist; if populated, render item[0] instead of clock
        items = await database.get_playlist_items(sid)
        state.playlist_items = items
        if items:
            # Will be rendered properly after tasks start; set a safe initial state
            state.playlist_pos = 0
            state.mode = "playlist"
        else:
            state.matrix = get_clock_matrix(
                screen["rows"], screen["cols"],
                fmt=db_settings.get("clock_format", "12h"),
                show_date=db_settings.get("show_date", "true") == "true",
                timezone=db_settings.get("timezone", "UTC"),
            )

        _screens[sid] = state

    for sid in _screens:
        _start_screen_rotation(sid)

    # Render initial playlist item for screens that have one
    for sid, state in _screens.items():
        if state.playlist_items:
            await _render_playlist_item(state)

    _clock_task = asyncio.create_task(_clock_tick_loop())

    global _mqtt
    from mqtt_bridge import MQTTBridge
    _mqtt = MQTTBridge(dispatch=_mqtt_dispatch,
                       screens_provider=lambda: _screens,
                       modes_provider=mode_registry.all_modes)
    await _mqtt.start()

    yield

    await _mqtt.stop()
    _mqtt = None
    _clock_task.cancel()
    for sid in list(_screens.keys()):
        _stop_screen_rotation(sid)
    await plugin_registry.shutdown()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="FlipperBoards", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ── Pydantic models ───────────────────────────────────────────────────────────

class DisplayContent(BaseModel):
    text: str
    duration: Optional[int] = None   # seconds to show; None = until manually changed

class MatrixContent(BaseModel):
    matrix: list[list[int]]
    duration: Optional[int] = None

class ColorMatrixContent(BaseModel):
    color_matrix: list[list[str]]
    duration: Optional[int] = None

class SettingsUpdate(BaseModel):
    rotation_interval: Optional[int] = None
    tile_color: Optional[str] = None
    bg_color: Optional[str] = None
    tile_bg_color: Optional[str] = None
    timezone: Optional[str] = None
    clock_format: Optional[str] = None
    show_date: Optional[bool] = None
    weather_location: Optional[str] = None
    weather_units: Optional[str] = None
    weather_api_key: Optional[str] = None
    news_api_key: Optional[str] = None
    news_categories: Optional[list[str]] = None
    news_sources: Optional[list[str]] = None
    calendar_ical_url: Optional[str] = None
    sound_enabled: Optional[bool] = None
    divider_width: Optional[int] = None
    divider_color: Optional[str] = None
    physical_mode: Optional[bool] = None
    flip_duration: Optional[int] = None
    mqtt_enabled: Optional[bool] = None
    mqtt_host: Optional[str] = None
    mqtt_port: Optional[int] = None
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_base_topic: Optional[str] = None
    mqtt_ha_discovery: Optional[bool] = None

class ModeContent(BaseModel):
    mode: str
    duration: Optional[int] = None

class PlaylistJump(BaseModel):
    pos: int

class ImageUpdate(BaseModel):
    name: Optional[str] = None
    folder: Optional[str] = None


class ScreenCreate(BaseModel):
    id: str
    name: str
    rows: int = 6
    cols: int = 22

class ScreenUpdate(BaseModel):
    name: str
    rows: int
    cols: int

class ModeUpdate(BaseModel):
    mode: str
    enabled: bool
    sort_order: int
    config: Optional[dict] = {}

class TextMessage(BaseModel):
    text: str
    duration: int = 30

class PlaylistItemCreate(BaseModel):
    type: str              # 'mode', 'text', 'photo', 'color'
    content: dict          # varies by type
    duration: int = 30

class PlaylistItemUpdate(BaseModel):
    type: str
    content: dict
    duration: int

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
    filename = _save_upload(file_bytes, original_filename)
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
        })
    return result


@app.post("/api/screens", status_code=201)
async def create_screen(body: ScreenCreate):
    if not _valid_screen_id(body.id):
        raise HTTPException(400, "Screen ID must be lowercase alphanumeric, hyphens, underscores, max 64 chars")
    if body.id in _screens:
        raise HTTPException(409, f"Screen '{body.id}' already exists")

    await database.create_screen(body.id, body.name, body.rows, body.cols)

    db_settings = await database.get_settings()
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

    await database.update_screen(screen_id, body.name, body.rows, body.cols)
    state = _screens[screen_id]
    state.name = body.name
    if state.rows != body.rows or state.cols != body.cols:
        state.rows = body.rows
        state.cols = body.cols
        state.matrix = blank_matrix(body.rows, body.cols)

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
    await manager.broadcast_all({"type": "screens_update", "screens": await _screens_payload()})
    if _mqtt:
        await _mqtt.remove_screen_discovery(screen_id)
    return {"status": "deleted"}


async def _screens_payload():
    screens = await database.get_screens()
    return [
        {**s, "mode": _screens[s["id"]].mode if s["id"] in _screens else "unknown",
         "online": s["id"] in _screens}
        for s in screens
    ]


def _schedule_revert(state: ScreenState, screen_id: str, duration: Optional[int]) -> None:
    """Cancel any existing push timer. If duration > 0, advance mode after N seconds."""
    if state.push_timer and not state.push_timer.done():
        state.push_timer.cancel()
    state.push_timer = None
    if duration is not None and duration > 0:
        async def _revert():
            try:
                await asyncio.sleep(duration)
                await advance_screen_mode(screen_id)
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
    }


@app.post("/api/display/text")
async def push_text(content: DisplayContent, screen: str = Query(default="main")):
    state = get_screen_state(screen)
    state.matrix = text_to_matrix(content.text, state.rows, state.cols)
    state.color_matrix = None
    state.photo_url = None
    state.mode = "text_push"
    _schedule_revert(state, screen, content.duration)
    await _broadcast_screen(state)
    return {"status": "ok", "screen": screen}


@app.post("/api/display/matrix")
async def push_matrix(content: MatrixContent, screen: str = Query(default="main")):
    if not content.matrix:
        raise HTTPException(400, "Empty matrix")
    state = get_screen_state(screen)
    state.matrix = content.matrix
    state.rows = len(content.matrix)
    state.cols = len(content.matrix[0]) if content.matrix else 0
    state.color_matrix = None
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
    state.color_matrix = content.color_matrix
    state.photo_url = None
    state.rows = len(content.color_matrix)
    state.cols = len(content.color_matrix[0]) if content.color_matrix else state.cols
    state.mode = "image_push"
    _schedule_revert(state, screen, content.duration)
    await _broadcast_screen(state)
    return {"status": "ok", "screen": screen}


@app.post("/api/display/photo")
async def push_photo(
    file: UploadFile = File(...),
    name: str = Form(default=''),
    folder: str = Form(default=''),
    duration: Optional[int] = Form(default=None),
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
async def push_library_photo(image_id: int, screen: str = Query(default="main"), duration: Optional[int] = Query(default=None)):
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
    state.photo_url = None
    state.mode = "blank"
    await _broadcast_screen(state)
    return {"status": "ok"}


@app.post("/api/display/next")
async def next_mode(screen: str = Query(default="main")):
    if screen not in _screens:
        raise HTTPException(404)
    await advance_screen_mode(screen)
    return {"status": "ok", "mode": _screens[screen].mode}


@app.post("/api/display/mode")
async def push_mode(content: ModeContent, screen: str = Query(default="main")):
    """Switch the display to a specific mode immediately."""
    state = get_screen_state(screen)
    mode = content.mode.strip().lower()
    if mode_registry.get(mode) is None:
        raise HTTPException(400, f"Unknown mode '{mode}'")
    db_settings = await database.get_settings()
    mode_entries = await database.get_modes(screen)
    mode_entry = next((m for m in mode_entries if m["mode"] == mode), None)
    mode_config = mode_entry.get("config", {}) if mode_entry else {}
    state.mode = mode
    state.color_matrix = None
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
    item_id = await database.add_playlist_item(screen, body.type, body.content, body.duration)
    state.playlist_items = await database.get_playlist_items(screen)
    return {"status": "created", "id": item_id}


@app.put("/api/playlist/{item_id}")
async def update_playlist_item(item_id: int, body: PlaylistItemUpdate, screen: str = Query(default="main")):
    state = get_screen_state(screen)
    await database.update_playlist_item(item_id, body.type, body.content, body.duration)
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
    await database.remove_playlist_item(item_id)
    state.playlist_items = await database.get_playlist_items(screen)
    if state.playlist_items:
        state.playlist_pos = min(state.playlist_pos, len(state.playlist_items) - 1)
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
                      duration: Optional[int] = Query(default=None)):
    design = await database.get_design(design_id)
    if not design:
        raise HTTPException(404, "Design not found")
    state = get_screen_state(screen)
    state.matrix = design["matrix"]
    state.color_matrix = None
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
    return await database.get_settings()


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

    new_settings = await database.get_settings()
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
    db_settings = await database.get_settings()
    screens_list = await _screens_payload()

    initial_msgs = [
        {"type": "settings_update", "settings": db_settings},
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
            initial_msgs.insert(0, {
                "type": "display_update",
                "matrix": state.matrix,
                "rows": state.rows,
                "cols": state.cols,
                "mode": state.mode,
                "screen_id": screen,
            })

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
        print(f"MQTT: unknown screen '{screen_id}'")
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
                print(f"MQTT: design '{ref}' not found")

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
                print(f"MQTT: image '{ref}' not found")

        elif command == "mode":
            await push_mode(ModeContent(mode=payload), screen=screen_id)

        elif command == "blank":
            await blank_display(screen=screen_id)

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
                    print(f"MQTT: unknown playlist action '{payload}'")

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
                print(f"MQTT: scoreboard item '{item_ref}' not found on '{screen_id}'")
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
            print(f"MQTT: unknown command '{command}'")
    except HTTPException as e:
        print(f"MQTT: command '{command}' rejected: {e.detail}")


# ── Serve frontend ────────────────────────────────────────────────────────────

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
