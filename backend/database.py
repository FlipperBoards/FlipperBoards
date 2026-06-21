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
            CREATE TABLE IF NOT EXISTS mode_configs (
                mode TEXT PRIMARY KEY,
                config TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS text_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                duration INTEGER NOT NULL DEFAULT 30,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.commit()
        await _seed_defaults(db)


async def _seed_defaults(db: aiosqlite.Connection):
    defaults = {
        "rows": "6",
        "cols": "22",
        "rotation_interval": "30",
        "font": "mono",
        "tile_color": "#ffffff",
        "bg_color": "#1a1a1a",
        "tile_bg_color": "#2a2a2a",
        "timezone": "America/Chicago",
        "clock_format": "12h",
        "show_date": "true",
        "weather_location": "",
        "weather_units": "imperial",
        "news_categories": '["technology","general"]',
        "news_sources": "[]",
        "calendar_ical_url": "",
    }
    for key, value in defaults.items():
        await db.execute(
            "INSERT OR IGNORE INTO display_settings (key, value) VALUES (?, ?)",
            (key, value)
        )

    mode_defaults = [
        ("clock", json.dumps({}), 1, 0),
        ("text", json.dumps({}), 0, 1),
        ("weather", json.dumps({}), 0, 2),
        ("news", json.dumps({}), 0, 3),
        ("quotes", json.dumps({}), 0, 4),
        ("calendar", json.dumps({}), 0, 5),
    ]
    for mode, config, enabled, order in mode_defaults:
        await db.execute(
            "INSERT OR IGNORE INTO mode_configs (mode, config, enabled, sort_order) VALUES (?, ?, ?, ?)",
            (mode, config, enabled, order)
        )

    await db.commit()


async def get_settings() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT key, value FROM display_settings") as cursor:
            rows = await cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


async def update_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO display_settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


async def get_modes() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT mode, config, enabled, sort_order FROM mode_configs ORDER BY sort_order"
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {
            "mode": row["mode"],
            "config": json.loads(row["config"]),
            "enabled": bool(row["enabled"]),
            "sort_order": row["sort_order"],
        }
        for row in rows
    ]


async def update_mode(mode: str, enabled: bool, sort_order: int, config: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO mode_configs (mode, config, enabled, sort_order) VALUES (?, ?, ?, ?)",
            (mode, json.dumps(config), int(enabled), sort_order)
        )
        await db.commit()


async def get_text_messages() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, text, duration, sort_order FROM text_messages ORDER BY sort_order, id"
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def add_text_message(text: str, duration: int = 30) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "INSERT INTO text_messages (text, duration, sort_order) VALUES (?, ?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM text_messages))",
            (text, duration)
        ) as cursor:
            row_id = cursor.lastrowid
        await db.commit()
    return row_id


async def delete_text_message(msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM text_messages WHERE id = ?", (msg_id,))
        await db.commit()
