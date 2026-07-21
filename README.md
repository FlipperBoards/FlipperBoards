# FlipperBoards

A Vestaboard-style split-flap display application. Run it on a Raspberry Pi connected to a TV, or anywhere Docker runs. Control it from any phone or computer on your network via a mobile-friendly web UI.

---

## Features

- **Authentic split-flap animation** — canvas sprite engine flips every tile through its character ring exactly like the real mechanism, with gravity easing, per-tile timing jitter, Web Audio synthesized clatter, and full-board sweep transitions; smooth even on a Raspberry Pi 3
- **Vestaboard character set** — codes 0–77: A–Z, digits, punctuation, hearts/stars/arrows/shapes (`♥ ★ → ■ ○ °`…), and 7 color tiles
- **Multiple independent screens** — each screen has its own URL, mode rotation, playlist, and WebSocket group; cast any screen to any TV
- **Ten auto-rotation modes** — Clock, Weather, News, Quotes, Calendar, Sports, Countdown, Stocks, Data Feed, Text Messages
- **Content playlist** — arrange any content in any order with per-item durations; mixes modes, custom text, photos, scoreboards, and menus
- **Dayparting** — per-item time windows show a lunch menu at lunch and a dinner menu at dinner, automatically
- **Colored text** — `{red}HAPPY HOUR{/}` markup colors individual letters — something a physical board can't do
- **Image display** — four modes: Photo Split (puzzle), Full Color (RGB mosaic), 8-Color Mosaic (Vestaboard palette), Monochrome (character density)
- **Physical frame mode** — configurable gap width and color between tiles to simulate wooden dowel rods
- **Theming** — 5 built-in presets + custom color pickers for tile text, tile background, and board background
- **REST API** — push any content programmatically
- **Optional password protection** — lock down control so only staff can change the boards; displays stay open
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

#### Auto-start with systemd (+ optional auto-update)

```bash
sudo bash deploy/install.sh
```

This installs `flipperboards-backend` (serves the API **and** the built
frontend on port 8000) plus an auto-update timer that pulls new commits,
rebuilds when needed, and restarts. Disable auto-update if you prefer manual
control: `sudo systemctl disable --now flipperboards-updater.timer`.

