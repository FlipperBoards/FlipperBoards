import React, { useState, useEffect } from 'react'
import { apiJson } from '../../utils/api'
import { useToast } from '../Toast'

// Full IANA timezone list from the browser (all modern browsers, incl. the
// Pi's Chromium). Falls back to a short list on very old browsers. The
// backend uses pytz, which knows every IANA zone, so any value here is valid.
const FALLBACK_TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver',
  'America/Phoenix', 'America/Los_Angeles', 'America/Anchorage', 'Pacific/Honolulu',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Moscow',
  'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Kolkata', 'Australia/Sydney',
]

const ALL_TIMEZONES = (() => {
  try {
    const zones = Intl.supportedValuesOf('timeZone')
    if (zones && zones.length) return zones
  } catch { /* older browser — use the fallback */ }
  return FALLBACK_TIMEZONES
})()

// Group by region (America, Asia, …) so the dropdown is navigable; UTC stands alone.
const TIMEZONE_GROUPS = (() => {
  const groups = {}
  for (const z of ALL_TIMEZONES) {
    if (z === 'UTC') continue
    const region = z.includes('/') ? z.split('/')[0] : 'Other'
    ;(groups[region] ||= []).push(z)
  }
  return groups
})()

const tzCity = (tz) => tz.includes('/') ? tz.split('/').slice(1).join('/').replace(/_/g, ' ') : tz

const TILE_PRESETS = [
  { label: 'Classic', tileColor: '#ffffff', tileBgColor: '#222222', bgColor: '#111111' },
  { label: 'Amber',   tileColor: '#ffb800', tileBgColor: '#1a1200', bgColor: '#0a0900' },
  { label: 'Green',   tileColor: '#00ff88', tileBgColor: '#001a0d', bgColor: '#00100a' },
  { label: 'Blue',    tileColor: '#4fc3f7', tileBgColor: '#0a1929', bgColor: '#050e1a' },
  { label: 'Red',     tileColor: '#ff5252', tileBgColor: '#1a0a0a', bgColor: '#0d0505' },
]

const WOOD_PRESETS = [
  { label: 'Black',      color: '#0a0a0a' },
  { label: 'Dark Wood',  color: '#3d2b1f' },
  { label: 'Walnut',     color: '#5c3d2e' },
  { label: 'Light Wood', color: '#8b6914' },
  { label: 'Steel',      color: '#4a4a4a' },
]

function Section({ title, children }) {
  return (
    <section
      className="rounded-xl p-4 space-y-3"
      style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
    >
      <p className="section-label">{title}</p>
      {children}
    </section>
  )
}

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="section-label">{label}</label>
      {children}
    </div>
  )
}

