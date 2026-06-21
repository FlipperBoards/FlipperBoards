import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

import database
import scheduler
from websocket_manager import manager
from charmap import blank_matrix, text_to_matrix
from config import settings

# --- State ---
_display_state: dict = {
    "matrix": [],
    "rows": settings.default_rows,
    "cols": settings.default_cols,
    "mode": "clock",
    "mode_idx": 0,
}

_active_modes: list[str] = ["clock"]
_rotation_interval: int = 30


# --- Content refresh ---
async def refresh_display():
    """Called by scheduler to advance to next mode and update matrix."""
    global _display_state, _active_modes, _rotation_interval

    db_settings = await database.get_settings()
    rows = int(db_settings.get("rows", settings.default_rows))
    cols = int(db_settings.get("cols", settings.default_cols))

    modes = await database.get_modes()
    enabled = [m for m in modes if m["enabled"]]
    if not enabled:
        return

    _display_state["mode_idx"] = (_display_state["mode_idx"] + 1) % len(enabled)
    current_mode = enabled[_display_state["mode_idx"]]
    mode_name = current_mode["mode"]
    _display_state["mode"] = mode_name

    matrix = await _render_mode(mode_name, rows, cols, db_settings)
    _display_state["matrix"] = matrix
    _display_state["rows"] = rows
    _display_state["cols"] = cols

    await manager.broadcast({
        "type": "display_update",
        "matrix": matrix,
        "rows": rows,
        "cols": cols,
        "mode": mode_name,
    })


async def _render_mode(mode: str, rows: int, cols: int, db_settings: dict) -> list:
    from services.clock import get_clock_matrix
    from services.weather import get_weather_matrix
    from services.news import get_news_matrix
    from services.quotes import get_quote_matrix
    from services.calendar_svc import get_calendar_matrix
    from services.text_svc import get_text_matrix

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
            categories=cats,
            sources=srcs,
        )

    elif mode == "quotes":
        return await get_quote_matrix(rows, cols)

    elif mode == "calendar":
        return await get_calendar_matrix(
            rows, cols,
            ical_url=db_settings.get("calendar_ical_url", ""),
            timezone=db_settings.get("timezone", "UTC"),
        )

    elif mode == "text":
        messages = await database.get_text_messages()
        return await get_text_matrix(rows, cols, messages)

    return blank_matrix(rows, cols)


async def tick_clock():
    """Update clock display every second without advancing mode."""
    db_settings = await database.get_settings()
    mode = _display_state.get("mode", "clock")
    if mode != "clock":
        return

    rows = int(db_settings.get("rows", settings.default_rows))
    cols = int(db_settings.get("cols", settings.default_cols))
    matrix = await _render_mode("clock", rows, cols, db_settings)
    _display_state["matrix"] = matrix

    await manager.broadcast({
        "type": "display_update",
        "matrix": matrix,
        "rows": rows,
        "cols": cols,
        "mode": "clock",
    })


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()

    db_settings = await database.get_settings()
    rows = int(db_settings.get("rows", settings.default_rows))
    cols = int(db_settings.get("cols", settings.default_cols))

    from services.clock import get_clock_matrix
    _display_state["matrix"] = get_clock_matrix(
        rows, cols,
        fmt=db_settings.get("clock_format", "12h"),
        show_date=db_settings.get("show_date", "true") == "true",
        timezone=db_settings.get("timezone", "UTC"),
    )
    _display_state["rows"] = rows
    _display_state["cols"] = cols

    interval = int(db_settings.get("rotation_interval", 30))
    scheduler.start_scheduler()
    scheduler.schedule_rotation(interval, refresh_display)

    # Clock second ticker
    scheduler._scheduler.add_job(
        tick_clock,
        trigger="interval",
        seconds=1,
        id="clock_tick",
        replace_existing=True,
    )

    yield
    scheduler.stop_scheduler()