Useful commands:
```bash
sudo systemctl status flipperboards-backend   # check status
sudo journalctl -u flipperboards-backend -f   # live logs
sudo journalctl -t flipperboards-updater -f   # updater logs
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
| **Pi kiosk** | Raspberry Pi wired to a TV — boots straight into fullscreen Chromium (labwc/Wayland autostart or X11 systemd variants) | [`deploy/pi-kiosk/`](deploy/pi-kiosk/) |
| **Android app** | Android TV, tablets, cheap HDMI sticks | [`android/`](android/) — APK built by CI |

Both point at the server over the network; the display updates live via
WebSocket.

Sharing the Pi with other apps (e.g. a DynaFrame photo frame)? The MQTT
[app controller](deploy/pi-appctl/) switches the TV between FlipperBoards
and other systemd-managed apps — one at a time — and shows up in Home
Assistant automatically.

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

**Display tuning parameters** (combine with `&`):

- `scale=0.75` — pin the internal render resolution (upscaled to fit).
- `fps=20` — pin the animation tick rate.
- `renderer=dom` — fall back to the original CSS tile renderer.
- `sound=0` — disable flip sounds for this display.

The display uses a canvas sprite engine: characters flip through the ring
just like a real split-flap mechanism (a scoreboard digit going 2→3 is one
flap; a full message change is a satisfying cascade). Every animation frame
is a handful of pre-rendered sprite blits, drawn on a bounded tick — and the
engine **tunes itself**: if the device can't hold the tick rate it steps down
(30→20 fps, then reduced internal resolution) and remembers the setting for
the next boot. `scale`/`fps` parameters pin it manually instead. Fonts are
bundled, so displays render identically with no internet access.

**Raspberry Pi tip:** on a Pi 3 driving a 1080p TV, set the HDMI output to
720p (`hdmi_mode` in `/boot/firmware/config.txt`) — the TV upscales, every
rendering cost halves, and at TV viewing distance the difference is
invisible.

---

## Quiet Hours

Each screen can sleep on a schedule — a bar's board blanks at closing time and
wakes before opening. Configure per screen in **Screens → edit (✎)**:

- **Off / on times** — overnight windows (off 23:00 → on 08:00) work naturally
- **Days** — which weekdays the off time applies to
- Manual override: the ☾/☀ button on each screen row, `POST
  /api/screens/{id}/sleep {"sleeping": true}`, or MQTT `sleep/set` — holds
  until the next scheduled boundary
- Pushing content to a sleeping screen wakes it

---

## Sound

Flip sounds are synthesized in the browser (no audio files). Control them in
**Config → Sound**:

- **Flip Sound Effects** — master on/off
- **Sound Schedule** — restrict the clatter to set hours and days (e.g. sound
  on 11:00–22:00 while the venue is open, silent otherwise). Overnight windows
  work naturally. The server evaluates this in the configured timezone.
- **Chime an announcement** — a push sent with `sound: true` (the **Chime**
  checkbox on the Text tab, or `"sound":true` in a REST/MQTT push) plays the
  flip clatter *even when the board is muted or off-schedule* — so a "LAST
  CALL" grabs attention without the board clicking all day. `sound: false`
  pushes silently.
- **Per-display override** — add `?sound=0` to a display URL to mute that
  specific TV regardless, or `?sound=1` to always play on it.

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
| Weather | Current conditions via Pirate Weather (key) or Open-Meteo (no key) |
| News | Google News — per-screen keyword search, source include/exclude, topic & locale; no API key |
| Quotes | Rotating inspirational quotes (ZenQuotes API or built-in fallback) |
| Calendar | Upcoming events from any iCal URL (Google Calendar, Outlook, etc.) — compact `M/D` date so titles get the room |
| Sports | Live scores across one or many leagues (NFL, NBA, MLB, NHL, college, MLS, EPL) with status filtering and full team names — no API key |
| Countdown | Days / hours:minutes:seconds to any date (or count up since one) — seconds tick live |
| Stocks | Stock & crypto prices with % change and green/red direction tiles — no API key needed |
| Data Feed | Poll any JSON URL and render a template — follower counts, sensors, anything |
| Drive Times | Live driving times with traffic to up to 6 destinations (Google Maps key) |
| Text Messages | Custom messages managed in the **Text** tab |

**News mode** pulls from Google News (no API key) with per-screen filtering in
the mode's ⚙ config:

- **Keyword** — free-text search (`Phoenix Suns`); supports Google operators
  like `intitle:`, `"exact phrase"`, `OR`
- **Topics** — pick one or several (Top Stories, World, Nation, Business,
  Technology, Entertainment, Sports, Science, Health); they merge with the
  keyword into one rotation
- **Only these sources / Never these sources** — comma-separated domains
  (`espn.com, apnews.com`) that filter **both** the keyword search and topics
- **Recency** — past hour / 24 hours / week, applied to keyword **and** topics
- **Language / Country** — ISO codes for locale (`en` / `US`)

Source and recency filters apply uniformly: Google News' `site:`/`when:`
operators only work on keyword searches, so for topic sections FlipperBoards
reads each item's source domain and publish time from the feed and filters them
the same way. Different screens can run different feeds — one board on
`Phoenix Suns` from `espn.com`, another on Business + Technology from the past
day. Headlines cache for 5 minutes and rotate one at a time. It's built on
Google News RSS directly (the same feeds the `google-news-api` project wraps),
so there's nothing to install and no key.

**Sports mode** rotates through the day's games with live scores, game clocks,
and full team names (it uses the longest name that fits — `KANSAS CITY CHIEFS`
on a wide board, `CHIEFS` on a narrow one, `KC` only as a last resort). As a
score changes, only its digits flip, just like a real stadium board. Scores
refresh with the rotation interval (60s API cache). Configure in the mode's ⚙:

- **Leagues** — pick one or several (NFL, NBA, MLB, NHL, college football &
  basketball, MLS, Premier League). Multiple leagues merge into one rotation,
  each game's status line tagged with its league (`NFL  3RD 7:32`).
- **Show** — Live now, **Live + Final** (the default — usually all you care
  about), Upcoming, or All games.
- **Team filter** — comma-separated names or abbreviations (`CHIEFS, LAKERS`),
  matched across every selected league. Filter to one game and it stays put so
  the score digits flip live.

**Countdown mode** counts down to a target date (`2027-01-01 00:00`) with an
optional label and a custom finish message — or counts up *since* a date.
The clock line re-renders every second, so only the second digits flip.

**Stocks mode** takes a comma-separated symbol list (`AAPL, MSFT, BTC-USD` —
Yahoo Finance symbols, crypto included) and shows one row per symbol with the
price, % change vs previous close, and a green/red accent tile per direction.
More symbols than rows pages automatically.

**Data Feed mode** polls any JSON URL every 2 minutes and renders a template
with `{dot.path.0.notation}` placeholders into the response — subscriber
counts, temperature sensors, home-automation values. Example: URL
`https://api.example.com/stats`, template `SUBS {data.followers}`. The server
fetches whatever URL an authenticated operator configures, so treat it like
any admin setting and deploy on a trusted network.

