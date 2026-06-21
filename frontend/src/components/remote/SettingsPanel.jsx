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

export default function SettingsPanel({ settings: initialSettings, onUpdate }) {
  const [s, setS] = useState(initialSettings || {})
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setS(initialSettings || {})
  }, [initialSettings])

  const handleChange = (key, value) => {
    setS(prev => ({ ...prev, [key]: value }))
  }

  const save = async () => {
    const body = {
      rows: Number(s.rows) || 6,
      cols: Number(s.cols) || 22,
      rotation_interval: Number(s.rotation_interval) || 30,
      tile_color: s.tile_color || '#ffffff',
      bg_color: s.bg_color || '#111111',
      tile_bg_color: s.tile_bg_color || '#222222',
      timezone: s.timezone || 'UTC',
      clock_format: s.clock_format || '12h',
      show_date: s.show_date !== 'false',
      weather_location: s.weather_location || '',
      weather_units: s.weather_units || 'imperial',
      weather_api_key: s.weather_api_key || '',
      news_api_key: s.news_api_key || '',
      calendar_ical_url: s.calendar_ical_url || '',
      sound_enabled: s.sound_enabled !== 'false',
    }
    await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
    onUpdate()
  }

  const applyPreset = (preset) => {
    setS(prev => ({
      ...prev,
      tile_color: preset.tileColor,
      tile_bg_color: preset.tileBgColor,
      bg_color: preset.bgColor,
    }))
  }

  const Field = ({ label, children }) => (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-gray-500 font-mono uppercase tracking-wider">{label}</label>
      {children}
    </div>
  )

  const inputCls = "bg-gray-800 text-white font-mono text-sm rounded-lg px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none w-full"
  const selectCls = inputCls

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-mono text-gray-200 font-semibold tracking-wider uppercase">
        Settings
      </h2>

      {/* Display size */}
      <section className="space-y-3">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-widest border-b border-gray-700 pb-1">
          Display
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Rows">
            <input type="number" min={1} max={12} value={s.rows || 6}
              onChange={e => handleChange('rows', e.target.value)} className={inputCls} />
          </Field>
          <Field label="Columns">
            <input type="number" min={1} max={40} value={s.cols || 22}
              onChange={e => handleChange('cols', e.target.value)} className={inputCls} />
          </Field>
        </div>
        <Field label="Rotation Interval (seconds)">
          <input type="number" min={5} max={3600} value={s.rotation_interval || 30}
            onChange={e => handleChange('rotation_interval', e.target.value)} className={inputCls} />
        </Field>
      </section>

      {/* Theme */}
      <section className="space-y-3">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-widest border-b border-gray-700 pb-1">
          Theme
        </div>
        <div className="flex flex-wrap gap-2">
          {TILE_PRESETS.map(preset => (
            <button
              key={preset.label}
              onClick={() => applyPreset(preset)}
              className="px-3 py-1.5 rounded-lg border border-gray-600 font-mono text-xs transition-colors hover:border-gray-400"
              style={{ background: preset.bgColor, color: preset.tileColor }}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Tile Text">
            <div className="flex items-center gap-2">
              <input type="color" value={s.tile_color || '#ffffff'}
                onChange={e => handleChange('tile_color', e.target.value)}
                className="w-10 h-9 rounded border border-gray-600 cursor-pointer bg-transparent" />
              <span className="text-xs text-gray-500 font-mono">{s.tile_color || '#ffffff'}</span>
            </div>
          </Field>
          <Field label="Tile BG">
            <div className="flex items-center gap-2">
              <input type="color" value={s.tile_bg_color || '#222222'}
                onChange={e => handleChange('tile_bg_color', e.target.value)}
                className="w-10 h-9 rounded border border-gray-600 cursor-pointer bg-transparent" />
              <span className="text-xs text-gray-500 font-mono">{s.tile_bg_color || '#222222'}</span>
            </div>
          </Field>
          <Field label="Background">
            <div className="flex items-center gap-2">
              <input type="color" value={s.bg_color || '#111111'}
                onChange={e => handleChange('bg_color', e.target.value)}
                className="w-10 h-9 rounded border border-gray-600 cursor-pointer bg-transparent" />
              <span className="text-xs text-gray-500 font-mono">{s.bg_color || '#111111'}</span>
            </div>
          </Field>
        </div>
      </section>

      {/* Clock */}
      <section className="space-y-3">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-widest border-b border-gray-700 pb-1">
          Clock
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Format">
            <select value={s.clock_format || '12h'}
              onChange={e => handleChange('clock_format', e.target.value)} className={selectCls}>
              <option value="12h">12-hour</option>
              <option value="24h">24-hour</option>
            </select>
          </Field>
          <Field label="Show Date">
            <select value={s.show_date === 'false' ? 'false' : 'true'}
              onChange={e => handleChange('show_date', e.target.value)} className={selectCls}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </Field>
        </div>
        <Field label="Timezone">
          <select value={s.timezone || 'UTC'}
            onChange={e => handleChange('timezone', e.target.value)} className={selectCls}>
            {TIMEZONES.map(tz => (
              <option key={tz} value={tz}>{tz}</option>
            ))}
          </select>
        </Field>
      </section>

      {/* Weather */}
      <section className="space-y-3">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-widest border-b border-gray-700 pb-1">
          Weather <span className="text-gray-700 normal-case">(OpenWeatherMap)</span>
        </div>
        <Field label="Location (City, Country)">
          <input type="text" placeholder="Portland,US" value={s.weather_location || ''}
            onChange={e => handleChange('weather_location', e.target.value)} className={inputCls} />
        </Field>
        <Field label="API Key">
          <input type="password" placeholder="OpenWeatherMap API key" value={s.weather_api_key || ''}
            onChange={e => handleChange('weather_api_key', e.target.value)} className={inputCls} />
        </Field>
        <Field label="Units">
          <select value={s.weather_units || 'imperial'}
            onChange={e => handleChange('weather_units', e.target.value)} className={selectCls}>
            <option value="imperial">Imperial (°F)</option>
            <option value="metric">Metric (°C)</option>
          </select>
        </Field>
      </section>

      {/* News */}
      <section className="space-y-3">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-widest border-b border-gray-700 pb-1">
          News <span className="text-gray-700 normal-case">(NewsAPI or RSS fallback)</span>
        </div>
        <Field label="API Key">
          <input type="password" placeholder="NewsAPI key (optional)" value={s.news_api_key || ''}
            onChange={e => handleChange('news_api_key', e.target.value)} className={inputCls} />
        </Field>
      </section>

      {/* Calendar */}
      <section className="space-y-3">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-widest border-b border-gray-700 pb-1">
          Calendar
        </div>
        <Field label="iCal URL">
          <input type="url" placeholder="https://calendar.google.com/calendar/ical/..." value={s.calendar_ical_url || ''}
            onChange={e => handleChange('calendar_ical_url', e.target.value)} className={inputCls} />
        </Field>
      </section>

      {/* Save */}
      {/* Sound */}
      <section className="space-y-3">
        <div className="text-xs text-gray-600 font-mono uppercase tracking-widest border-b border-gray-700 pb-1">
          Sound
        </div>
        <Field label="Flip Sound Effects">
          <select value={s.sound_enabled === 'false' ? 'false' : 'true'}
            onChange={e => handleChange('sound_enabled', e.target.value)} className={selectCls}>
            <option value="true">Enabled</option>
            <option value="false">Disabled</option>
          </select>
        </Field>
      </section>

      <button
        onClick={save}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-mono font-semibold rounded-xl py-3 transition-colors tracking-widest uppercase"
      >
        {saved ? '✓ SAVED' : 'SAVE SETTINGS'}
      </button>
    </div>
  )
}
