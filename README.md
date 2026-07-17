# FlipperBoards

A Vestaboard-style split-flap display application. Run it on a Raspberry Pi connected to a TV, or anywhere Docker runs. Control it from any phone or computer on your network via a mobile-friendly web UI.

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
- **Wake Lock** — prevents the TV screen from sleeping while the display view is open

---

## Self-Hosting

There are two supported self-host options.

---

### Option 1 — Raspberry Pi (bare metal)

**Requirements:** Raspberry Pi 3B+ or newer, Raspberry Pi OS (64-bit recommended), Python 3.11+, Node.js 18+

```bash
# Install Python and Node if needed
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Clone and set up
git clone https://github.com/FlipperBoards/FlipperBoards
cd FlipperBoards
chmod +x setup.sh && ./setup.sh
```

**Start the server:**
```bash
cd backend
source .venv/bin/activate
python main.py
```

#### Auto-start with systemd

Edit `flipperboards.service` if your username or install path differs from the defaults (`pi` / `/home/pi/FlipperBoards`), then:

```bash
sudo cp flipperboards.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable flipperboards
sudo systemctl start flipperboards
```

Useful commands:
```bash
sudo systemctl status flipperboards   # check status
sudo journalctl -u flipperboards -f   # live logs
sudo systemctl restart flipperboards  # restart after config change
```

---

### Option 2 — Docker

**Requirements:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows) or Docker Engine + Docker Compose (Linux)

```bash
git clone https://github.com/FlipperBoards/FlipperBoards
cd FlipperBoards
docker compose up -d
```

That's it. The image builds automatically on first run.

**Data is persisted** in a `./data/` folder next to the compose file:
- `./data/flipperboards.db` — SQLite database (settings, screens, playlists)
- `./data/uploads/` — uploaded photos

```bash
docker compose logs -f         # live logs
docker compose restart         # restart
docker compose pull && docker compose up -d  # update
docker compose down            # stop
```

---

### Option 3 — Unraid

Install from Community Applications (search "FlipperBoards"), or add the
template manually: **Docker → Add Container → Template** and point at
`unraid/FlipperBoards.xml` from this repo. All data lives in
`/mnt/user/appdata/flipperboards`.

---

### Kiosk display clients

The server can run anywhere (Unraid, Docker, a Pi) — anything with a browser
can be a display. Two purpose-built clients are included:

| Client | Where | Setup |
|--------|-------|-------|
| **Pi kiosk** | Raspberry Pi wired to a TV — boots straight into fullscreen Chromium | [`deploy/pi-kiosk/`](deploy/pi-kiosk/) |
| **Android app** | Android TV, tablets, cheap HDMI sticks | [`android/`](android/) — APK built by CI |

Both point at the server over the network; the display updates live via
WebSocket.

---

### Accessing the app

Once running (either option), open these URLs — replace `<ip>` with your Pi's IP or `localhost` if running locally:

| URL | Purpose |
|-----|---------|
| `http://<ip>:8000/display` | Full-screen display — open in the TV's browser |
| `http://<ip>:8000/` | Remote control — open on your phone or computer |
| `http://<ip>:8000/display?screen=lobby` | Display for a named screen |
| `http://<ip>:8000/?screen=lobby` | Remote control for a named screen |
| `http://<ip>:8000/display?kiosk=1` | Kiosk mode — no UI chrome |

---

## Multiple Screens

Each screen is an independent display with its own mode rotation, playlist, text queue, and WebSocket group. Create and manage screens in the **Screens** tab of the remote control, or via the API:

```bash
curl -X POST http://<ip>:8000/api/screens \
  -H 'Content-Type: application/json' \
  -d '{"id":"lobby","name":"Lobby Display","rows":6,"cols":22}'
```

Then open `http://<ip>:8000/display?screen=lobby` on the lobby TV and `http://<ip>:8000/?screen=lobby` on your phone to control it.

---

## Display Modes

Enable and order modes in the **Modes** tab. The rotation interval is set in **Settings**.

| Mode | Description |
|------|-------------|
| Clock | Live time and date — updates every second |
| Weather | Current conditions — requires a location (API key optional) |
| News | Top headlines — falls back to BBC/Reuters RSS with no API key |
| Quotes | Rotating inspirational quotes (ZenQuotes API or built-in fallback) |
| Calendar | Upcoming events from any iCal URL (Google Calendar, Outlook, etc.) |
| Text Messages | Custom messages managed in the **Text** tab |

