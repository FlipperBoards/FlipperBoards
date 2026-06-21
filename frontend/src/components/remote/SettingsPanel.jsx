import React, { useState, useEffect } from 'react'

const TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver',
  'America/Los_Angeles', 'America/Anchorage', 'Pacific/Honolulu',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Moscow',
  'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Kolkata', 'Australia/Sydney',
]

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

export default function SettingsPanel({ settings: initialSettings, onUpdate }) {
  const [s, setS] = useState(initialSettings || {})
  const [saved, setSaved] = useState(false)

  useEffect(() => { setS(initialSettings || {}) }, [initialSettings])

  const set = (key, value) => setS(prev => ({ ...prev, [key]: value }))

  const save = async () => {
    await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rows:              Number(s.rows) || 6,
        cols:              Number(s.cols) || 22,
        rotation_interval: Number(s.rotation_interval) || 30,
        tile_color:        s.tile_color        || '#ffffff',
        bg_color:          s.bg_color          || '#111111',
        tile_bg_color:     s.tile_bg_color     || '#222222',
        timezone:          s.timezone          || 'UTC',
        clock_format:      s.clock_format      || '12h',
        show_date:         s.show_date !== 'false',
        weather_location:  s.weather_location  || '',
        weather_units:     s.weather_units     || 'imperial',
        weather_api_key:   s.weather_api_key   || '',
        news_api_key:      s.news_api_key      || '',
        calendar_ical_url: s.calendar_ical_url || '',
        sound_enabled:     s.sound_enabled !== 'false',
        divider_width:     Number(s.divider_width) || 4,
        divider_color:     s.divider_color     || '#111111',
        physical_mode:     s.physical_mode === 'true',
      }),
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
    onUpdate()
  }

  const applyPreset = (preset) =>
    setS(prev => ({ ...prev, tile_color: preset.tileColor, tile_bg_color: preset.tileBgColor, bg_color: preset.bgColor }))

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--text-1)' }}>
        Settings
      </h2>

      {/* Display size */}
      <Section title="Display">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Rows">
            <input type="number" min={1} max={12} value={s.rows || 6}
              onChange={e => set('rows', e.target.value)} className="fb-input" />
          </Field>
          <Field label="Columns">
            <input type="number" min={1} max={40} value={s.cols || 22}
              onChange={e => set('cols', e.target.value)} className="fb-input" />
          </Field>
        </div>
        <Field label="Rotation Interval">
          <div className="flex items-center gap-2">
            <input type="number" min={5} max={3600} value={s.rotation_interval || 30}
              onChange={e => set('rotation_interval', e.target.value)} className="fb-input" />
            <span className="text-[11px] font-mono flex-shrink-0" style={{ color: 'var(--text-3)' }}>sec</span>
          </div>
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
            {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
          </select>
        </Field>
      </Section>

      {/* Weather */}
      <Section title="Weather — OpenWeatherMap">
        <Field label="Location (City, Country)">
          <input type="text" placeholder="Portland,US" value={s.weather_location || ''}
            onChange={e => set('weather_location', e.target.value)} className="fb-input" />
        </Field>
        <Field label="API Key">
          <input type="password" placeholder="OpenWeatherMap key" value={s.weather_api_key || ''}
            onChange={e => set('weather_api_key', e.target.value)} className="fb-input" />
        </Field>
        <Field label="Units">
          <select value={s.weather_units || 'imperial'} onChange={e => set('weather_units', e.target.value)} className="fb-input">
            <option value="imperial">Imperial (°F)</option>
            <option value="metric">Metric (°C)</option>
          </select>
        </Field>
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

      <button
        onClick={save}
        className="fb-btn-primary w-full py-3"
        style={saved ? { background: '#16a34a' } : {}}
      >
        {saved ? '✓ Saved' : 'Save Settings'}
      </button>
    </div>
  )
}
