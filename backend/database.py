import aiosqlite
import json
from config import settings

DB_PATH = settings.db_path


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS display_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS screens (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                rows INTEGER NOT NULL DEFAULT 6,
                cols INTEGER NOT NULL DEFAULT 22
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS screen_modes (
                screen_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                config TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (screen_id, mode)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS text_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screen_id TEXT NOT NULL DEFAULT 'main',
                text TEXT NOT NULL,
                duration INTEGER NOT NULL DEFAULT 30,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS playlist_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screen_id TEXT NOT NULL,
                url TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.commit()
        await _seed_defaults(db)


async def _seed_defaults(db: aiosqlite.Connection):
    global_defaults = {
        "rotation_interval": "30",
        "tile_color": "#ffffff",
        "bg_color": "#1a1a1a",
        "tile_bg_color": "#2a2a2a",
        "timezone": "America/Chicago",
        "clock_format": "12h",
        "show_date": "true",
        "weather_location": "",
        "weather_units": "imperial",
        "weather_api_key": "",
        "news_api_key": "",
        "news_categories": '["technology","general"]',
        "news_sources": "[]",
        "calendar_ical_url": "",
        "sound_enabled": "true",
        "divider_width": "4",
        "divider_color": "#111111",
        "physical_mode": "false",
    }
    for key, value in global_defaults.items():
        await db.execute(
            "INSERT OR IGNORE INTO display_settings (key, value) VALUES (?, ?)",
            (key, value)
        )

    # Seed the default "main" screen
    await db.execute(
        "INSERT OR IGNORE INTO screens (id, name, rows, cols) VALUES (?, ?, ?, ?)",
        ("main", "Main Display", 6, 22)
    )

    # Seed default mode configs for the main screen
    mode_defaults = [
        ("main", "clock",          "{}", 1, 0),
        ("main", "text",           "{}", 0, 1),
        ("main", "weather",        "{}", 0, 2),
        ("main", "news",           "{}", 0, 3),
        ("main", "quotes",         "{}", 0, 4),
        ("main", "calendar",       "{}", 0, 5),
        ("main", "photo_playlist", "{}", 0, 6),
    ]
    for screen_id, mode, config, enabled, order in mode_defaults:
        await db.execute(
            "INSERT OR IGNORE INTO screen_modes (screen_id, mode, config, enabled, sort_order) VALUES (?,?,?,?,?)",
            (screen_id, mode, config, enabled, order)
        )

    await db.commit()


# ── Global settings ──────────────────────────────────────────────────────────

async def get_settings() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT key, value FROM display_settings") as cur:
            rows = await cur.fetchall()
    return {row["key"]: row["value"] for row in rows}


async def update_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO display_settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


# ── Screens ───────────────────────────────────────────────────────────────────

async def get_screens() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, name, rows, cols FROM screens ORDER BY id") as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def get_screen(screen_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, rows, cols FROM screens WHERE id = ?", (screen_id,)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def create_screen(screen_id: str, name: str, rows: int = 6, cols: int = 22):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO screens (id, name, rows, cols) VALUES (?, ?, ?, ?)",
            (screen_id, name, rows, cols)
        )
        mode_defaults = [
            ("clock", 1, 0), ("text", 0, 1), ("weather", 0, 2),
            ("news", 0, 3), ("quotes", 0, 4), ("calendar", 0, 5),
            ("photo_playlist", 0, 6),
        ]
        for mode, enabled, order in mode_defaults:
            await db.execute(
                "INSERT OR IGNORE INTO screen_modes (screen_id, mode, config, enabled, sort_order) VALUES (?,?,?,?,?)",
                (screen_id, mode, "{}", enabled, order)
            )
        await db.commit()


async def update_screen(screen_id: str, name: str, rows: int, cols: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE screens SET name=?, rows=?, cols=? WHERE id=?",
            (name, rows, cols, screen_id)
        )
        await db.commit()


async def delete_screen(screen_id: str):
    if screen_id == "main":
        raise ValueError("Cannot delete the main screen")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM screens WHERE id=?", (screen_id,))
        await db.execute("DELETE FROM screen_modes WHERE screen_id=?", (screen_id,))
        await db.execute("DELETE FROM text_messages WHERE screen_id=?", (screen_id,))
        await db.execute("DELETE FROM playlist_images WHERE screen_id=?", (screen_id,))
        await db.commit()


# ── Per-screen modes ──────────────────────────────────────────────────────────

async def get_modes(screen_id: str = "main") -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT mode, config, enabled, sort_order FROM screen_modes WHERE screen_id=? ORDER BY sort_order",
            (screen_id,)
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        # fallback: return default mode list (disabled)
        return [
            {"mode": m, "config": {}, "enabled": False, "sort_order": i}
            for i, m in enumerate(["clock", "text", "weather", "news", "quotes", "calendar"])
        ]
    return [
        {"mode": row["mode"], "config": json.loads(row["config"]),
         "enabled": bool(row["enabled"]), "sort_order": row["sort_order"]}
        for row in rows
    ]


async def update_mode(screen_id: str, mode: str, enabled: bool, sort_order: int, config: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO screen_modes (screen_id, mode, config, enabled, sort_order) VALUES (?,?,?,?,?)",
            (screen_id, mode, json.dumps(config), int(enabled), sort_order)
        )
        await db.commit()


# ── Per-screen text messages ──────────────────────────────────────────────────

async def get_text_messages(screen_id: str = "main") -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, text, duration, sort_order FROM text_messages WHERE screen_id=? ORDER BY sort_order, id",
            (screen_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def add_text_message(screen_id: str, text: str, duration: int = 30) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "INSERT INTO text_messages (screen_id, text, duration, sort_order) "
            "VALUES (?, ?, ?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM text_messages WHERE screen_id=?))",
            (screen_id, text, duration, screen_id)
        ) as cur:
            row_id = cur.lastrowid
        await db.commit()
    return row_id


async def delete_text_message(msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM text_messages WHERE id = ?", (msg_id,))
        await db.commit()


# ── Per-screen image playlist ─────────────────────────────────────────────────

async def get_playlist(screen_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, url, sort_order FROM playlist_images WHERE screen_id=? ORDER BY sort_order, id",
            (screen_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def add_playlist_image(screen_id: str, url: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "INSERT INTO playlist_images (screen_id, url, sort_order) "
            "VALUES (?, ?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM playlist_images WHERE screen_id=?))",
            (screen_id, url, screen_id)
        ) as cur:
            row_id = cur.lastrowid
        await db.commit()
    return row_id


async def remove_playlist_image(image_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM playlist_images WHERE id=?", (image_id,))
        await db.commit()


async def clear_playlist(screen_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM playlist_images WHERE screen_id=?", (screen_id,))
        await db.commit()