**Drive Times mode** shows live driving times with traffic to up to 6
destinations, one row each with dot leaders and a traffic accent tile —
green (clear), yellow (slow), red (heavy):

```
     DRIVE TIMES
■ HOME··········23 MIN
■ AIRPORT·······41 MIN
■ THE SHOP·······8 MIN
```

Set the **Google Maps API key** in Settings (Routes API enabled on the key),
then the **origin** and **destinations** (`Name | address`, one per line) in
the mode's ⚙ config. Anywhere an address goes, coordinates work too — decimal
(`Home | 45.52, -122.68`) or the DMS format Google Maps copies on right-click
(`Home | 33°26'43.8"N 111°59'21.0"W`). Coordinates skip geocoding entirely,
which is handy for spots without a clean street address. Times refresh **every 5 minutes while displayed** —
fetches only happen when a screen is actually showing the mode, and one
Route Matrix request covers all destinations. Google bills the Route Matrix
per element (destinations × refreshes), so fewer destinations and fewer
display-hours cost less; a board showing 6 destinations 24/7 lands in the
hundreds of dollars per month range, while a few hours a day stays inside
the free credit. Destinations can also be pushed over MQTT (see MQTT
topics) — including ready-made times from Home Assistant's free Waze
integration, which needs no Google key at all.

---

## Content Playlist

The **Playlist** tab builds an ordered sequence of any content type. When the playlist has items it completely replaces the Modes rotation — each item has its own duration and the sequence loops forever.

**Item types:** Mode, Text (custom message), Photo (split across tiles), Score
(live scoreboard), Menu (dot-leader price list)

**Example:** `Text (20s) → Weather (30s) → News (30s) → Text (20s) → Photo (15s) → repeat`

Remove all playlist items to return to the Modes rotation.

### Per-item configuration

A **Mode** item carries its **own** config, edited with the ⚙ button on its
row (the same fields as the Modes tab). So the same mode can appear several
times with different settings — a News item for `Phoenix Suns · espn.com`
next to another for `Business · past 24h`, or Sports items for different
leagues — all rotating in one sequence. Live modes (countdown, drive times)
tick using each item's own config.

### Named sets

The queue is organized into **sets** — named lists shown as tabs at the top
(the default is "Playlist"). Only one set plays at a time; the others sit
ready. Use sets to keep a "Morning", "Lunch", and "Game Night" lineup and
switch between them:

- **Activate** a set manually to make it the one that plays.
- Give a set a **⏱ Schedule** (start/end time + weekdays) and it
  auto-activates during that window — e.g. a Lunch set `11:00–16:00`, a Dinner
  set `16:00–23:00`. The scheduled set wins; outside every window the first set
  plays. A manual activation holds until the next scheduled boundary (same as
  quiet hours).

Editing a set (adding items, reordering) doesn't disturb whatever set is
currently playing. Sets can also be activated over MQTT
(`flipperboards/<screen>/set/set` with the set name or id) — so a Home
Assistant automation can flip the board to "Happy Hour" on a schedule or a
button press.

### Time windows (dayparting)

Every playlist item can carry a time window (the ⏱ button on its row): start
time, end time, and weekdays. Outside its window the item is skipped —
the rotation flows through the remaining items. A bar's playlist can hold both
the lunch menu (`11:00–16:00`) and the dinner menu (`16:00–23:00`) and always
show the right one. Overnight windows (`22:00–02:00`) work naturally. If
every item is out of its window the board falls back to the clock.

### Menu items

The **Menu** item type renders a title plus name/price entries with
dot leaders and right-aligned prices:

```
      HAPPY HOUR
WELLS··············4.50
DRAFTS·············5.00
WINGS··············9.99
```

More entries than rows paginate each time the item comes around.

### Scoreboard items

The **Score** item type shows two teams with live scores — home team with a
green accent tile, away with red, scores right-aligned:

```
█ HAWKS             12
█ OWLS               7
```

