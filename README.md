# FlipperBoards

A Vestaboard-style split-flap display application. Runs on a Raspberry Pi connected to a TV, remotely controlled from any phone or computer on your network.

## Features

- Authentic split-flap flip animation (Vestaboard character set)
- Configurable grid size (rows × columns)
- Six display modes with automatic rotation:
  - **Clock** — live time & date with timezone support
  - **Weather** — current conditions via OpenWeatherMap
  - **News** — top headlines via NewsAPI or BBC/Reuters RSS fallback
  - **Quotes** — inspirational quotes (ZenQuotes API or built-in list)
  - **Calendar** — upcoming events from any iCal/Google Calendar URL
  - **Text Messages** — custom messages you push from the remote
- Full REST API for pushing content programmatically
- WebSocket real-time sync to all connected clients
- Color & font theming (5 built-in presets + custom color pickers)
- Mobile-friendly remote control UI

## Quick Start

```bash
git clone https://github.com/mikekmiller/flipperboards
cd FlipperBoards
chmod +x setup.sh && ./setup.sh
```

Then start the server:
```bash
cd backend
source .venv/bin/activate
python main.py
```

| URL | Purpose |
|-----|---------|
| `http://<pi-ip>:8000/display` | Full-screen display (open in TV browser) |
| `http://<pi-ip>:8000/` | Remote control (open on phone/computer) |

## Raspberry Pi Auto-Start

```bash
# Edit the user/path in flipperboards.service first, then:
sudo cp flipperboards.service /etc/systemd/system/
sudo systemctl enable flipperboards
sudo systemctl start flipperboards
```

## Docker

```bash
docker compose up -d
```

## REST API

### Push text content
```http
POST /api/display/text
Content-Type: application/json

{ "text": "HELLO WORLD" }
```

### Push raw matrix
```http
POST /api/display/matrix
Content-Type: application/json

{ "matrix": [[1, 2, 3, ...], ...] }
```
*(Character codes match the Vestaboard standard: 0=blank, 1–26=A–Z, 27–36=1–0, 71–77=color tiles)*

### Display controls
```http
POST /api/display/blank      # Clear display
POST /api/display/next       # Advance to next mode
GET  /api/state              # Get current display state
```

### Settings
```http
GET  /api/settings           # Get all settings
PUT  /api/settings           # Update settings (partial OK)
```

### Modes
```http
GET  /api/modes              # Get mode list + enabled status
PUT  /api/modes/{mode}       # Enable/disable/configure a mode
```

### Text rotation messages
```http
GET    /api/messages         # List saved messages
POST   /api/messages         # Add message { text, duration }
DELETE /api/messages/{id}    # Remove message
```

## Configuration

All settings are persisted in SQLite. Key settings via `PUT /api/settings`:

| Key | Default | Description |
|-----|---------|-------------|
| `rows` | 6 | Display rows |
| `cols` | 22 | Display columns |
| `rotation_interval` | 30 | Seconds between mode changes |
| `timezone` | UTC | IANA timezone string |
| `clock_format` | 12h | `12h` or `24h` |
| `tile_color` | #ffffff | Character color |
| `tile_bg_color` | #2a2a2a | Tile background |
| `bg_color` | #111111 | Board background |
| `weather_api_key` | — | OpenWeatherMap key |
| `weather_location` | — | e.g. `Portland,US` |
| `weather_units` | imperial | `imperial` or `metric` |
| `news_api_key` | — | NewsAPI key (optional) |
| `calendar_ical_url` | — | iCal URL from Google Calendar etc. |

## API Keys (all optional)

- **Weather**: Get a free key at [openweathermap.org/api](https://openweathermap.org/api)
- **News**: Get a free key at [newsapi.org](https://newsapi.org) (falls back to BBC/Reuters RSS without one)
- **Calendar**: Paste your Google Calendar's "Secret address in iCal format" from calendar settings

## References

See `References/SOURCES.md` for open-source projects used as inspiration.