---

## Content Playlist

The **Playlist** tab builds an ordered sequence of any content type. When the playlist has items it completely replaces the Modes rotation — each item has its own duration and the sequence loops forever.

**Item types:** Mode, Text (custom message), Photo (split across tiles)

**Example:** `Text (20s) → Weather (30s) → News (30s) → Text (20s) → Photo (15s) → repeat`

Remove all playlist items to return to the Modes rotation.

---

## Image Display

Push an image from the **Image** tab for immediate one-shot display.

| Mode | Description |
|------|-------------|
| Photo Split | Real photo divided tile-by-tile (puzzle effect) — great for logos on Zoom calls |
| Full Color | Each tile gets its average RGB color — smooth photo mosaic |
| 8-Color Mosaic | Nearest Vestaboard color per tile — bold graphic look |
| Monochrome | Brightness mapped to character density — ASCII art aesthetic |

---

## Physical Frame Mode

Enable in **Settings → Physical Frame**. Simulates wooden dowel rods separating tiles:

- **Divider width** — gap in pixels between tiles (0–20)
- **Divider color** — presets: Black, Dark Wood, Light Wood, Walnut, Steel; or pick any color

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
Character codes: `0`=blank, `1–26`=A–Z, `27–36`=1–0, `71–77`=color tiles

```http
POST /api/display/color-matrix
{ "color_matrix": [["#ff0000","#00ff00",...], ...] }
```

```http
POST /api/display/photo          # multipart/form-data, field: file
POST /api/display/blank          # clear to blank
POST /api/display/next           # advance to next item
GET  /api/state                  # current display state
```

### Playlist

```http
GET    /api/playlist             # list items
POST   /api/playlist             # add item
PUT    /api/playlist/{id}        # update item
DELETE /api/playlist/{id}        # remove item
POST   /api/playlist/reorder     # { "ids": [3,1,2] }
POST   /api/playlist/clear       # remove all
POST   /api/playlist/play        # jump to item 1 now
```

Add items via curl:
```bash
# Mode item
curl -X POST http://<ip>:8000/api/playlist \
  -H 'Content-Type: application/json' \
  -d '{"type":"mode","content":{"mode":"weather"},"duration":30}'

# Text item
curl -X POST http://<ip>:8000/api/playlist \
  -H 'Content-Type: application/json' \
  -d '{"type":"text","content":{"text":"Welcome!"},"duration":20}'

# Photo item (upload first, then reference the URL)
URL=$(curl -s -F file=@logo.jpg http://<ip>:8000/api/upload | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")
curl -X POST http://<ip>:8000/api/playlist \
  -H 'Content-Type: application/json' \
  -d "{\"type\":\"photo\",\"content\":{\"url\":\"$URL\"},\"duration\":15}"
```

### Screens

```http
GET    /api/screens              # list all screens
POST   /api/screens              # create screen
PUT    /api/screens/{id}         # rename or resize
DELETE /api/screens/{id}         # delete (cannot delete "main")
```

### Modes

```http
GET  /api/modes                  # list modes + enabled status
PUT  /api/modes/{mode}           # enable/disable/configure
```

### Text messages

```http
GET    /api/messages             # list messages
POST   /api/messages             # { "text": "...", "duration": 30 }
DELETE /api/messages/{id}        # remove
```

### Settings

```http
GET  /api/settings               # all settings
PUT  /api/settings               # update any subset
```

---

## Settings Reference

| Key | Default | Description |
|-----|---------|-------------|
| `rotation_interval` | `30` | Seconds between mode/playlist advances |
| `timezone` | `America/Chicago` | IANA timezone (e.g. `America/New_York`) |
| `clock_format` | `12h` | `12h` or `24h` |
| `show_date` | `true` | Show date below time in clock mode |
| `tile_color` | `#ffffff` | Character color |
| `tile_bg_color` | `#2a2a2a` | Tile background |
| `bg_color` | `#1a1a1a` | Board background |
| `sound_enabled` | `true` | Flip sound synthesis |
| `physical_mode` | `false` | Physical frame mode |
| `divider_width` | `4` | Pixels between tiles (0–20) |
| `divider_color` | `#111111` | Gap color |
| `weather_api_key` | — | OpenWeatherMap key (optional) |
| `weather_location` | — | e.g. `Portland,US` |
| `weather_units` | `imperial` | `imperial` or `metric` |
| `news_api_key` | — | NewsAPI key (optional) |
| `news_categories` | `["technology","general"]` | JSON array |
| `calendar_ical_url` | — | iCal URL |

