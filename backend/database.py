import aiosqlite
import json
from contextlib import asynccontextmanager
from config import settings

DB_PATH = settings.db_path

DEFAULT_ORG_ID = 1


@asynccontextmanager
async def _connect():
    """Shared connection factory: WAL journal + busy timeout so concurrent
    reads/writes wait instead of raising 'database is locked'."""
    conn = aiosqlite.connect(DB_PATH)
    # aiosqlite.Connection IS a Thread. If the awaiting task is cancelled at
    # exactly the wrong moment (a known aiosqlite race), the connection's
    # cleanup never runs and the worker thread lives forever — as a daemon it
    # can at least never block process exit.
    conn.daemon = True
    async with conn as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        yield db


# ── Schema init & migration ───────────────────────────────────────────────────

async def init_db():
    async with _connect() as db:
        await _create_tables(db)
        await _notify_plugins(db)
        await db.commit()
        await _seed_defaults(db)


async def _create_tables(db: aiosqlite.Connection):
    # ── Identity / auth tables (used in SaaS; present but unpopulated in self-hosted) ──

    await db.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            slug        TEXT    NOT NULL UNIQUE,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    NOT NULL UNIQUE,
            name        TEXT    NOT NULL DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS org_members (
            org_id      INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id     INTEGER NOT NULL REFERENCES users(id)         ON DELETE CASCADE,
            role        TEXT    NOT NULL DEFAULT 'member',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (org_id, user_id)
        )
    """)

    # ── Core display tables ───────────────────────────────────────────────────

    await db.execute("""
        CREATE TABLE IF NOT EXISTS display_settings (
            org_id  INTEGER NOT NULL DEFAULT 1,
            key     TEXT    NOT NULL,
            value   TEXT    NOT NULL,
            PRIMARY KEY (org_id, key)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS screens (
            id       TEXT    NOT NULL,
            org_id   INTEGER NOT NULL DEFAULT 1,
            name     TEXT    NOT NULL,
            rows     INTEGER NOT NULL DEFAULT 6,
            cols     INTEGER NOT NULL DEFAULT 22,
            schedule TEXT    NOT NULL DEFAULT '{}',
            PRIMARY KEY (org_id, id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS screen_modes (
            org_id      INTEGER NOT NULL DEFAULT 1,
            screen_id   TEXT    NOT NULL,
            mode        TEXT    NOT NULL,
            config      TEXT    NOT NULL DEFAULT '{}',
            enabled     INTEGER NOT NULL DEFAULT 0,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (org_id, screen_id, mode)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS text_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id      INTEGER NOT NULL DEFAULT 1,
            screen_id   TEXT    NOT NULL DEFAULT 'main',
            text        TEXT    NOT NULL,
            duration    INTEGER NOT NULL DEFAULT 30,
            sort_order  INTEGER NOT NULL DEFAULT 0
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS playlist_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id      INTEGER NOT NULL DEFAULT 1,
            screen_id   TEXT    NOT NULL,
            type        TEXT    NOT NULL,
            content     TEXT    NOT NULL DEFAULT '{}',
            duration    INTEGER NOT NULL DEFAULT 30,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            window      TEXT    NOT NULL DEFAULT '{}'
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS image_library (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id       INTEGER NOT NULL DEFAULT 1,
            filename     TEXT    NOT NULL UNIQUE,
            name         TEXT    NOT NULL DEFAULT '',
            folder       TEXT    NOT NULL DEFAULT '',
            size         INTEGER NOT NULL DEFAULT 0,
            content_type TEXT    NOT NULL DEFAULT 'image/jpeg',
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS designs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id     INTEGER NOT NULL DEFAULT 1,
            screen_id  TEXT    NOT NULL DEFAULT 'main',
            name       TEXT    NOT NULL,
            matrix     TEXT    NOT NULL,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token       TEXT    PRIMARY KEY,
            org_id      INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            expires_at  TEXT    NOT NULL
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS screen_state (
            org_id      INTEGER NOT NULL DEFAULT 1,
            screen_id   TEXT    NOT NULL,
            state       TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (org_id, screen_id)
        )
    """)

    # Lookup indexes — these tables are queried by (org_id, screen_id)/folder
    # on every rotation tick and remote-control fetch
    await db.execute("CREATE INDEX IF NOT EXISTS idx_playlist_screen ON playlist_items(org_id, screen_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_screen ON text_messages(org_id, screen_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_designs_screen  ON designs(org_id, screen_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_images_folder   ON image_library(org_id, folder)")


async def _notify_plugins(db: aiosqlite.Connection):
    import plugins as plugin_registry
    await plugin_registry.db_init(db)


async def _seed_defaults(db: aiosqlite.Connection):
    # Default organization (self-hosted always uses org_id=1)
    await db.execute(
        "INSERT OR IGNORE INTO organizations (id, name, slug) VALUES (?, ?, ?)",
        (1, "Default", "default")
    )

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
        "flip_duration": "120",
        "divider_width": "4",
        "divider_color": "#111111",
        "physical_mode": "false",
        "mqtt_enabled": "false",
        "mqtt_host": "",
        "mqtt_port": "1883",
        "mqtt_username": "",
        "mqtt_password": "",
        "mqtt_base_topic": "flipperboards",
        "mqtt_ha_discovery": "true",
        "auth_enabled": "false",
        "auth_password_hash": "",
    }
    for key, value in global_defaults.items():
        await db.execute(
            "INSERT OR IGNORE INTO display_settings (org_id, key, value) VALUES (?, ?, ?)",
            (DEFAULT_ORG_ID, key, value)
        )

    await db.execute(
        "INSERT OR IGNORE INTO screens (id, org_id, name, rows, cols) VALUES (?, ?, ?, ?, ?)",
        ("main", DEFAULT_ORG_ID, "Main Display", 6, 22)
    )

    mode_defaults = [
        ("clock", 1, 0), ("text", 0, 1), ("weather", 0, 2),
        ("news", 0, 3), ("quotes", 0, 4), ("calendar", 0, 5),
    ]
    for mode, enabled, order in mode_defaults:
        await db.execute(
            "INSERT OR IGNORE INTO screen_modes "
            "(org_id, screen_id, mode, config, enabled, sort_order) VALUES (?,?,?,?,?,?)",
            (DEFAULT_ORG_ID, "main", mode, "{}", enabled, order)
        )

    await db.commit()


# ── Global settings ───────────────────────────────────────────────────────────

async def get_settings(org_id: int = DEFAULT_ORG_ID) -> dict:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT key, value FROM display_settings WHERE org_id = ?", (org_id,)
        ) as cur:
            rows = await cur.fetchall()
    return {row["key"]: row["value"] for row in rows}


async def update_setting(key: str, value: str, org_id: int = DEFAULT_ORG_ID):
    async with _connect() as db:
        await db.execute(
            "INSERT OR REPLACE INTO display_settings (org_id, key, value) VALUES (?, ?, ?)",
            (org_id, key, value)
        )
        await db.commit()


# ── Organizations ─────────────────────────────────────────────────────────────

async def get_organization(org_id: int) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, slug, created_at FROM organizations WHERE id = ?", (org_id,)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


# ── Screens ───────────────────────────────────────────────────────────────────

def _screen_row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["schedule"] = json.loads(d.get("schedule") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["schedule"] = {}
    return d


async def get_screens(org_id: int = DEFAULT_ORG_ID) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, rows, cols, schedule FROM screens WHERE org_id = ? ORDER BY id",
            (org_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [_screen_row_to_dict(row) for row in rows]


async def get_screen(screen_id: str, org_id: int = DEFAULT_ORG_ID) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, rows, cols, schedule FROM screens WHERE id = ? AND org_id = ?",
            (screen_id, org_id)
        ) as cur:
            row = await cur.fetchone()
    return _screen_row_to_dict(row) if row else None


async def create_screen(
    screen_id: str, name: str, rows: int = 6, cols: int = 22, org_id: int = DEFAULT_ORG_ID
):
    async with _connect() as db:
        await db.execute(
            "INSERT OR IGNORE INTO screens (id, org_id, name, rows, cols) VALUES (?, ?, ?, ?, ?)",
            (screen_id, org_id, name, rows, cols)
        )
        mode_defaults = [
            ("clock", 1, 0), ("text", 0, 1), ("weather", 0, 2),
            ("news", 0, 3), ("quotes", 0, 4), ("calendar", 0, 5),
        ]
        for mode, enabled, order in mode_defaults:
            await db.execute(
                "INSERT OR IGNORE INTO screen_modes "
                "(org_id, screen_id, mode, config, enabled, sort_order) VALUES (?,?,?,?,?,?)",
                (org_id, screen_id, mode, "{}", enabled, order)
            )
        await db.commit()


async def update_screen(
    screen_id: str, name: str, rows: int, cols: int,
    schedule: dict | None = None, org_id: int = DEFAULT_ORG_ID
):
    async with _connect() as db:
        if schedule is None:
            await db.execute(
                "UPDATE screens SET name=?, rows=?, cols=? WHERE id=? AND org_id=?",
                (name, rows, cols, screen_id, org_id)
            )
        else:
            await db.execute(
                "UPDATE screens SET name=?, rows=?, cols=?, schedule=? WHERE id=? AND org_id=?",
                (name, rows, cols, json.dumps(schedule), screen_id, org_id)
            )
        await db.commit()


async def delete_screen(screen_id: str, org_id: int = DEFAULT_ORG_ID):
    if screen_id == "main":
        raise ValueError("Cannot delete the main screen")
    async with _connect() as db:
        await db.execute(
            "DELETE FROM screens WHERE id=? AND org_id=?", (screen_id, org_id)
        )
        await db.execute(
            "DELETE FROM screen_modes WHERE screen_id=? AND org_id=?", (screen_id, org_id)
        )
        await db.execute(
            "DELETE FROM text_messages WHERE screen_id=? AND org_id=?", (screen_id, org_id)
        )
        await db.execute(
            "DELETE FROM playlist_items WHERE screen_id=? AND org_id=?", (screen_id, org_id)
        )
        await db.commit()


# ── Per-screen modes ──────────────────────────────────────────────────────────

async def get_modes(screen_id: str = "main", org_id: int = DEFAULT_ORG_ID) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT mode, config, enabled, sort_order FROM screen_modes "
            "WHERE screen_id=? AND org_id=? ORDER BY sort_order",
            (screen_id, org_id)
        ) as cur:
            rows = await cur.fetchall()
    if not rows:
        return [
            {"mode": m, "config": {}, "enabled": False, "sort_order": i}
            for i, m in enumerate(["clock", "text", "weather", "news", "quotes", "calendar"])
        ]
    return [
        {
            "mode": row["mode"],
            "config": json.loads(row["config"]),
            "enabled": bool(row["enabled"]),
            "sort_order": row["sort_order"],
        }
        for row in rows
    ]


async def update_mode(
    screen_id: str, mode: str, enabled: bool, sort_order: int, config: dict,
    org_id: int = DEFAULT_ORG_ID,
):
    async with _connect() as db:
        await db.execute(
            "INSERT OR REPLACE INTO screen_modes "
            "(org_id, screen_id, mode, config, enabled, sort_order) VALUES (?,?,?,?,?,?)",
            (org_id, screen_id, mode, json.dumps(config), int(enabled), sort_order)
        )
        await db.commit()


# ── Per-screen text messages ──────────────────────────────────────────────────

async def get_text_messages(
    screen_id: str = "main", org_id: int = DEFAULT_ORG_ID
) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, text, duration, sort_order FROM text_messages "
            "WHERE screen_id=? AND org_id=? ORDER BY sort_order, id",
            (screen_id, org_id)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def add_text_message(
    screen_id: str, text: str, duration: int = 30, org_id: int = DEFAULT_ORG_ID
) -> int:
    async with _connect() as db:
        async with db.execute(
            "INSERT INTO text_messages (org_id, screen_id, text, duration, sort_order) "
            "VALUES (?, ?, ?, ?, "
            "(SELECT COALESCE(MAX(sort_order),0)+1 FROM text_messages WHERE screen_id=? AND org_id=?))",
            (org_id, screen_id, text, duration, screen_id, org_id)
        ) as cur:
            row_id = cur.lastrowid
        await db.commit()
    return row_id


async def delete_text_message(msg_id: int, org_id: int = DEFAULT_ORG_ID):
    async with _connect() as db:
        await db.execute(
            "DELETE FROM text_messages WHERE id = ? AND org_id = ?", (msg_id, org_id)
        )
        await db.commit()


# ── Universal content playlist ────────────────────────────────────────────────

async def get_playlist_items(
    screen_id: str, org_id: int = DEFAULT_ORG_ID
) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, type, content, duration, sort_order, window FROM playlist_items "
            "WHERE screen_id=? AND org_id=? ORDER BY sort_order, id",
            (screen_id, org_id)
        ) as cur:
            rows = await cur.fetchall()
    result = []
    for row in rows:
        try:
            window = json.loads(row["window"] or "{}")
        except (json.JSONDecodeError, TypeError):
            window = {}
        result.append({
            "id": row["id"],
            "type": row["type"],
            "content": json.loads(row["content"]),
            "duration": row["duration"],
            "sort_order": row["sort_order"],
            "window": window,
        })
    return result


async def add_playlist_item(
    screen_id: str, item_type: str, content: dict, duration: int,
    window: dict | None = None, org_id: int = DEFAULT_ORG_ID,
) -> int:
    async with _connect() as db:
        async with db.execute(
            "INSERT INTO playlist_items (org_id, screen_id, type, content, duration, window, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?, "
            "(SELECT COALESCE(MAX(sort_order), 0) + 1 FROM playlist_items WHERE screen_id=? AND org_id=?))",
            (org_id, screen_id, item_type, json.dumps(content), duration,
             json.dumps(window or {}), screen_id, org_id)
        ) as cur:
            row_id = cur.lastrowid
        await db.commit()
    return row_id


async def update_playlist_item(
    item_id: int, item_type: str, content: dict, duration: int,
    window: dict | None = None, org_id: int = DEFAULT_ORG_ID,
):
    async with _connect() as db:
        if window is None:
            await db.execute(
                "UPDATE playlist_items SET type=?, content=?, duration=? WHERE id=? AND org_id=?",
                (item_type, json.dumps(content), duration, item_id, org_id)
            )
        else:
            await db.execute(
                "UPDATE playlist_items SET type=?, content=?, duration=?, window=? WHERE id=? AND org_id=?",
                (item_type, json.dumps(content), duration, json.dumps(window), item_id, org_id)
            )
        await db.commit()


async def remove_playlist_item(item_id: int, org_id: int = DEFAULT_ORG_ID):
    async with _connect() as db:
        await db.execute(
            "DELETE FROM playlist_items WHERE id=? AND org_id=?", (item_id, org_id)
        )
        await db.commit()


async def clear_playlist_items(screen_id: str, org_id: int = DEFAULT_ORG_ID):
    async with _connect() as db:
        await db.execute(
            "DELETE FROM playlist_items WHERE screen_id=? AND org_id=?", (screen_id, org_id)
        )
        await db.commit()


async def reorder_playlist_items(
    screen_id: str, ordered_ids: list[int], org_id: int = DEFAULT_ORG_ID
):
    async with _connect() as db:
        for order, item_id in enumerate(ordered_ids):
            await db.execute(
                "UPDATE playlist_items SET sort_order=? WHERE id=? AND screen_id=? AND org_id=?",
                (order, item_id, screen_id, org_id)
            )
        await db.commit()


# ── Image library ─────────────────────────────────────────────────────────────

async def add_image(filename: str, name: str = '', folder: str = '',
                    size: int = 0, content_type: str = 'image/jpeg',
                    org_id: int = DEFAULT_ORG_ID) -> int:
    async with _connect() as db:
        cur = await db.execute(
            "INSERT INTO image_library (org_id, filename, name, folder, size, content_type) "
            "VALUES (?,?,?,?,?,?)",
            (org_id, filename, name, folder, size, content_type),
        )
        await db.commit()
        return cur.lastrowid


async def get_images(folder: str | None = None, org_id: int = DEFAULT_ORG_ID) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        if folder is not None:
            sql = ("SELECT id, filename, name, folder, size, content_type, created_at "
                   "FROM image_library WHERE org_id=? AND folder=? ORDER BY created_at DESC")
            params = (org_id, folder)
        else:
            sql = ("SELECT id, filename, name, folder, size, content_type, created_at "
                   "FROM image_library WHERE org_id=? ORDER BY created_at DESC")
            params = (org_id,)
        async with db.execute(sql, params) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_image(image_id: int, org_id: int = DEFAULT_ORG_ID) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, filename, name, folder, size, content_type, created_at "
            "FROM image_library WHERE id=? AND org_id=?",
            (image_id, org_id),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_image(image_id: int, name: str | None = None, folder: str | None = None,
                       org_id: int = DEFAULT_ORG_ID):
    updates: dict = {}
    if name is not None:
        updates['name'] = name
    if folder is not None:
        updates['folder'] = folder
    if not updates:
        return
    cols = ', '.join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [image_id, org_id]
    async with _connect() as db:
        await db.execute(f"UPDATE image_library SET {cols} WHERE id=? AND org_id=?", vals)
        await db.commit()


async def delete_image(image_id: int, org_id: int = DEFAULT_ORG_ID) -> str | None:
    """Removes the DB record and returns the filename (for disk cleanup), or None if not found."""
    async with _connect() as db:
        async with db.execute(
            "SELECT filename FROM image_library WHERE id=? AND org_id=?", (image_id, org_id)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        await db.execute("DELETE FROM image_library WHERE id=? AND org_id=?", (image_id, org_id))
        await db.commit()
        return row[0]


async def remove_playlist_items_by_image_url(image_url: str, org_id: int = DEFAULT_ORG_ID):
    """Delete playlist items whose content JSON contains the given image URL."""
    async with _connect() as db:
        await db.execute(
            "DELETE FROM playlist_items WHERE org_id=? AND content LIKE ?",
            (org_id, f'%{image_url}%'),
        )
        await db.commit()


async def get_designs(screen_id: str, org_id: int = DEFAULT_ORG_ID) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, matrix, created_at FROM designs "
            "WHERE org_id=? AND screen_id=? ORDER BY created_at DESC",
            (org_id, screen_id),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {"id": r["id"], "name": r["name"],
         "matrix": json.loads(r["matrix"]), "created_at": r["created_at"]}
        for r in rows
    ]


async def get_design(design_id: int, org_id: int = DEFAULT_ORG_ID) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, matrix, created_at FROM designs WHERE id=? AND org_id=?",
            (design_id, org_id),
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        return None
    return {"id": row["id"], "name": row["name"],
            "matrix": json.loads(row["matrix"]), "created_at": row["created_at"]}


async def add_design(screen_id: str, name: str, matrix: list, org_id: int = DEFAULT_ORG_ID) -> int:
    async with _connect() as db:
        cur = await db.execute(
            "INSERT INTO designs (org_id, screen_id, name, matrix) VALUES (?,?,?,?)",
            (org_id, screen_id, name, json.dumps(matrix)),
        )
        await db.commit()
        return cur.lastrowid


async def update_design(design_id: int, name: str, matrix: list, org_id: int = DEFAULT_ORG_ID):
    async with _connect() as db:
        await db.execute(
            "UPDATE designs SET name=?, matrix=? WHERE id=? AND org_id=?",
            (name, json.dumps(matrix), design_id, org_id),
        )
        await db.commit()


async def delete_design(design_id: int, org_id: int = DEFAULT_ORG_ID):
    async with _connect() as db:
        await db.execute("DELETE FROM designs WHERE id=? AND org_id=?", (design_id, org_id))
        await db.commit()


# ── Auth sessions ─────────────────────────────────────────────────────────────

async def add_session(token: str, expires_at: str, org_id: int = DEFAULT_ORG_ID):
    async with _connect() as db:
        await db.execute(
            "INSERT INTO auth_sessions (token, org_id, expires_at) VALUES (?, ?, ?)",
            (token, org_id, expires_at),
        )
        # Opportunistic cleanup of expired sessions
        await db.execute("DELETE FROM auth_sessions WHERE expires_at < datetime('now')")
        await db.commit()


async def get_session(token: str) -> bool:
    """True when the token exists and has not expired."""
    async with _connect() as db:
        async with db.execute(
            "SELECT 1 FROM auth_sessions WHERE token=? AND expires_at >= datetime('now')",
            (token,),
        ) as cur:
            return await cur.fetchone() is not None


async def remove_session(token: str):
    async with _connect() as db:
        await db.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
        await db.commit()


async def clear_sessions(org_id: int = DEFAULT_ORG_ID):
    """Log everyone out — used when the password changes or auth is disabled."""
    async with _connect() as db:
        await db.execute("DELETE FROM auth_sessions WHERE org_id=?", (org_id,))
        await db.commit()


# ── Persisted display state ───────────────────────────────────────────────────

async def save_screen_state(screen_id: str, state: dict, org_id: int = DEFAULT_ORG_ID):
    async with _connect() as db:
        await db.execute(
            "INSERT OR REPLACE INTO screen_state (org_id, screen_id, state, updated_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (org_id, screen_id, json.dumps(state)),
        )
        await db.commit()


async def load_screen_state(screen_id: str, org_id: int = DEFAULT_ORG_ID) -> dict | None:
    async with _connect() as db:
        async with db.execute(
            "SELECT state FROM screen_state WHERE org_id=? AND screen_id=?",
            (org_id, screen_id),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None


async def delete_screen_state(screen_id: str, org_id: int = DEFAULT_ORG_ID):
    async with _connect() as db:
        await db.execute(
            "DELETE FROM screen_state WHERE org_id=? AND screen_id=?", (org_id, screen_id))
        await db.commit()
