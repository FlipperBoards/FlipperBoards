import aiosqlite
import json
from config import settings

DB_PATH = settings.db_path

DEFAULT_ORG_ID = 1


# ── Schema init & migration ───────────────────────────────────────────────────

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await _create_tables(db)
        await _migrate(db)
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
            id      TEXT    NOT NULL,
            org_id  INTEGER NOT NULL DEFAULT 1,
            name    TEXT    NOT NULL,
            rows    INTEGER NOT NULL DEFAULT 6,
            cols    INTEGER NOT NULL DEFAULT 22,
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
            sort_order  INTEGER NOT NULL DEFAULT 0
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


async def _migrate(db: aiosqlite.Connection):
    """Add org_id to legacy tables that predate multi-tenant support."""

    # display_settings: old schema had (key TEXT PRIMARY KEY, value TEXT).
    # New schema needs (org_id, key) composite PK. Rebuild the table if needed.
    async with db.execute("PRAGMA table_info(display_settings)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    if "org_id" not in cols and cols:
        await db.execute("ALTER TABLE display_settings RENAME TO _display_settings_legacy")
        await db.execute("""
            CREATE TABLE display_settings (
                org_id  INTEGER NOT NULL DEFAULT 1,
                key     TEXT    NOT NULL,
                value   TEXT    NOT NULL,
                PRIMARY KEY (org_id, key)
            )
        """)
        await db.execute(
            "INSERT OR IGNORE INTO display_settings (org_id, key, value) "
            "SELECT 1, key, value FROM _display_settings_legacy"
        )
        await db.execute("DROP TABLE _display_settings_legacy")

    # screens: old schema had id TEXT PRIMARY KEY with no org_id
    async with db.execute("PRAGMA table_info(screens)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    if "org_id" not in cols and cols:
        # Rebuild — can't add a NOT NULL column without a default via ALTER in all SQLite versions
        await db.execute("ALTER TABLE screens RENAME TO _screens_legacy")
        await db.execute("""
            CREATE TABLE screens (
                id      TEXT    NOT NULL,
                org_id  INTEGER NOT NULL DEFAULT 1,
                name    TEXT    NOT NULL,
                rows    INTEGER NOT NULL DEFAULT 6,
                cols    INTEGER NOT NULL DEFAULT 22,
                PRIMARY KEY (org_id, id)
            )
        """)
        await db.execute(
            "INSERT OR IGNORE INTO screens (id, org_id, name, rows, cols) "
            "SELECT id, 1, name, rows, cols FROM _screens_legacy"
        )
        await db.execute("DROP TABLE _screens_legacy")

    # screen_modes: old PK was (screen_id, mode)
    async with db.execute("PRAGMA table_info(screen_modes)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    if "org_id" not in cols and cols:
        await db.execute("ALTER TABLE screen_modes RENAME TO _screen_modes_legacy")
        await db.execute("""
            CREATE TABLE screen_modes (
                org_id      INTEGER NOT NULL DEFAULT 1,
                screen_id   TEXT    NOT NULL,
                mode        TEXT    NOT NULL,
                config      TEXT    NOT NULL DEFAULT '{}',
                enabled     INTEGER NOT NULL DEFAULT 0,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (org_id, screen_id, mode)
            )
        """)
        await db.execute(
            "INSERT OR IGNORE INTO screen_modes (org_id, screen_id, mode, config, enabled, sort_order) "
            "SELECT 1, screen_id, mode, config, enabled, sort_order FROM _screen_modes_legacy"
        )
        await db.execute("DROP TABLE _screen_modes_legacy")

    # text_messages and playlist_items: simple column additions are safe
    for table in ("text_messages", "playlist_items"):
        async with db.execute(f"PRAGMA table_info({table})") as cur:
            cols = {row[1] for row in await cur.fetchall()}
        if "org_id" not in cols and cols:
            await db.execute(
                f"ALTER TABLE {table} ADD COLUMN org_id INTEGER NOT NULL DEFAULT 1"
            )


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
        "divider_width": "4",
        "divider_color": "#111111",
        "physical_mode": "false",
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
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT key, value FROM display_settings WHERE org_id = ?", (org_id,)
        ) as cur:
            rows = await cur.fetchall()
    return {row["key"]: row["value"] for row in rows}


async def update_setting(key: str, value: str, org_id: int = DEFAULT_ORG_ID):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO display_settings (org_id, key, value) VALUES (?, ?, ?)",
            (org_id, key, value)
        )
        await db.commit()


# ── Organizations ─────────────────────────────────────────────────────────────

async def get_organization(org_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, slug, created_at FROM organizations WHERE id = ?", (org_id,)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


# ── Screens ───────────────────────────────────────────────────────────────────

async def get_screens(org_id: int = DEFAULT_ORG_ID) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, rows, cols FROM screens WHERE org_id = ? ORDER BY id",
            (org_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def get_screen(screen_id: str, org_id: int = DEFAULT_ORG_ID) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, rows, cols FROM screens WHERE id = ? AND org_id = ?",
            (screen_id, org_id)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def create_screen(
    screen_id: str, name: str, rows: int = 6, cols: int = 22, org_id: int = DEFAULT_ORG_ID
):
    async with aiosqlite.connect(DB_PATH) as db:
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
    screen_id: str, name: str, rows: int, cols: int, org_id: int = DEFAULT_ORG_ID
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE screens SET name=?, rows=?, cols=? WHERE id=? AND org_id=?",
            (name, rows, cols, screen_id, org_id)
        )
        await db.commit()


async def delete_screen(screen_id: str, org_id: int = DEFAULT_ORG_ID):
    if screen_id == "main":
        raise ValueError("Cannot delete the main screen")
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM text_messages WHERE id = ? AND org_id = ?", (msg_id, org_id)
        )
        await db.commit()


# ── Universal content playlist ────────────────────────────────────────────────

async def get_playlist_items(
    screen_id: str, org_id: int = DEFAULT_ORG_ID
) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, type, content, duration, sort_order FROM playlist_items "
            "WHERE screen_id=? AND org_id=? ORDER BY sort_order, id",
            (screen_id, org_id)
        ) as cur:
            rows = await cur.fetchall()
    return [
        {
            "id": row["id"],
            "type": row["type"],
            "content": json.loads(row["content"]),
            "duration": row["duration"],
            "sort_order": row["sort_order"],
        }
        for row in rows
    ]


