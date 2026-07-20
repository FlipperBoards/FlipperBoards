import React from 'react'

/** Renders one config field from a mode's config_schema. Shared by the Modes
 * tab (ModeSelector) and per-item playlist config (UniversalPlaylist). */
export default function ConfigField({ schema, value, onChange }) {
  if (schema.type === 'select') {
    return (
      <div className="flex flex-col gap-1.5">
        <label className="section-label">{schema.label}</label>
        <select value={value ?? schema.default ?? ''} onChange={e => onChange(e.target.value)} className="fb-input">
          {(schema.options || []).map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        {schema.help && <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>{schema.help}</p>}
      </div>
    )
  }

  if (schema.type === 'multiselect') {
    const selected = Array.isArray(value) ? value : (value ?? schema.default ?? [])
    const toggle = (key) => {
      const next = selected.includes(key)
        ? selected.filter(k => k !== key)
        : [...selected, key]
      onChange(next)
    }
    return (
      <div className="flex flex-col gap-1.5">
        <label className="section-label">{schema.label}</label>
        <div className="flex flex-wrap gap-1.5">
          {(schema.options || []).map(opt => {
            const on = selected.includes(opt.value)
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggle(opt.value)}
                className="text-[11px] px-2.5 py-1 rounded-full transition-all"
                style={{
                  background: on ? 'var(--accent-dim)' : 'var(--surface)',
                  border: `1px solid ${on ? 'var(--accent-border)' : 'var(--border)'}`,
                  color: on ? 'var(--text-1)' : 'var(--text-3)',
                }}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
        {schema.help && <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>{schema.help}</p>}
      </div>
    )
  }

  if (schema.type === 'textarea') {
    return (
      <div className="flex flex-col gap-1.5">
        <label className="section-label">{schema.label}</label>
        <textarea
          rows={4}
          value={value ?? ''}
          placeholder={schema.placeholder ?? ''}
          onChange={e => onChange(e.target.value)}
          className="fb-input"
          style={{ resize: 'vertical', lineHeight: '1.5' }}
        />
        {schema.help && <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>{schema.help}</p>}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label className="section-label">{schema.label}</label>
      <input
        type={schema.secret ? 'password' : schema.type === 'number' ? 'number' : 'text'}
        value={value ?? ''}
        placeholder={schema.placeholder ?? ''}
        onChange={e => onChange(e.target.value)}
        className="fb-input"
      />
      {schema.help && <p className="text-[11px] font-mono" style={{ color: 'var(--text-3)' }}>{schema.help}</p>}
    </div>
  )
}