Bump scores from the playlist row's **+/−** buttons, the REST API, or MQTT —
**only the changed digit tiles flip**, everything else stays still. When the
playlist advances to the next game (or any other item), the whole board does a
dramatic full flip sweep.

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
Color individual letters with markup — `{red}HAPPY HOUR{/} 5-7PM` renders
"HAPPY HOUR" in red. Colors: red, orange, yellow, green, blue, violet, white.
Works in pushed text and playlist text items; the Text tab preview shows it
live.

Add `"sound": true` to any push (`text`, `matrix`, `color-matrix`, photo,
design) to force the flip clatter for that announcement even when the board is
muted or outside its sound schedule — or `"sound": false` to push silently.
The **Chime** checkbox on the Text tab does this. Omit it to follow the
schedule.

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
POST /api/display/mode           # { "mode": "clock", "duration": 60 }
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
POST   /api/playlist/jump        # { "pos": 2 } — jump to a specific item
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

# Scoreboard item
curl -X POST http://<ip>:8000/api/playlist \
  -H 'Content-Type: application/json' \
  -d '{"type":"scoreboard","content":{"home_name":"HAWKS","away_name":"OWLS","home_score":0,"away_score":0},"duration":60}'

# Live score update — only the changed digit flips
curl -X PUT http://<ip>:8000/api/playlist/<id> \
  -H 'Content-Type: application/json' \
  -d '{"type":"scoreboard","content":{"home_name":"HAWKS","away_name":"OWLS","home_score":1,"away_score":0},"duration":60}'
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

## Security

FlipperBoards is designed for **trusted private networks** (home, office, bar).
By default there is no login. If untrusted people share the network — e.g. a
venue with guest Wi-Fi — enable password protection in **Config → Security**:

- **Control requires login** — the remote UI and every mutating API call
  (`POST`/`PUT`/`DELETE`) need a session; staff sign in once per device
  (sessions last 30 days)
- **Displays stay open** — TVs, kiosks, and read-only API calls work without
  a login, so wall-mounted screens survive reboots unattended
- Passwords are stored as salted PBKDF2 hashes; changing the password signs
  everyone out

API clients authenticate with `POST /api/auth/login {"password": "..."}` and
the returned `fb_session` cookie. MQTT is governed by your broker's own
credentials, not this password.

Do not expose FlipperBoards directly to the internet — for remote access use
a VPN or an authenticating reverse proxy.

---

## MQTT & Home Assistant

Enable in **Config → MQTT / Home Assistant** (broker host/port/credentials).
Everything the REST API can do, MQTT can do — from Home Assistant, Node-RED,
or a plain `mosquitto_pub`.

### Command topics