async def add_playlist_item(
    screen_id: str, item_type: str, content: dict, duration: int,
    org_id: int = DEFAULT_ORG_ID,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "INSERT INTO playlist_items (org_id, screen_id, type, content, duration, sort_order) "
            "VALUES (?, ?, ?, ?, ?, "
            "(SELECT COALESCE(MAX(sort_order), 0) + 1 FROM playlist_items WHERE screen_id=? AND org_id=?))",
            (org_id, screen_id, item_type, json.dumps(content), duration, screen_id, org_id)
        ) as cur:
            row_id = cur.lastrowid
        await db.commit()
    return row_id


async def update_playlist_item(
    item_id: int, item_type: str, content: dict, duration: int,
    org_id: int = DEFAULT_ORG_ID,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE playlist_items SET type=?, content=?, duration=? WHERE id=? AND org_id=?",
            (item_type, json.dumps(content), duration, item_id, org_id)
        )
        await db.commit()


async def remove_playlist_item(item_id: int, org_id: int = DEFAULT_ORG_ID):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM playlist_items WHERE id=? AND org_id=?", (item_id, org_id)
        )
        await db.commit()


async def clear_playlist_items(screen_id: str, org_id: int = DEFAULT_ORG_ID):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM playlist_items WHERE screen_id=? AND org_id=?", (screen_id, org_id)
        )
        await db.commit()


async def reorder_playlist_items(
    screen_id: str, ordered_ids: list[int], org_id: int = DEFAULT_ORG_ID
):
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO image_library (org_id, filename, name, folder, size, content_type) "
            "VALUES (?,?,?,?,?,?)",
            (org_id, filename, name, folder, size, content_type),
        )
        await db.commit()
        return cur.lastrowid


async def get_images(folder: str | None = None, org_id: int = DEFAULT_ORG_ID) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE image_library SET {cols} WHERE id=? AND org_id=?", vals)
        await db.commit()


async def delete_image(image_id: int, org_id: int = DEFAULT_ORG_ID) -> str | None:
    """Removes the DB record and returns the filename (for disk cleanup), or None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT filename FROM image_library WHERE id=? AND org_id=?", (image_id, org_id)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        await db.execute("DELETE FROM image_library WHERE id=? AND org_id=?", (image_id, org_id))
        await db.commit()
        return row[0]


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp"}

async def remove_playlist_items_by_image_url(image_url: str, org_id: int = DEFAULT_ORG_ID):
    """Delete playlist items whose content JSON contains the given image URL."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM playlist_items WHERE org_id=? AND content LIKE ?",
            (org_id, f'%{image_url}%'),
        )
        await db.commit()


async def get_designs(screen_id: str, org_id: int = DEFAULT_ORG_ID) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO designs (org_id, screen_id, name, matrix) VALUES (?,?,?,?)",
            (org_id, screen_id, name, json.dumps(matrix)),
        )
        await db.commit()
        return cur.lastrowid


async def update_design(design_id: int, name: str, matrix: list, org_id: int = DEFAULT_ORG_ID):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE designs SET name=?, matrix=? WHERE id=? AND org_id=?",
            (name, json.dumps(matrix), design_id, org_id),
        )
        await db.commit()


async def delete_design(design_id: int, org_id: int = DEFAULT_ORG_ID):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM designs WHERE id=? AND org_id=?", (design_id, org_id))
        await db.commit()


async def migrate_existing_uploads(upload_dir: str, org_id: int = DEFAULT_ORG_ID):
    """One-time: register files already on disk that have no DB record yet."""
    import os, mimetypes
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT filename FROM image_library WHERE org_id=?", (org_id,)) as cur:
            known = {row[0] for row in await cur.fetchall()}
        rows = []
        for name in os.listdir(upload_dir):
            if name in known or os.path.splitext(name)[1].lower() not in _IMAGE_EXTS:
                continue
            path = os.path.join(upload_dir, name)
            if not os.path.isfile(path):
                continue
            rows.append((org_id, name, '', '', os.path.getsize(path),
                         mimetypes.guess_type(name)[0] or 'image/jpeg'))
        if rows:
            await db.executemany(
                "INSERT OR IGNORE INTO image_library "
                "(org_id, filename, name, folder, size, content_type) VALUES (?,?,?,?,?,?)",
                rows,
            )
            await db.commit()