---

## API Keys

All keys are optional — the app works without any of them.

| Service | Fallback | Where to get a key |
|---------|----------|--------------------|
| Weather | Open-Meteo (no key needed) | [openweathermap.org/api](https://openweathermap.org/api) |
| News | BBC & Reuters RSS | [newsapi.org](https://newsapi.org) |
| Calendar | n/a | Google Calendar → Settings → Secret iCal address |

---

## Character Codes

| Range | Characters |
|-------|-----------|
| 0 | Blank |
| 1–26 | A–Z |
| 27–36 | 1–0 |
| 37–62 | Punctuation (`!`, `@`, `#`, `$`, `(`, `)`, `-`, `+`, `&`, `=`, `;`, `:`, `"`, `'`, `%`, `,`, `.`, `/`, `\`, `?`) |
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
│   ├── main.py              # FastAPI app, WebSocket, rotation loop, all API routes
│   ├── database.py          # SQLite schema + async CRUD (aiosqlite)
│   ├── websocket_manager.py # Per-screen WebSocket connection groups
│   ├── charmap.py           # Vestaboard character set, text→matrix
│   ├── config.py            # Settings via FB_ environment variables
│   ├── services/
│   │   ├── clock.py         # Live time/date matrix rendering
│   │   ├── weather.py       # OpenWeatherMap + Open-Meteo fallback
│   │   ├── news.py          # NewsAPI + RSS fallback
│   │   ├── quotes.py        # ZenQuotes API + built-in fallback
│   │   ├── calendar_svc.py  # iCal parsing
│   │   └── text_svc.py      # Rotating text messages
│   ├── uploads/             # Uploaded photos (served as /uploads/*)
│   └── flipperboards.db     # SQLite (auto-created on first run)
│
├── frontend/src/
│   ├── components/
│   │   ├── DisplayView.jsx          # Full-screen display, wake lock, kiosk mode
│   │   ├── SplitFlapDisplay.jsx     # Grid renderer
│   │   ├── FlapTile.jsx             # CSS 3D animation + Web Audio flip sound
│   │   ├── ColorTile.jsx            # RGB color tile with lerp transitions
│   │   ├── PhotoTile.jsx            # CSS background-position photo split
│   │   └── remote/
│   │       ├── RemoteControl.jsx    # Tabbed remote control shell
│   │       ├── ScreenManager.jsx    # Create/edit/delete screens
│   │       ├── ModeSelector.jsx     # Enable/disable/reorder modes
│   │       ├── TextInput.jsx        # Text message queue
│   │       ├── ImageUpload.jsx      # Immediate image push (4 modes)
│   │       ├── UniversalPlaylist.jsx # Content playlist builder
│   │       └── SettingsPanel.jsx    # Theme + physical frame settings
│   ├── hooks/
│   │   ├── useWebSocket.js          # Auto-reconnecting WebSocket
│   │   └── useDisplayState.js       # Unified display state
│   └── utils/
│       ├── audio.js                 # Web Audio synthesized flip sound
│       ├── charmap.js               # Client-side character map
│       └── imageToMatrix.js         # Canvas image → matrix/color-matrix
│
├── setup.sh                 # Pi setup script
├── flipperboards.service    # systemd unit file
├── Dockerfile               # Multi-stage build
└── docker-compose.yml       # Compose with persistent data volumes
```

### Environment variables

```bash
FB_HOST=0.0.0.0
FB_PORT=8000
FB_DB_PATH=flipperboards.db
FB_DEFAULT_ROWS=6
FB_DEFAULT_COLS=22
```

---

## License

FlipperBoards Sustainable Use License — free to self-host, commercial hosted service requires a license. See [LICENSE.md](LICENSE.md).