# --- App ---
app = FastAPI(title="FlipperBoards", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic models ---
class DisplayContent(BaseModel):
    text: str
    rows: Optional[int] = None
    cols: Optional[int] = None


class MatrixContent(BaseModel):
    matrix: list[list[int]]


class SettingsUpdate(BaseModel):
    rows: Optional[int] = None
    cols: Optional[int] = None
    rotation_interval: Optional[int] = None
    font: Optional[str] = None
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


class ModeUpdate(BaseModel):
    mode: str
    enabled: bool
    sort_order: int
    config: Optional[dict] = {}


class TextMessage(BaseModel):
    text: str
    duration: int = 30


# --- API Routes ---

@app.get("/api/state")
async def get_state():
    return _display_state


@app.post("/api/display/text")
async def push_text(content: DisplayContent):
    db_settings = await database.get_settings()
    rows = content.rows or int(db_settings.get("rows", settings.default_rows))
    cols = content.cols or int(db_settings.get("cols", settings.default_cols))

    matrix = text_to_matrix(content.text, rows, cols)
    _display_state["matrix"] = matrix
    _display_state["rows"] = rows
    _display_state["cols"] = cols
    _display_state["mode"] = "text_push"

    await manager.broadcast({
        "type": "display_update",
        "matrix": matrix,
        "rows": rows,
        "cols": cols,
        "mode": "text_push",
    })
    return {"status": "ok", "matrix": matrix}


@app.post("/api/display/matrix")
async def push_matrix(content: MatrixContent):
    matrix = content.matrix
    if not matrix:
        raise HTTPException(400, "Empty matrix")

    rows = len(matrix)
    cols = len(matrix[0]) if matrix else 0
    _display_state["matrix"] = matrix
    _display_state["rows"] = rows
    _display_state["cols"] = cols
    _display_state["mode"] = "matrix_push"

    await manager.broadcast({
        "type": "display_update",
        "matrix": matrix,
        "rows": rows,
        "cols": cols,
        "mode": "matrix_push",
    })
    return {"status": "ok"}


@app.post("/api/display/blank")
async def blank_display():
    db_settings = await database.get_settings()
    rows = int(db_settings.get("rows", settings.default_rows))
    cols = int(db_settings.get("cols", settings.default_cols))
    matrix = blank_matrix(rows, cols)
    _display_state["matrix"] = matrix
    _display_state["mode"] = "blank"

    await manager.broadcast({
        "type": "display_update",
        "matrix": matrix,
        "rows": rows,
        "cols": cols,
        "mode": "blank",
    })
    return {"status": "ok"}


@app.post("/api/display/next")
async def next_mode():
    await refresh_display()
    return {"status": "ok", "mode": _display_state["mode"]}


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

    # Reschedule if interval changed
    if "rotation_interval" in updates:
        scheduler.schedule_rotation(int(updates["rotation_interval"]), refresh_display)

    # Broadcast settings change
    new_settings = await database.get_settings()
    await manager.broadcast({"type": "settings_update", "settings": new_settings})
    return new_settings


@app.get("/api/modes")
async def get_modes():
    return await database.get_modes()


@app.put("/api/modes/{mode}")
async def update_mode(mode: str, body: ModeUpdate):
    await database.update_mode(mode, body.enabled, body.sort_order, body.config or {})
    await manager.broadcast({"type": "modes_update", "modes": await database.get_modes()})
    return {"status": "ok"}


@app.get("/api/messages")
async def get_messages():
    return await database.get_text_messages()


@app.post("/api/messages")
async def add_message(msg: TextMessage):
    msg_id = await database.add_text_message(msg.text, msg.duration)
    return {"id": msg_id, "text": msg.text, "duration": msg.duration}


@app.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: int):
    await database.delete_text_message(msg_id)
    return {"status": "ok"}


# --- WebSocket ---
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # Send current state on connect
    await ws.send_text(json.dumps({
        "type": "display_update",
        "matrix": _display_state["matrix"],
        "rows": _display_state["rows"],
        "cols": _display_state["cols"],
        "mode": _display_state["mode"],
    }))
    settings_data = await database.get_settings()
    await ws.send_text(json.dumps({"type": "settings_update", "settings": settings_data}))
    modes_data = await database.get_modes()
    await ws.send_text(json.dumps({"type": "modes_update", "modes": modes_data}))

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


# --- Serve frontend ---
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
