# FlipperBoards Plugin Development Guide

Plugins extend FlipperBoards with new display modes — things like "Now Playing on Spotify", "YouTube Subscriber Count", "Stock Ticker", or anything else you can fetch from an API. The built-in modes (Clock, Weather, News, etc.) are themselves registered through the same system.

---

## Quick Start

1. Create your plugin directory inside `backend/plugins/`:

```
backend/plugins/
  myapp/
    __init__.py
```

2. Write your plugin:

```python
# backend/plugins/myapp/__init__.py
from plugins.base import FlipperPlugin
from mode_registry import ModeDefinition
from charmap import text_to_matrix

class MyAppPlugin(FlipperPlugin):
    name = "myapp"
    version = "0.1.0"

    @property
    def modes(self):
        return [
            ModeDefinition(
                id="myapp",
                label="My App",
                icon="🚀",
                description="Shows data from My App",
                config_schema={
                    "api_key": {
                        "label": "API Key",
                        "type": "string",
                        "secret": True,
                        "placeholder": "sk-...",
                        "help": "Get a key at myapp.com/api",
                    },
                },
                render=self._render,
            )
        ]

    async def _render(self, rows: int, cols: int, config: dict, settings: dict) -> list[list[int]]:
        api_key = config.get("api_key", "")
        if not api_key:
            return text_to_matrix("MYAPP: ADD API KEY IN MODES CONFIG", rows, cols)
        # ... fetch data, build text, return matrix
        return text_to_matrix("HELLO FROM MYAPP", rows, cols)

plugin = MyAppPlugin()  # required — the loader looks for this name
```

3. Enable the plugin:

```bash
# .env or environment variable
FB_PLUGINS=myapp

# Multiple plugins
FB_PLUGINS=myapp,youtube,myotherplugin
```

4. Restart the server. Your mode appears in the **Modes** tab of the remote control, with a ⚙ icon to configure it.

---

## Plugin Interface

### `FlipperPlugin` base class

| Property / Method | Description |
|---|---|
| `name: str` | Unique plugin identifier (snake_case) |
| `version: str` | Semver string |
| `required: bool` | If `True`, startup fails when the plugin isn't loaded |
| `modes` property | Returns list of `ModeDefinition` objects |
| `on_db_init(db)` | Called during DB init — create plugin-specific tables here |
| `on_startup(app)` | Called after DB init — register FastAPI routes here |
| `on_shutdown()` | Called on app shutdown — close connections, etc. |

### `ModeDefinition`

```python
ModeDefinition(
    id: str,          # unique mode key, used as DB identifier (e.g. "spotify_now_playing")
    label: str,       # display name in the UI (e.g. "Spotify: Now Playing")
    icon: str,        # emoji shown on the mode card (e.g. "🎵")
    description: str, # one-line description shown below the icon
    config_schema: dict,   # see Config Schema below
    render: callable, # async render function — see Render Function below
)
```

### Render Function

```python
async def render(
    rows: int,          # display rows (default 6)
    cols: int,          # display columns (default 22)
    config: dict,       # per-mode config saved by the user (from config_schema)
    settings: dict,     # global app settings (timezone, units, etc.)
) -> list[list[int]]    # Vestaboard character matrix
```

The return value is a 2D array of character codes:

| Code | Character |
|------|-----------|
| 0 | Blank |
| 1–26 | A–Z |
| 27–36 | 1–0 |
| 37–62 | Punctuation |
| 71–77 | Color tiles (red, orange, yellow, green, blue, violet, white) |

Use `text_to_matrix(text, rows, cols)` from `charmap` for most cases — it handles wrapping, centering, and character mapping automatically.

### Config Schema

The `config_schema` dict defines what config fields appear in the UI when a user clicks ⚙ on your mode card. Each key becomes a field:

```python
config_schema = {
    "field_key": {
        "label": str,        # field label shown in UI
        "type": str,         # "string" | "number" | "boolean" | "select"
        "secret": bool,      # render as password field (optional, default False)
        "placeholder": str,  # input placeholder text (optional)
        "help": str,         # small help text below the field (optional)
        "default": any,      # default value (optional)

        # for type="select" only:
        "options": [
            {"value": "opt1", "label": "Option 1"},
            {"value": "opt2", "label": "Option 2"},
        ],
    },
}
```

Config values are stored per-screen in the `screen_modes` table. Each screen can have different config for the same mode.

---

## Lifecycle Hooks

### `on_db_init(db)` — Add plugin tables

```python
async def on_db_init(self, db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS spotify_tokens (
            screen_id  TEXT NOT NULL,
            org_id     INTEGER NOT NULL DEFAULT 1,
            token      TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            PRIMARY KEY (screen_id, org_id)
        )
    """)
```

Always include `org_id INTEGER NOT NULL DEFAULT 1` in plugin tables — this makes your plugin SaaS-compatible when FlipperBoards Cloud launches.

### `on_startup(app)` — Register routes

```python
async def on_startup(self, app):
    from fastapi import APIRouter
    router = APIRouter(prefix="/api/spotify")

    @router.get("/auth")
    async def spotify_auth():
        return {"url": "https://accounts.spotify.com/authorize?..."}

    app.include_router(router)
```

### `on_shutdown()` — Cleanup

```python
async def on_shutdown(self):
    if self._http_client:
        await self._http_client.aclose()
```

---

## Tips

**Caching** — Your render function is called on every rotation cycle. Cache expensive API responses to avoid hammering rate limits:

```python
import time

class MyPlugin(FlipperPlugin):
    _cache: dict = {}
    _cache_until: float = 0

    async def _render(self, rows, cols, config, settings):
        now = time.time()
        key = config.get("channel_id", "")
        if now < self._cache_until and key in self._cache:
            return self._cache[key]

        result = await self._fetch(config)
        self._cache[key] = result
        self._cache_until = now + 300  # cache 5 minutes
        return result
```

**Error handling** — Always catch exceptions and return a legible error matrix instead of raising:

```python
try:
    data = await fetch_something()
except Exception:
    return text_to_matrix("MYAPP: FETCH ERROR", rows, cols)
```

**httpx is available** — `httpx` is in the project dependencies. Use `httpx.AsyncClient` for async HTTP:

```python
import httpx

async with httpx.AsyncClient(timeout=8.0) as client:
    r = await client.get("https://api.example.com/data", params={"key": api_key})
    r.raise_for_status()
    return r.json()
```

**SaaS compatibility** — Include `org_id` in any DB tables you create (see above). Use `DEFAULT_ORG_ID` from `database` when inserting:

```python
from database import DEFAULT_ORG_ID

await db.execute("INSERT INTO my_table (org_id, ...) VALUES (?, ...)", (DEFAULT_ORG_ID, ...))
```

---

## Example Plugin: YouTube

A complete, working example is included at `backend/plugins/youtube/__init__.py`. It shows:
- `config_schema` with `string`, `secret`, and `select` field types
- Async HTTP with `httpx`
- Error handling with user-friendly matrix messages
- Count formatting (1.2M, 345K, etc.)

---

## Sharing Your Plugin

Once your plugin works, we'd love to see it! Open a pull request or post in Discussions with:
- What it does
- Required API keys / accounts
- Example screenshot

Community plugins will be listed in the README.
