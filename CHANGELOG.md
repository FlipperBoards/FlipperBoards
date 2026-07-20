# Changelog

All notable changes to FlipperBoards are documented here.

## Unreleased

### Changed
- Timezone picker now offers the full IANA list (~400 zones, grouped by
  region) instead of 15 hardcoded ones — so zones like `America/Phoenix`
  (no DST) are selectable and events render at the correct offset
- Calendar events use a compact numeric date (`7/20`) and short time (`7P`,
  `11:15A`) so the event title gets most of the row instead of being clipped
  to a few letters; all-day events show no time, and events under an hour away
  count down (`15MIN`, `NOW`) instead of showing a clock time
- Weather now uses Pirate Weather (pirateweather.net, free tier) when an API
  key is set, replacing OpenWeatherMap; Open-Meteo remains the keyless
  fallback. The location accepts coordinates — decimal or DMS, optionally
  labeled (`Home | 33.413, -111.604`) — skipping geocoding entirely; drive
  times share the same parser
- Canvas engine v2 for weak hardware: mid-flip poses are pre-rendered into
  the sprite atlas so every animation frame is a few same-size blits (no
  runtime scaling or per-frame allocation); animation draws on a bounded
  tick (30 fps) decoupled from flap speed; an adaptive ladder steps down
  tick rate and internal resolution when the device can't keep up and
  remembers the settled rung (`?scale=` / `?fps=` pin it manually). Under a
  Pi-class CPU throttle the frame time dropped ~3× (p95 133 ms → 50 ms)
- Display view rewritten as a canvas sprite engine — smooth split-flap motion
  on weak hardware (Raspberry Pi 3). Tiles flip through their character ring
  like the real mechanism (authentic cascade), with gravity easing, per-tile
  timing jitter, baked-in card styling (rounded flaps, center split, sheen),
  and a rAF loop that stops completely when the board is idle. The CSS tile
  renderer remains available via `?renderer=dom`; `?scale=` renders at
  reduced resolution for very weak boards
- Fonts are now bundled (@fontsource) instead of loaded from Google Fonts —
  displays render identically on fully offline networks
- Pi kiosk launcher enables GPU rasterization flags (Chromium blocklists the
  Pi's GPU by default)
- Flip sound synthesis reuses a shared noise buffer; the canvas engine plays
  one clack per frame scaled by how many flaps landed

### Added
- Sound scheduling: restrict flip sounds to set hours/days (Config → Sound),
  evaluated server-side in the configured timezone. Individual pushes can
  override it — `sound: true` (the Text tab's Chime box, or REST/MQTT) forces
  the clatter for an announcement even when the board is muted or off-schedule;
  `sound: false` pushes silently. `?sound=0/1` still hard-overrides a single
  display
- Sports mode now takes multiple leagues at once (merged into one rotation,
  each row tagged with its league), a status filter (Live / Live + Final /
  Upcoming / All, defaulting to Live + Final), and multi-team filtering
  across leagues; it renders full team names
  where they fit (`KANSAS CITY CHIEFS` → `CHIEFS` → `KC`) instead of only
  abbreviations. Config uses a new multi-select chip widget
- Drive Times mode: live driving times with traffic to up to 6 destinations
  (Google Routes API, one Route Matrix call per refresh) — dot-leader rows
  with green/yellow/red traffic accent tiles; refreshes every 5 minutes only
  while displayed (cost control); destinations or ready-made times can also
  be pushed over MQTT (`drivetime/set`), so Home Assistant's free Waze
  integration works with no Google key
- labwc/Wayland kiosk support: `deploy/pi-kiosk/labwc-autostart.sample` for
  current Raspberry Pi OS desktop images, with docs covering the Wayland
  equivalents of screen blanking/cursor hiding and the unquoted-URL pitfall
  that silently drops `kiosk=1`
- Playlist time windows (dayparting): every playlist item can carry a start
  time, end time, and weekday selection — the lunch menu shows at lunch, the
  dinner menu at dinner; overnight windows supported; all-items-out-of-window
  falls back to the clock
- Menu playlist items: title + name/price entries with dot leaders and
  right-aligned prices; paginates when entries outnumber rows
- Countdown mode: days / HH:MM:SS to a target date with label and custom
  finish message, or count up since a date — seconds tick live with
  digit-only flips
- Colored text markup: `{red}HAPPY HOUR{/}` colors individual letters in
  pushed text and playlist text items (7 Vestaboard palette colors); live in
  the Text tab preview
- Stocks mode: comma-separated Yahoo Finance symbols (stocks + crypto) with
  price, % change, and green/red direction tiles — no API key; pages through
  long symbol lists
- Data Feed mode: poll any JSON URL and render a template with
  `{dot.path.0.notation}` placeholders — follower counts, sensors, anything
  with a JSON endpoint

## 0.1.0 — 2026-07-18

First tagged release.

### Added
- Sports mode: live game scores from ESPN's public API (NFL, NBA, MLB, NHL,
  college football/basketball, MLS, EPL) — rotates games or locks onto one
  team with digit-only score flips; no API key required
- Quiet hours: per-screen sleep schedules (off/on times, weekday selection,
  overnight windows) with manual ☾/☀ override via UI, REST, and MQTT
- Display state persists across restarts — playlists resume at their
  position, pushed content is restored instead of dropping to the clock
- Optional password protection (Config → Security): control surfaces require
  login while displays stay open — built for shared networks like a bar where
  only staff should change the boards
- MQTT control for everything (text, matrix, designs, images, modes, playlist,
  scoreboards) with retained state topics and last-will availability
- Home Assistant MQTT discovery — each screen appears as a device with
  message/mode/next/blank entities
- Scoreboard playlist items with live score updates (only changed digits flip)
  and +/− controls in the Queue tab
- Full-board sweep transition when the playlist advances to a new item
- Screen Designer: tile-by-tile editor with paint/tap modes, undo/redo,
  draft autosave, FontAwesome icon stamps, save/load/push/queue designs
- Playlist drag-to-reorder
- Live text preview showing exactly how a message wraps on the board
- Push durations: show content for N seconds or until changed
- Raspberry Pi kiosk client (`deploy/pi-kiosk/`) and MQTT multi-app
  switcher (`deploy/pi-appctl/`)
- Android WebView kiosk app with screen picker and sound toggle
- Docker multi-arch images (amd64/arm64) on GHCR + Unraid CA template
- pytest suite (56 tests) + ruff lint + CI on every PR
- Error toasts across the remote control; real connection indicators

### Fixed
- Rotation/clock loops now survive transient errors instead of dying silently
- Pushed content no longer fights the rotation timer (double advances)
- Matrix pushes can no longer resize a screen or inject invalid tile codes
- Upload hardening: type allowlist + size cap
- Cross-screen playlist corruption; per-screen news/text/quotes cursors
- Calendar UTC timestamps and folded iCal lines parse correctly
- Flip animation stutter from re-renders mid-flip
