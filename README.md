# FlipperBoards

A Vestaboard-style split-flap display application built for Raspberry Pi + TV. Remotely controlled from any phone or computer on your network via a mobile-friendly web UI. Multiple independent screens, a full REST API, and an image playlist make it useful for home automation dashboards, office lobbies, event backdrops, or Zoom call backgrounds.

![Split-flap display showing a clock](https://user-images.githubusercontent.com/placeholder/flipperboards-preview.png)

---

## Features

- **Authentic split-flap animation** — CSS 3D fold/rise keyframes, Web Audio synthesized flip sounds, per-column stagger timing
- **Vestaboard character set** — codes 0–77 (blank, A–Z, 0–9, punctuation, 7 color tiles)
- **Multiple independent screens** — each screen has its own URL, mode rotation, playlist, and WebSocket group; cast any screen to any TV
- **Six auto-rotation modes** — Clock, Weather, News, Quotes, Calendar, Text Messages
- **Content playlist** — arrange any content in any order with per-item durations; mixes modes, custom text, and photos
- **Image display** — four modes: Photo Split (puzzle), Full Color (RGB mosaic), 8-Color Mosaic (Vestaboard palette), Monochrome (character density)
- **Physical frame mode** — configurable gap width and color between tiles to simulate wooden dowel rods
- **Theming** — 5 built-in presets + custom color pickers for tile text, tile background, and board background
- **REST API** — push any content programmatically
- **WebSocket sync** — all clients on a screen see changes instantly
- **Kiosk mode** — `?kiosk=1` hides all controls for clean TV display
- **Wake Lock** — prevents TV screen from sleeping while the display view is open

---

## Quick Start

**Requirements:** Python 3.11+, Node.js 18+

```bash
git clone https://github.com/mikekmiller/flipperboards
cd FlipperBoards
chmod +x setup.sh && ./setup.sh
```

Start the server:
```bash
cd backend
source .venv/bin/activate
python main.py
```

| URL | Purpose |
|-----|---------|
| `http://<pi-ip>:8000/display` | Full-screen display (open in TV browser) |
| `http://<pi-ip>:8000/` | Remote control (open on phone/computer) |
| `http://<pi-ip>:8000/display?screen=lobby` | Display for a specific named screen |
| `http://<pi-ip>:8000/?screen=lobby` | Remote control for a specific screen |
| `http://<pi-ip>:8000/display?kiosk=1` | Kiosk mode — no UI chrome, just the display |

---

## Raspberry Pi Auto-Start

```bash
# Edit WorkingDirectory and User in flipperboards.service, then:
sudo cp flipperboards.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable flipperboards
sudo systemctl start flipperboards

# View logs
sudo journalctl -u flipperboards -f
```

## Docker

```bash
docker compose up -d
```

The compose file maps port 8000 and mounts `./backend/flipperboards.db` and `./backend/uploads` as volumes so data survives container restarts.

---

## Multiple Screens

Each screen is an independent display with its own:
- Mode rotation and enabled modes
- Content playlist
- Text message queue
- Photo/image content
- WebSocket subscriber group

Create and manage screens in the **Screens** tab of the remote control, or via the API:

```http
GET    /api/screens                    # List all screens
POST   /api/screens                    # Create a screen
PUT    /api/screens/{id}               # Rename or resize
DELETE /api/screens/{id}               # Delete (cannot delete "main")
```

Example — create a "lobby" screen:
```bash
curl -X POST http://pi:8000/api/screens \
  -H 'Content-Type: application/json' \
  -d '{"id":"lobby","name":"Lobby Display","rows":6,"cols":22}'
```

Then open `http://pi:8000/display?screen=lobby` on the lobby TV.

Most endpoints accept a `?screen=<id>` query parameter (default: `main`).

---

## Display Modes

Enable and order modes in the **Modes** tab. The rotation interval is set in **Settings**.

| Mode | Description |
|------|-------------|
| Clock | Live time and date; updates every second |
| Weather | Current conditions — requires a location (API key optional) |
| News | Top headlines — falls back to BBC/Reuters RSS with no API key |
| Quotes | Rotating inspirational quotes (ZenQuotes API or built-in fallback) |
| Calendar | Upcoming events from any iCal URL (Google Calendar, Outlook, etc.) |
| Text Messages | Custom messages managed in the **Text** tab |

---

## Content Playlist

The **Playlist** tab lets you build an ordered sequence of any content type. When the playlist has items, it completely replaces the Modes rotation. Each item has its own display duration. The sequence loops forever.

**Item types:**
- **Mode** — runs a built-in mode (Clock, Weather, News, Quotes, Calendar, Text Messages)
- **Text** — displays a specific custom message
- **Photo** — shows an uploaded photo split across all tiles

**Example sequence:** `Text (20s) → Weather (30s) → News (30s) → Text (20s) → Photo (15s) → repeat`

Remove all playlist items to return to the Modes rotation.

**Controls:**
- Click a duration badge to edit it inline
- ↑ / ↓ buttons to reorder
- **Play Now** — jump to item 1 immediately and restart the timer
- **Clear All** — remove everything and return to mode rotation

---

## Image Display

Push an image from the **Image** tab for an immediate one-shot display.

| Mode | Description |
|------|-------------|
| **Photo Split** | Actual photo divided tile-by-tile (puzzle effect) — great for logos on Zoom calls |
| **Full Color** | Each tile gets its average RGB color — smooth photo mosaic |
| **8-Color Mosaic** | Nearest Vestaboard color per tile — bold graphic look |
| **Monochrome** | Brightness mapped to character density — ASCII art aesthetic |

Images are processed in the browser (Canvas API) — no server-side image library required for color/mono modes. Photo Split uploads to the server and serves the image via URL so all clients share the same source.

---

## Physical Frame Mode

Enable in **Settings → Physical Frame**. Simulates wooden dowel rods separating tiles:

- **Divider width** — gap in pixels between tiles (0–20)
- **Divider color** — presets: Black, Dark Wood, Light Wood, Walnut, Steel; or custom color

Pair with a larger `tileSize` and a dark `bgColor` for the most realistic look.

---

## REST API

All endpoints accept `?screen=<id>` (default: `main`).

### Push content immediately

```http
POST /api/display/text
{ "text": "HELLO WORLD" }
```

```http
POST /api/display/matrix
{ "matrix": [[1,2,3,...], ...] }
```
Character codes: `0`=blank, `1–26`=A–Z, `27–36`=1–0, `37–44`=punctuation, `71–77`=color tiles (red, orange, yellow, green, blue, violet, white)

```http
POST /api/display/color-matrix
{ "color_matrix": [["#ff0000","#00ff00",...], ...] }
```
Each cell is a CSS hex color string. Grid dimensions are inferred from the matrix.

```http
POST /api/display/photo          # multipart/form-data, field: file
POST /api/display/blank          # clear to blank
POST /api/display/next           # advance to next mode/playlist item
GET  /api/state                  # current display state
```

### File upload (no display effect)

```http
POST /api/upload                 # multipart/form-data, field: file
→ { "url": "/uploads/abc123.jpg" }
```

### Playlist

```http
GET    /api/playlist             # list items (ordered)
POST   /api/playlist             # add item
PUT    /api/playlist/{id}        # update item
DELETE /api/playlist/{id}        # remove item
POST   /api/playlist/reorder     # { "ids": [3,1,2] } — full reorder
POST   /api/playlist/clear       # remove all items
POST   /api/playlist/play        # jump to item 1 now
```

Add a mode item:
```bash
curl -X POST http://pi:8000/api/playlist \
  -H 'Content-Type: application/json' \
  -d '{"type":"mode","content":{"mode":"weather"},"duration":30}'
```

Add a text item:
```bash
curl -X POST http://pi:8000/api/playlist \
  -H 'Content-Type: application/json' \
  -d '{"type":"text","content":{"text":"Welcome to FlipperBoards"},"duration":20}'
```

Add a photo item (upload first):
```bash
URL=$(curl -s -F file=@logo.jpg http://pi:8000/api/upload | jq -r .url)
curl -X POST http://pi:8000/api/playlist \
  -H 'Content-Type: application/json' \
  -d "{\"type\":\"photo\",\"content\":{\"url\":\"$URL\"},\"duration\":15}"
```

### Modes

```http
GET  /api/modes                  # list modes + enabled status
PUT  /api/modes/{mode}           # enable/disable/configure a mode
```

```bash
curl -X PUT http://pi:8000/api/modes/weather \
  -H 'Content-Type: application/json' \
  -d '{"mode":"weather","enabled":true,"sort_order":2,"config":{}}'
```

### Text messages

```http
GET    /api/messages             # list messages
POST   /api/messages             # { "text": "...", "duration": 30 }
DELETE /api/messages/{id}        # remove message
```

### Settings

```http
GET  /api/settings               # all settings as key/value object
PUT  /api/settings               # update any subset
```

```bash
curl -X PUT http://pi:8000/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"weather_location":"Chicago,US","timezone":"America/Chicago"}'
```

---

## Settings Reference

All settings are persisted in SQLite (`flipperboards.db`).

| Key | Default | Description |
|-----|---------|-------------|
| `rotation_interval` | `30` | Seconds between mode/playlist advances |
| `timezone` | `America/Chicago` | IANA timezone (e.g. `America/New_York`) |
| `clock_format` | `12h` | `12h` or `24h` |
| `show_date` | `true` | Show date below time in clock mode |
| `tile_color` | `#ffffff` | Character/foreground color |
| `tile_bg_color` | `#2a2a2a` | Tile background color |
| `bg_color` | `#1a1a1a` | Board background color |
| `sound_enabled` | `true` | Flip sound synthesis on display page |
| `physical_mode` | `false` | Physical frame rendering mode |
| `divider_width` | `4` | Pixels between tiles (0–20) |
| `divider_color` | `#111111` | Color of gaps between tiles |
| `weather_api_key` | — | OpenWeatherMap API key (optional) |
| `weather_location` | — | Location for weather, e.g. `Portland,US` |
| `weather_units` | `imperial` | `imperial` or `metric` |
| `news_api_key` | — | NewsAPI key (optional) |
| `news_categories` | `["technology","general"]` | JSON array of news categories |
| `calendar_ical_url` | — | iCal URL (Google Calendar secret address, etc.) |

---

## API Keys

All API keys are optional — the app works without any of them using free fallbacks.

| Service | Optional | Fallback | Where to get a key |
|---------|----------|----------|--------------------|
| Weather | Yes | Open-Meteo (no key required) | [openweathermap.org/api](https://openweathermap.org/api) |
| News | Yes | BBC & Reuters RSS feeds | [newsapi.org](https://newsapi.org) |
| Calendar | — | (no iCal = no calendar content) | Google Calendar → Settings → Secret iCal address |

---

## Character Code Reference

The Vestaboard character set (codes 0–77):

| Range | Characters |
|-------|-----------|
| 0 | Blank |
| 1–26 | A–Z |
| 27–36 | 1–0 (digits) |
| 37 | `!` |
| 38 | `@` |
| 39–44 | `#`, `$`, `(`, `)`, `-`, `+` |
| 45 | `&` |
| 46 | `=` |
| 47 | `;` |
| 48 | `:` |
| 53 | `"` |
| 54 | `'` (apostrophe) |
| 55 | `%` |
| 56 | `,` |
| 57 | `.` |
| 59 | `/` |
| 60 | `\` |
| 62 | `?` |
| 71 | Red tile |
| 72 | Orange tile |
| 73 | Yellow tile |
| 74 | Green tile |
| 75 | Blue tile |
| 76 | Violet tile |
| 77 | White tile |

---

## Architecture

```
FlipperBoards/
├── backend/
│   ├── main.py              # FastAPI app, WebSocket, rotation loop, API routes
│   ├── database.py          # SQLite schema + async CRUD (aiosqlite)
│   ├── websocket_manager.py # Per-screen WebSocket connection groups
│   ├── charmap.py           # Vestaboard character set, text→matrix conversion
│   ├── config.py            # Settings via environment variables (FB_ prefix)
│   ├── services/
│   │   ├── clock.py         # Live time/date matrix rendering
│   │   ├── weather.py       # OpenWeatherMap + Open-Meteo fallback
│   │   ├── news.py          # NewsAPI + RSS fallback (no feedparser dependency)
│   │   ├── quotes.py        # ZenQuotes API + built-in fallback list
│   │   ├── calendar_svc.py  # iCal parsing via httpx
│   │   └── text_svc.py      # Rotating text messages
│   ├── uploads/             # Uploaded images (served as /uploads/*)
│   └── flipperboards.db     # SQLite database (auto-created on first run)
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── DisplayView.jsx        # Full-screen display, wake lock, kiosk mode
│       │   ├── SplitFlapDisplay.jsx   # Grid renderer — FlapTile / ColorTile / PhotoTile
│       │   ├── FlapTile.jsx           # CSS 3D animation + Web Audio flip sound
│       │   ├── ColorTile.jsx          # RGB color tile with smooth lerp transitions
│       │   ├── PhotoTile.jsx          # CSS background-position photo-split tile
│       │   └── remote/
│       │       ├── RemoteControl.jsx  # Tabbed remote control shell
│       │       ├── ScreenManager.jsx  # Create/edit/delete screens
│       │       ├── ModeSelector.jsx   # Enable/disable/reorder modes
│       │       ├── TextInput.jsx      # Text message queue manager
│       │       ├── ImageUpload.jsx    # Image push (4 modes)
│       │       ├── UniversalPlaylist.jsx # Content playlist builder
│       │       └── SettingsPanel.jsx  # Theme + physical frame settings
│       ├── hooks/
│       │   ├── useWebSocket.js        # WebSocket with auto-reconnect
│       │   └── useDisplayState.js     # Unified display state from WebSocket
│       └── utils/
│           ├── audio.js               # Web Audio synthesized flip sound
│           ├── charmap.js             # Client-side Vestaboard character map
│           └── imageToMatrix.js       # Canvas-based image → matrix/color-matrix
│
├── setup.sh                 # Quick install for Raspberry Pi / Linux
├── flipperboards.service    # systemd service file
├── Dockerfile
└── docker-compose.yml
```

### WebSocket message types

| Type | Direction | Payload |
|------|-----------|---------|
| `display_update` | server→client | `{matrix, rows, cols, mode, screen_id}` |
| `image_update` | server→client | `{color_matrix, rows, cols, screen_id}` |
| `photo_split` | server→client | `{image_url, rows, cols, screen_id}` |
| `settings_update` | server→client | `{settings}` |
| `modes_update` | server→client | `{modes}` |
| `screens_update` | server→client | `{screens}` |

---

## Environment Variables

Override defaults with `FB_` prefixed environment variables:

```bash
FB_HOST=0.0.0.0
FB_PORT=8000
FB_DB_PATH=flipperboards.db
FB_DEFAULT_ROWS=6
FB_DEFAULT_COLS=22
```

---

## References

See `References/SOURCES.md` for open-source Vestaboard projects used as inspiration.