Base topic is configurable (default `flipperboards`); `<sid>` is the screen id
(`main` unless you've added screens).

| Topic | Payload |
|-------|---------|
| `flipperboards/<sid>/text/set` | `HELLO WORLD` or `{"text":"HI","duration":30,"sound":true}` |
| `flipperboards/<sid>/matrix/set` | `{"matrix":[[...codes...]],"duration":30}` |
| `flipperboards/<sid>/design/set` | design name, id, or `{"design":"My Design","duration":60}` |
| `flipperboards/<sid>/image/set` | library image id/name or `{"image":12,"duration":60}` |
| `flipperboards/<sid>/mode/set` | mode id — `clock`, `weather`, `news`, … |
| `flipperboards/<sid>/blank/set` | anything |
| `flipperboards/<sid>/sleep/set` | `on` \| `off` — manual quiet-hours override |
| `flipperboards/<sid>/playlist/set` | `next` \| `play` \| item index (`2`) |
| `flipperboards/<sid>/set/set` | activate a playlist set by name or id (`Happy Hour`) |
| `flipperboards/<sid>/scoreboard/set` | `{"home_score":3}` — partial updates OK |
| `flipperboards/<sid>/scoreboard/<item_id>/set` | same, targeting a specific playlist item |
| `flipperboards/<sid>/drivetime/set` | `[{"name":"HOME","dest":"123 Main St"}]` (computed via Google) or `[{"name":"HOME","minutes":23,"traffic":"heavy"}]` (ready-made, e.g. HA Waze); `clear` returns to the configured list |

### State topics (published, retained)

| Topic | Payload |
|-------|---------|
| `flipperboards/bridge/availability` | `online` / `offline` (last will) |
| `flipperboards/<sid>/state` | `{"mode","rows","cols","playlist_pos","playlist_len"}` |
| `flipperboards/<sid>/mode` | current mode string |
| `flipperboards/<sid>/text/state` | last pushed text |

### Examples

```bash
mosquitto_pub -h <broker> -t flipperboards/main/text/set -m 'DINNER IS READY'
mosquitto_pub -h <broker> -t flipperboards/main/mode/set -m weather
mosquitto_pub -h <broker> -t flipperboards/main/scoreboard/set -m '{"home_score":2,"away_score":1}'
mosquitto_pub -h <broker> -t flipperboards/main/playlist/set -m next
```

### Home Assistant discovery

With **HA Discovery** enabled (default), each screen announces itself via MQTT
discovery and appears in Home Assistant as a device — no YAML:

- **Message** (text entity) — type a message, it appears on the board
- **Mode** (select) — switch between clock/weather/news/…
- **Playlist Set** (select) — pick which named set plays; the options track
  your set names and the current value follows schedule/manual switches
- **Next** (button) — advance the playlist
- **Blank** (button) — clear the display

Note: after a text/image push the mode state may show values not in the select
options (e.g. `text_push`) — HA displays the select as unknown until a real
mode is active again.

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
| `sound_enabled` | `true` | Flip sound synthesis (master switch) |
| `sound_schedule` | `{}` | `{enabled, on_time, off_time, days}` — sound plays only inside this window |
| `physical_mode` | `false` | Physical frame mode |
| `divider_width` | `4` | Pixels between tiles (0–20) |
| `divider_color` | `#111111` | Gap color |
| `weather_api_key` | — | Pirate Weather key (optional) |
| `google_maps_api_key` | — | Google Maps key for Drive Times (Routes API) |
| `weather_location` | — | `Portland,US`, coordinates (`33.413, -111.604`), or labeled coords (`Home \| 33.413, -111.604`) |
| `weather_units` | `imperial` | `imperial` or `metric` |
| `news_categories` | `["technology","general"]` | JSON array |
| `calendar_ical_url` | — | iCal URL |
| `mqtt_enabled` | `false` | Enable the MQTT bridge |
| `mqtt_host` | — | Broker hostname/IP |
| `mqtt_port` | `1883` | Broker port |
| `mqtt_username` | — | Broker username (optional) |
| `mqtt_password` | — | Broker password (optional) |
| `mqtt_base_topic` | `flipperboards` | Topic prefix |
| `mqtt_ha_discovery` | `true` | Home Assistant MQTT discovery |

---

## API Keys

All keys are optional — the app works without any of them.

| Service | Fallback | Where to get a key |
|---------|----------|--------------------|
| Weather | Open-Meteo (no key needed) | [pirateweather.net](https://pirateweather.net) — free tier |
| News | Google News (no key needed) | — |
| Calendar | n/a | Google Calendar → Settings → Secret iCal address |
| Drive Times | MQTT-pushed times (e.g. HA Waze) | [console.cloud.google.com](https://console.cloud.google.com) — enable Routes API |

---

## Character Codes

| Range | Characters |
|-------|-----------|
| 0 | Blank |
| 1–26 | A–Z |
| 27–36 | 1–0 |
| 37–46 | `!` `@` `#` `$` `(` `)` `-` `+` `&` `=` |
| 47–56 | `;` `:` `'` `"` `%` `,` `.` `/` `?` `°` |
| 57–60 | `♥` `♦` `♣` `♠` |
| 61–62 | `★` `☆` |
| 63–66 | `←` `↑` `→` `↓` |
| 67–69 | `·` `■` `○` |
| 70 | Reserved (blank) |
| 71–77 | Color tiles: Red, Orange, Yellow, Green, Blue, Violet, White |

---

## Architecture

```
FlipperBoards/
├── backend/
│   ├── main.py              # FastAPI app, WebSocket, rotation loops, all API routes
│   ├── database.py          # SQLite schema + async CRUD (aiosqlite, WAL)
│   ├── mqtt_bridge.py       # MQTT control + Home Assistant discovery
│   ├── mode_registry.py     # Pluggable display-mode registry
│   ├── websocket_manager.py # Per-screen WebSocket connection groups
│   ├── charmap.py           # Vestaboard character set, text→matrix
│   ├── config.py            # Startup settings via FB_ environment variables
│   ├── plugins/             # Optional plugin modes (see PLUGINS.md)
│   ├── services/
│   │   ├── clock.py         # Live time/date matrix rendering
│   │   ├── weather.py       # Pirate Weather + Open-Meteo fallback
│   │   ├── news.py          # Google News RSS (search + domain/topic filters)
│   │   ├── quotes.py        # ZenQuotes API + built-in fallback
│   │   ├── calendar_svc.py  # iCal parsing
│   │   ├── scoreboard.py    # Team-score matrix rendering
│   │   └── text_svc.py      # Rotating text messages
│   └── tests/               # pytest suite (run: pytest backend/tests)
│
├── frontend/src/
│   ├── components/
│   │   ├── DisplayView.jsx          # Full-screen display, wake lock, kiosk mode
│   │   ├── SplitFlapDisplay.jsx     # Grid renderer + sweep stagger
│   │   ├── FlapTile.jsx             # CSS 3D animation + Web Audio flip sound
│   │   ├── ColorTile.jsx            # RGB color tile with lerp transitions
│   │   ├── PhotoTile.jsx            # CSS background-position photo split
│   │   ├── Toast.jsx                # App-wide error/success toasts
│   │   └── remote/
│   │       ├── RemoteControl.jsx    # Tabbed remote control shell
│   │       ├── ScreenManager.jsx    # Create/edit/delete screens
│   │       ├── ModeSelector.jsx     # Enable/disable/configure modes
│   │       ├── TextInput.jsx        # Text push with live preview
│   │       ├── ImageUpload.jsx      # Image push (4 modes) + library
│   │       ├── ScreenDesigner.jsx   # Tile-by-tile editor, icon stamps, undo
│   │       ├── UniversalPlaylist.jsx # Playlist builder, drag reorder, scoreboards
│   │       ├── DurationPicker.jsx   # Shared duration control
│   │       └── SettingsPanel.jsx    # Theme, MQTT, physical frame settings
│   ├── hooks/
│   │   ├── useWebSocket.js          # Auto-reconnecting WebSocket
│   │   └── useDisplayState.js       # Unified display state
│   ├── data/icons.js                # Curated FontAwesome icon catalog
│   └── utils/
│       ├── api.js                   # fetch wrapper with error propagation
│       ├── audio.js                 # Web Audio synthesized flip sound
│       ├── charmap.js               # Client-side character map + preview
│       ├── iconStamp.js             # FA icon → tile matrix rendering
│       └── imageToMatrix.js         # Canvas image → matrix/color-matrix
│
├── android/                 # WebView kiosk app (APK built by CI)
├── deploy/
│   ├── install.sh           # Linux systemd install (backend + auto-updater)
│   ├── update.sh            # Git-poll auto-updater (rebuilds frontend)
│   ├── start.ps1            # Windows dev auto-reload script
│   ├── pi-kiosk/            # Raspberry Pi fullscreen-browser client
│   └── pi-appctl/           # MQTT multi-app switcher for shared Pis
├── unraid/                  # Unraid Community Applications template
├── setup.sh                 # Bare-metal first-time setup (venv + build)
├── Dockerfile               # Multi-stage build
└── docker-compose.yml       # Compose with persistent /data volume
```

### Environment variables

Startup configuration (`.env` file or environment; all optional):

```bash
FB_HOST=0.0.0.0            # bind address
FB_PORT=8000               # port
FB_DB_PATH=flipperboards.db
FB_UPLOAD_DIR=uploads      # photo storage directory
FB_DEFAULT_ROWS=6          # dimensions for newly created screens
FB_DEFAULT_COLS=22
FB_WEATHER_API_KEY=        # fallback when the UI setting is empty
FB_NEWS_API_KEY=           # fallback when the UI setting is empty
FB_PLUGINS=                # comma-separated plugin names (see PLUGINS.md)
```

Runtime settings (theme, MQTT, rotation, API keys…) live in the database and
are edited in the **Config** tab — see the Settings Reference above.

---

## Development

```bash
# Backend tests + lint
pip install -r backend/requirements-dev.txt
cd backend && pytest tests && ruff check .

# Frontend dev server (proxies /api and /ws to :8000)
cd frontend && npm install && npm run dev
```

CI runs the test suite and a production frontend build on every push and PR.
See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved, and
[PLUGINS.md](PLUGINS.md) for writing custom display modes.

---

## License

FlipperBoards is **source-available** under the FlipperBoards Sustainable Use
License — free to self-host and modify for your own use (including in a
commercial environment); offering it as a hosted service to third parties
requires a commercial license. See [LICENSE.md](LICENSE.md).