function SecuritySection() {
  const [enabled, setEnabled] = useState(false)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const showToast = useToast()

  useEffect(() => {
    fetch('/api/auth/status').then(r => r.json())
      .then(st => setEnabled(st.enabled)).catch(() => {})
  }, [])

  const configure = async (nextEnabled) => {
    if (busy) return
    if (nextEnabled && !password.trim() && !enabled) {
      showToast('Set a password first')
      return
    }
    setBusy(true)
    try {
      const body = { enabled: nextEnabled }
      if (password.trim()) body.password = password.trim()
      await apiJson('/api/auth/configure', 'POST', body)
      setEnabled(nextEnabled)
      setPassword('')
      showToast(
        nextEnabled
          ? (body.password ? 'Password set — control now requires login' : 'Login requirement enabled')
          : 'Login requirement disabled',
        'success')
    } catch (err) {
      showToast(`Security update failed: ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title="Security">
      <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>
        {enabled
          ? 'Login required — only people with the password can control the boards. Displays stay open.'
          : 'Anyone on your network can control the boards. Set a password to restrict control to staff.'}
      </p>
      <div className="flex gap-2">
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          placeholder={enabled ? 'New password (optional)' : 'Choose a password (min 4 chars)'}
          minLength={4}
          className="fb-input flex-1"
        />
        {enabled && password.trim() && (
          <button onClick={() => configure(true)} disabled={busy}
            className="fb-btn-primary text-[11px] px-3 py-1.5 flex-shrink-0">
            Change
          </button>
        )}
      </div>
      <button
        onClick={() => configure(!enabled)}
        disabled={busy || (!enabled && !password.trim())}
        className={enabled ? 'fb-btn-ghost w-full py-2' : 'fb-btn-primary w-full py-2'}
      >
        {busy ? 'Working…' : enabled ? 'Disable Login Requirement' : 'Enable Login Requirement'}
      </button>
      {enabled && (
        <p className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>
          Changing the password signs everyone out. Sessions last 30 days.
        </p>
      )}
    </Section>
  )
}

export default function SettingsPanel({ settings: initialSettings, onUpdate }) {
  const [s, setS] = useState(initialSettings || {})
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const showToast = useToast()

  useEffect(() => { setS(initialSettings || {}) }, [initialSettings])

  const set = (key, value) => setS(prev => ({ ...prev, [key]: value }))

  const save = async () => {
    if (saving) return
    setSaving(true)
    try {
      await apiJson('/api/settings', 'PUT', {
        rotation_interval: Number(s.rotation_interval) || 30,
        tile_color:        s.tile_color        || '#ffffff',
        bg_color:          s.bg_color          || '#1a1a1a',
        tile_bg_color:     s.tile_bg_color     || '#2a2a2a',
        timezone:          s.timezone          || 'UTC',
        clock_format:      s.clock_format      || '12h',
        show_date:         s.show_date !== 'false',
        weather_location:  s.weather_location  || '',
        weather_units:     s.weather_units     || 'imperial',
        weather_api_key:   s.weather_api_key   || '',
        google_maps_api_key: s.google_maps_api_key || '',
        news_api_key:      s.news_api_key      || '',
        calendar_ical_url: s.calendar_ical_url || '',
        sound_enabled:     s.sound_enabled !== 'false',
        flip_duration:     Number(s.flip_duration) || 120,
        divider_width:     Number(s.divider_width) || 4,
        divider_color:     s.divider_color     || '#111111',
        physical_mode:     s.physical_mode === 'true',
        mqtt_enabled:      s.mqtt_enabled === 'true',
        mqtt_host:         s.mqtt_host        || '',
        mqtt_port:         Number(s.mqtt_port) || 1883,
        mqtt_username:     s.mqtt_username    || '',
        mqtt_password:     s.mqtt_password    || '',
        mqtt_base_topic:   s.mqtt_base_topic  || 'flipperboards',
        mqtt_ha_discovery: s.mqtt_ha_discovery !== 'false',
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      onUpdate()
    } catch (err) {
      showToast(`Save failed: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const applyPreset = (preset) =>
    setS(prev => ({ ...prev, tile_color: preset.tileColor, tile_bg_color: preset.tileBgColor, bg_color: preset.bgColor }))

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--text-1)' }}>
        Settings
      </h2>

      {/* Display size — rows/cols are per-screen, managed in the Screens tab */}
      <Section title="Display">
        <Field label="Rotation Interval">
          <div className="flex items-center gap-2">
            <input type="number" min={5} max={3600} value={s.rotation_interval || 30}
              onChange={e => set('rotation_interval', e.target.value)} className="fb-input" />
            <span className="text-[11px] font-mono flex-shrink-0" style={{ color: 'var(--text-3)' }}>sec</span>
          </div>
        </Field>
        <Field label="Flip Speed">
          <select value={s.flip_duration || '120'} onChange={e => set('flip_duration', e.target.value)} className="fb-input">
            <option value="60">Fast (60ms)</option>
            <option value="120">Normal (120ms)</option>
            <option value="200">Slow (200ms)</option>
            <option value="350">Very Slow (350ms)</option>
          </select>
        </Field>
      </Section>

      {/* Theme */}
      <Section title="Theme">
        <div className="flex flex-wrap gap-1.5">
          {TILE_PRESETS.map(preset => (
            <button
              key={preset.label}
              onClick={() => applyPreset(preset)}
              className="px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all"
              style={{
                background: preset.bgColor,
                color: preset.tileColor,
                border: `1px solid ${preset.tileBgColor}`,
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { key: 'tile_color',    label: 'Tile Text',  def: '#ffffff' },
            { key: 'tile_bg_color', label: 'Tile BG',    def: '#222222' },
            { key: 'bg_color',      label: 'Background', def: '#111111' },
          ].map(({ key, label, def }) => (
            <Field key={key} label={label}>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={s[key] || def}
                  onChange={e => set(key, e.target.value)}
                  className="w-9 h-9 rounded-lg cursor-pointer border-0 bg-transparent p-0.5"
                  style={{ border: '1px solid var(--border)' }}
                />
                <span className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>
                  {s[key] || def}
                </span>
              </div>
            </Field>
          ))}
        </div>
      </Section>

      {/* Clock */}
      <Section title="Clock">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Format">
            <select value={s.clock_format || '12h'} onChange={e => set('clock_format', e.target.value)} className="fb-input">
              <option value="12h">12-hour</option>
              <option value="24h">24-hour</option>
            </select>
          </Field>
          <Field label="Show Date">
            <select value={s.show_date === 'false' ? 'false' : 'true'} onChange={e => set('show_date', e.target.value)} className="fb-input">
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </Field>
        </div>
        <Field label="Timezone">
          <select value={s.timezone || 'UTC'} onChange={e => set('timezone', e.target.value)} className="fb-input">
            <option value="UTC">UTC</option>
            {Object.entries(TIMEZONE_GROUPS).map(([region, zones]) => (
              <optgroup key={region} label={region}>
                {zones.map(tz => <option key={tz} value={tz}>{tzCity(tz)}</option>)}
              </optgroup>
            ))}
          </select>
        </Field>
      </Section>

      {/* Weather */}
      <Section title="Weather — Pirate Weather">
        <Field label="Location (city or coordinates)">
          <input type="text" placeholder="Portland,US — or 33.413, -111.604" value={s.weather_location || ''}
            onChange={e => set('weather_location', e.target.value)} className="fb-input" />
        </Field>
        <Field label="API Key">
          <input type="password" placeholder="pirateweather.net key — optional, falls back to Open-Meteo"
            value={s.weather_api_key || ''}
            onChange={e => set('weather_api_key', e.target.value)} className="fb-input" />
        </Field>
        <Field label="Units">
          <select value={s.weather_units || 'imperial'} onChange={e => set('weather_units', e.target.value)} className="fb-input">
            <option value="imperial">Imperial (°F)</option>
            <option value="metric">Metric (°C)</option>
          </select>
        </Field>
      </Section>

      {/* Drive times */}
      <Section title="Drive Times — Google Maps">
        <Field label="Google Maps API Key">
          <input type="password" placeholder="Routes API enabled — key from console.cloud.google.com"
            value={s.google_maps_api_key || ''}
            onChange={e => set('google_maps_api_key', e.target.value)} className="fb-input" />
        </Field>
        <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>
          Origin and destinations are set per screen in the Drive Times mode ⚙ config.
          Times refresh every 5 minutes while displayed.
        </p>
      </Section>

      {/* News */}
      <Section title="News">
        <Field label="NewsAPI Key">
          <input type="password" placeholder="Optional — falls back to RSS" value={s.news_api_key || ''}
            onChange={e => set('news_api_key', e.target.value)} className="fb-input" />
        </Field>
      </Section>

      {/* Calendar */}
      <Section title="Calendar">
        <Field label="iCal URL">
          <input type="url" placeholder="https://calendar.google.com/calendar/ical/…" value={s.calendar_ical_url || ''}
            onChange={e => set('calendar_ical_url', e.target.value)} className="fb-input" />
        </Field>
      </Section>

      {/* Physical Frame */}
      <Section title="Physical Frame / Dowel Rods">
        <Field label="Frame Mode">
          <select value={s.physical_mode === 'true' ? 'true' : 'false'}
            onChange={e => set('physical_mode', e.target.value)} className="fb-input">
            <option value="false">Standard</option>
            <option value="true">Physical Frame (inset tiles)</option>
          </select>
        </Field>
        <Field label={`Divider Width — ${s.divider_width || 4}px`}>
          <input type="range" min={0} max={20} value={s.divider_width || 4}
            onChange={e => set('divider_width', e.target.value)}
            className="w-full accent-blue-500" />
        </Field>
        <Field label="Divider Color">
          <div className="flex items-center gap-2 flex-wrap">
            <input type="color" value={s.divider_color || '#111111'}
              onChange={e => set('divider_color', e.target.value)}
              className="w-9 h-9 rounded-lg cursor-pointer p-0.5"
              style={{ border: '1px solid var(--border)', background: 'transparent' }} />
            {WOOD_PRESETS.map(p => (
              <button key={p.color} onClick={() => set('divider_color', p.color)}
                className="text-[10px] font-mono px-2 py-1 rounded transition-colors"
                style={{ background: p.color, color: '#fff', border: '1px solid rgba(255,255,255,0.1)' }}>
                {p.label}
              </button>
            ))}
          </div>
        </Field>
      </Section>

      {/* Sound */}
      <Section title="Sound">
        <Field label="Flip Sound Effects">
          <select value={s.sound_enabled === 'false' ? 'false' : 'true'}
            onChange={e => set('sound_enabled', e.target.value)} className="fb-input">
            <option value="true">Enabled</option>
            <option value="false">Disabled</option>
          </select>
        </Field>
      </Section>

      {/* MQTT */}
      {/* Security */}
      <SecuritySection />

      <Section title="MQTT / Home Assistant">
        <Field label="MQTT Control">
          <select value={s.mqtt_enabled === 'true' ? 'true' : 'false'}
            onChange={e => set('mqtt_enabled', e.target.value)} className="fb-input">
            <option value="false">Disabled</option>
            <option value="true">Enabled</option>
          </select>
        </Field>
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <Field label="Broker Host">
              <input type="text" placeholder="192.168.1.50" value={s.mqtt_host || ''}
                onChange={e => set('mqtt_host', e.target.value)} className="fb-input" />
            </Field>
          </div>
          <Field label="Port">
            <input type="number" placeholder="1883" value={s.mqtt_port || '1883'}
              onChange={e => set('mqtt_port', e.target.value)} className="fb-input" />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Username">
            <input type="text" placeholder="Optional" value={s.mqtt_username || ''}
              onChange={e => set('mqtt_username', e.target.value)} className="fb-input" />
          </Field>
          <Field label="Password">
            <input type="password" placeholder="Optional" value={s.mqtt_password || ''}
              onChange={e => set('mqtt_password', e.target.value)} className="fb-input" />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Base Topic">
            <input type="text" placeholder="flipperboards" value={s.mqtt_base_topic || 'flipperboards'}
              onChange={e => set('mqtt_base_topic', e.target.value)} className="fb-input" />
          </Field>
          <Field label="HA Discovery">
            <select value={s.mqtt_ha_discovery === 'false' ? 'false' : 'true'}
              onChange={e => set('mqtt_ha_discovery', e.target.value)} className="fb-input">
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </Field>
        </div>
        <p className="text-[10px] font-mono" style={{ color: 'var(--text-3)' }}>
          Saving restarts the MQTT connection. With HA Discovery on, each screen
          appears in Home Assistant as a device with message, mode, and button entities.
        </p>
      </Section>

      <button
        onClick={save}
        disabled={saving}
        className="fb-btn-primary w-full py-3"
        style={saved ? { background: '#16a34a' } : {}}
      >
        {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Settings'}
      </button>
    </div>
  )
}
