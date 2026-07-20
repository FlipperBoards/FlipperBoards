import React, { useState } from 'react'
import { apiFetch, apiJson } from '../../utils/api'
import { useToast } from '../Toast'

function ConfigField({ fieldKey, schema, value, onChange }) {
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

export default function ModeSelector({ modes, screenId = 'main', onUpdate }) {
  const [saving, setSaving] = useState(false)
  const [configuringMode, setConfiguringMode] = useState(null)
  const [configDraft, setConfigDraft] = useState({})
  const [configSaving, setConfigSaving] = useState(false)
  const showToast = useToast()

  const qs = `?screen=${encodeURIComponent(screenId)}`

  const toggle = async (mode, currentEnabled) => {
    const modeData = modes.find(m => m.mode === mode)
    if (!modeData) return
    setSaving(true)
    try {
      await apiJson(`/api/modes/${mode}${qs}`, 'PUT',
                    { mode, enabled: !currentEnabled, sort_order: modeData.sort_order, config: modeData.config || {} })
    } catch (err) {
      showToast(`Mode update failed: ${err.message}`)
    }
    setSaving(false)
    onUpdate()
  }

  const openConfig = (e, modeData) => {
    e.stopPropagation()
    setConfiguringMode(modeData.mode)
    setConfigDraft({ ...(modeData.config || {}) })
  }

  const saveConfig = async () => {
    const modeData = modes.find(m => m.mode === configuringMode)
    if (!modeData) return
    setConfigSaving(true)
    try {
      await apiJson(`/api/modes/${configuringMode}${qs}`, 'PUT',
                    { mode: configuringMode, enabled: modeData.enabled, sort_order: modeData.sort_order, config: configDraft })
      setConfiguringMode(null)
    } catch (err) {
      showToast(`Config save failed: ${err.message}`)
    }
    setConfigSaving(false)
    onUpdate()
  }

  const nextMode = () =>
    apiFetch(`/api/display/next${qs}`, { method: 'POST' })
      .catch(err => showToast(`Next failed: ${err.message}`))
  const blankDisplay = () =>
    apiFetch(`/api/display/blank${qs}`, { method: 'POST' })
      .catch(err => showToast(`Blank failed: ${err.message}`))

  const configuringData = configuringMode ? modes.find(m => m.mode === configuringMode) : null

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-widest" style={{ color: 'var(--text-1)' }}>
          Display Modes
        </h2>
        <div className="flex gap-2">
          <button onClick={nextMode} className="fb-btn-ghost text-[11px] px-3 py-1.5">
            Next →
          </button>
          <button onClick={blankDisplay} className="fb-btn-ghost text-[11px] px-3 py-1.5" style={{ color: 'var(--text-3)' }}>
            Blank
          </button>
        </div>
      </div>

      {/* Mode grid */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {modes.map((m) => {
          const hasConfig = m.config_schema && Object.keys(m.config_schema).length > 0
          const isConfiguring = configuringMode === m.mode
          return (
            <button
              key={m.mode}
              onClick={() => toggle(m.mode, m.enabled)}
              disabled={saving}
              className="flex flex-col items-start gap-1.5 rounded-xl p-3 text-left transition-all"
              style={{
                background: m.enabled ? 'var(--accent-dim)' : 'var(--surface)',
                border: `1px solid ${m.enabled ? 'var(--accent-border)' : 'var(--border)'}`,
                boxShadow: m.enabled ? '0 0 16px var(--accent-glow)' : 'none',
                opacity: m.enabled ? 1 : 0.65,
                outline: isConfiguring ? '2px solid rgba(234,179,8,0.5)' : 'none',
                outlineOffset: '2px',
              }}
            >
              <div className="flex items-center gap-2 w-full">
                <span className="text-lg leading-none">{m.icon ?? '⬡'}</span>
                <span className="flex-1 text-xs font-semibold truncate" style={{ color: 'var(--text-1)' }}>
                  {m.label ?? m.mode}
                </span>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {hasConfig && (
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={e => openConfig(e, m)}
                      onKeyDown={e => e.key === 'Enter' && openConfig(e, m)}
                      className="w-4 h-4 flex items-center justify-center rounded text-[10px] transition-colors"
                      style={{ color: isConfiguring ? '#eab308' : 'var(--text-3)' }}
                      title="Configure"
                    >
                      ⚙
                    </span>
                  )}
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: m.enabled ? 'var(--accent)' : 'var(--text-3)' }}
                  />
                </div>
              </div>
              {m.description && (
                <span className="text-[10px] leading-tight pl-7" style={{ color: 'var(--text-3)' }}>
                  {m.description}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Inline config panel */}
      {configuringData?.config_schema && (
        <div
          className="rounded-xl p-4 space-y-4"
          style={{
            background: 'rgba(234,179,8,0.05)',
            border: '1px solid rgba(234,179,8,0.25)',
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-base">{configuringData.icon}</span>
              <span className="text-xs font-semibold" style={{ color: 'var(--text-1)' }}>
                {configuringData.label} — Config
              </span>
            </div>
            <button
              onClick={() => setConfiguringMode(null)}
              className="text-lg leading-none transition-colors"
              style={{ color: 'var(--text-3)' }}
            >
              ×
            </button>
          </div>

          <div className="space-y-3">
            {Object.entries(configuringData.config_schema).map(([key, schema]) => (
              <ConfigField
                key={key}
                fieldKey={key}
                schema={schema}
                value={configDraft[key]}
                onChange={val => setConfigDraft(prev => ({ ...prev, [key]: val }))}
              />
            ))}
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={saveConfig}
              disabled={configSaving}
              className="fb-btn-primary flex-1"
              style={{ background: '#854d0e', borderColor: 'rgba(234,179,8,0.3)' }}
            >
              {configSaving ? 'Saving…' : 'Save Config'}
            </button>
            <button onClick={() => setConfiguringMode(null)} className="fb-btn-ghost px-4">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
