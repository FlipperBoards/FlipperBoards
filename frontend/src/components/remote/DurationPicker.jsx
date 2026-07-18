import React, { useState } from 'react'

/** Shared "Display for" duration control: presets + custom seconds.
 * value is a string: '' = until changed, otherwise seconds. */
export default function DurationPicker({ value, onChange, label = 'Display for' }) {
  const presets = [
    { label: 'Until changed', v: '' },
    { label: '10s',  v: '10' },
    { label: '30s',  v: '30' },
    { label: '1 min', v: '60' },
    { label: '5 min', v: '300' },
  ]
  const isPreset = presets.some(p => p.v === value)
  const [custom, setCustom] = useState(false)

  const handleSelect = v => {
    if (v === '__custom__') { setCustom(true); onChange('60') }
    else { setCustom(false); onChange(v) }
  }

  if (custom || (!isPreset && value !== '')) {
    return (
      <div className="flex items-center gap-1.5">
        <label className="section-label whitespace-nowrap">{label}</label>
        <input
          type="number" min={1} max={86400}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-16 text-center fb-input py-1"
        />
        <span className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>sec</span>
        <button
          type="button"
          onClick={() => { setCustom(false); onChange('') }}
          className="text-[10px] font-mono opacity-50 hover:opacity-100"
          style={{ color: 'var(--text-3)' }}
        >
          ×
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5">
      <label className="section-label whitespace-nowrap">{label}</label>
      <select
        value={value}
        onChange={e => handleSelect(e.target.value)}
        className="fb-input py-1 text-[11px]"
      >
        {presets.map(p => <option key={p.v} value={p.v}>{p.label}</option>)}
        <option value="__custom__">Custom…</option>
      </select>
    </div>
  )
}
