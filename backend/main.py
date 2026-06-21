import asyncio
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import database
import plugins as plugin_registry
from websocket_manager import manager
from charmap import blank_matrix, text_to_matrix
from config import settings


# ── Org resolution ────────────────────────────────────────────────────────────
# Self-hosted: always org 1. SaaS: swap this dependency for JWT middleware.

def get_org_id() -> int:
    return database.DEFAULT_ORG_ID

# ── Upload directory ──────────────────────────────────────────────────────────

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
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


_screens: dict[str, ScreenState] = {}


def get_screen_state(screen_id: str) -> ScreenState:
    if screen_id not in _screens:
        raise HTTPException(404, f"Screen '{screen_id}' not found")
    return _screens[screen_id]


# ── Content rendering ─────────────────────────────────────────────────────────

async def _render_mode(mode: str, rows: int, cols: int, db_settings: dict) -> list:
    from services.clock import get_clock_matrix
    from services.weather import get_weather_matrix
    from services.news import get_news_matrix
    from services.quotes import get_quote_matrix
    from services.calendar_svc import get_calendar_matrix

    if mode == "clock":
        return get_clock_matrix(
            rows, cols,
            fmt=db_settings.get("clock_format", "12h"),
            show_date=db_settings.get("show_date", "true") == "true",
            timezone=db_settings.get("timezone", "UTC"),
        )
    elif mode == "weather":
        return await get_weather_matrix(
            rows, cols,
            api_key=db_settings.get("weather_api_key", ""),
            location=db_settings.get("weather_location", ""),
            units=db_settings.get("weather_units", "imperial"),
        )
    elif mode == "news":
        cats = json.loads(db_settings.get("news_categories", '["general"]'))
        srcs = json.loads(db_settings.get("news_sources", "[]"))
        return await get_news_matrix(
            rows, cols,
            api_key=db_settings.get("news_api_key", ""),
            categories=cats, sources=srcs,
        )
    elif mode == "quotes":
        return await get_quote_matrix(rows, cols)
    elif mode == "calendar":
        return await get_calendar_matrix(
            rows, cols,
            ical_url=db_settings.get("calendar_ical_url", ""),
            timezone=db_settings.get("timezone", "UTC"),
        )
    return blank_matrix(rows, cols)


async def _render_playlist_item(state: ScreenState):
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
        if mode == "text":
            messages = await database.get_text_messages(state.screen_id)
            from services.text_svc import get_text_matrix
            state.matrix = await get_text_matrix(state.rows, state.cols, messages)
        else:
            state.matrix = await _render_mode(mode, state.rows, state.cols, db_settings)

    elif item_type == "text":
        state.mode = "text_push"
        state.matrix = text_to_matrix(content.get("text", ""), state.rows, state.cols)

    elif item_type == "photo":
        state.mode = "photo_push"
        state.photo_url = content.get("url", "")

    elif item_type == "color":
        state.mode = "image_push"
        state.color_matrix = content.get("color_matrix")

    await _broadcast_screen(state)


async def advance_screen_mode(screen_id: str):
    """Advance to the next content item and broadcast."""
    if screen_id not in _screens:
        return

    state = _screens[screen_id]

    # Universal playlist takes priority when items exist
    if state.playlist_items:
        state.playlist_pos = (state.playlist_pos + 1) % len(state.playlist_items)
        await _render_playlist_item(state)
        return

    # Fallback: rotate through enabled modes
    db_settings = await database.get_settings()
    modes = await database.get_modes(screen_id)
    enabled = [m for m in modes if m["enabled"]]
    if not enabled:
        return

    state.mode_idx = (state.mode_idx + 1) % len(enabled)
    mode_name = enabled[state.mode_idx]["mode"]
    state.mode = mode_name
    state.color_matrix = None
    state.photo_url = None

    if mode_name == "text":
        messages = await database.get_text_messages(screen_id)
        from services.text_svc import get_text_matrix
        matrix = await get_text_matrix(state.rows, state.cols, messages)
    else:
        matrix = await _render_mode(mode_name, state.rows, state.cols, db_settings)

    state.matrix = matrix
    await _broadcast_screen(state)


async def _broadcast_screen(state: ScreenState):
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
        await manager.broadcast(state.screen_id, {
            "type": "display_update",
            "matrix": state.matrix,
            "rows": state.rows,
            "cols": state.cols,
            "mode": state.mode,
            "screen_id": state.screen_id,
        })


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

    yield

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

class MatrixContent(BaseModel):
    matrix: list[list[int]]

class ColorMatrixContent(BaseModel):
    color_matrix: list[list[str]]

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_screen_id(sid: str) -> bool:
    return bool(re.match(r'^[a-z0-9_-]{1,64}$', sid))


def _save_upload(file_bytes: bytes, original_filename: str) -> str:
    ext = os.path.splitext(original_filename or "image.jpg")[1].lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(file_bytes)
    return f"/uploads/{filename}"


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
    return {"status": "deleted"}


async def _screens_payload():
    screens = await database.get_screens()
    return [
        {**s, "mode": _screens[s["id"]].mode if s["id"] in _screens else "unknown",
         "online": s["id"] in _screens}
        for s in screens
    ]


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
    await _broadcast_screen(state)
    return {"status": "ok", "screen": screen}


@app.post("/api/display/photo")
async def push_photo(
    file: UploadFile = File(...),
    screen: str = Query(default="main"),
):
    state = get_screen_state(screen)
    content = await file.read()
    image_url = _save_upload(content, file.filename or "photo.jpg")
    state.photo_url = image_url
    state.color_matrix = None
    state.mode = "photo_push"
    await _broadcast_screen(state)
    return {"status": "ok", "image_url": image_url, "screen": screen}


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


# ── File upload (for playlist photo items) ────────────────────────────────────

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Save an uploaded file and return its public URL. Does not affect the display."""
    content = await file.read()
    url = _save_upload(content, file.filename or "image.jpg")
    return {"url": url}


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
    await _render_playlist_item(state)
    # Restart rotation so timer starts fresh from now
    _stop_screen_rotation(screen)
    _start_screen_rotation(screen)
    return {"status": "ok", "screen": screen}


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

    new_settings = await database.get_settings()
    await manager.broadcast_all({"type": "settings_update", "settings": new_settings})
    return new_settings


# ── Per-screen modes ──────────────────────────────────────────────────────────

@app.get("/api/modes")
async def get_modes(screen: str = Query(default="main")):
    return await database.get_modes(screen)


@app.put("/api/modes/{mode}")
async def update_mode(mode: str, body: ModeUpdate, screen: str = Query(default="main")):
    await database.update_mode(screen, mode, body.enabled, body.sort_order, body.config or {})
    await manager.broadcast(screen, {"type": "modes_update", "modes": await database.get_modes(screen)})
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
        {"type": "modes_update", "modes": await database.get_modes(screen)},
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
