import React, { useState } from 'react'

function ConfigField({ fieldKey, schema, value, onChange }) {
  const cls = "bg-gray-900 text-white font-mono text-sm rounded-lg px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none w-full"

  if (schema.type === 'select') {
    return (
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-400 font-mono">{schema.label}</label>
        <select value={value ?? schema.default ?? ''} onChange={e => onChange(e.target.value)} className={cls}>
          {(schema.options || []).map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        {schema.help && <p className="text-xs text-gray-600 font-mono">{schema.help}</p>}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-gray-400 font-mono">{schema.label}</label>
      <input
        type={schema.secret ? 'password' : schema.type === 'number' ? 'number' : 'text'}
        value={value ?? ''}
        placeholder={schema.placeholder ?? ''}
        onChange={e => onChange(e.target.value)}
        className={cls}
      />
      {schema.help && <p className="text-xs text-gray-600 font-mono">{schema.help}</p>}
    </div>
  )
}

export default function ModeSelector({ modes, screenId = 'main', onUpdate }) {
  const [saving, setSaving] = useState(false)
  const [configuringMode, setConfiguringMode] = useState(null)
  const [configDraft, setConfigDraft] = useState({})
  const [configSaving, setConfigSaving] = useState(false)

  const qs = `?screen=${encodeURIComponent(screenId)}`

  const toggle = async (mode, currentEnabled) => {
    const modeData = modes.find(m => m.mode === mode)
    if (!modeData) return
    setSaving(true)
    await fetch(`/api/modes/${mode}${qs}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode,
        enabled: !currentEnabled,
        sort_order: modeData.sort_order,
        config: modeData.config || {},
      }),
    })
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
    await fetch(`/api/modes/${configuringMode}${qs}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: configuringMode,
        enabled: modeData.enabled,
        sort_order: modeData.sort_order,
        config: configDraft,
      }),
    })
    setConfigSaving(false)
    setConfiguringMode(null)
    onUpdate()
  }

  const nextMode = async () => {
    await fetch(`/api/display/next${qs}`, { method: 'POST' })
  }

  const blankDisplay = async () => {
    await fetch(`/api/display/blank${qs}`, { method: 'POST' })
  }

  const configuringData = configuringMode ? modes.find(m => m.mode === configuringMode) : null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-mono text-gray-200 font-semibold tracking-wider uppercase">
          Display Modes
        </h2>
        <div className="flex gap-2">
          <button
            onClick={nextMode}
            className="bg-gray-700 hover:bg-gray-600 text-white font-mono text-xs rounded-lg px-3 py-1.5 transition-colors"
          >
            NEXT →
          </button>
          <button
            onClick={blankDisplay}
            className="bg-gray-700 hover:bg-gray-600 text-gray-400 font-mono text-xs rounded-lg px-3 py-1.5 transition-colors"
          >
            BLANK
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {modes.map((m) => {
          const hasConfig = m.config_schema && Object.keys(m.config_schema).length > 0
          const isConfiguring = configuringMode === m.mode
          return (
            <button
              key={m.mode}
              onClick={() => toggle(m.mode, m.enabled)}
              disabled={saving}
              className={`
                flex flex-col items-start gap-1 rounded-xl p-3 border transition-all text-left relative
                ${m.enabled
                  ? 'bg-blue-900/40 border-blue-600 shadow-lg shadow-blue-900/20'
                  : 'bg-gray-800 border-gray-700 opacity-60 hover:opacity-80'
                }
                ${isConfiguring ? 'ring-2 ring-yellow-500/60' : ''}
              `}
            >
              <div className="flex items-center gap-2 w-full">
                <span className="text-xl">{m.icon ?? '⬡'}</span>
                <span className="flex-1 font-mono text-sm text-gray-200 font-semibold">{m.label ?? m.mode}</span>
                <div className="flex items-center gap-1">
                  {hasConfig && (
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(e) => openConfig(e, m)}
                      onKeyDown={(e) => e.key === 'Enter' && openConfig(e, m)}
                      className={`w-5 h-5 flex items-center justify-center rounded transition-colors text-xs
                        ${isConfiguring ? 'text-yellow-400' : 'text-gray-500 hover:text-gray-300'}`}
                      title="Configure"
                    >
                      ⚙
                    </span>
                  )}
                  <div className={`w-2 h-2 rounded-full ${m.enabled ? 'bg-blue-400' : 'bg-gray-600'}`} />
                </div>
              </div>
              <span className="text-xs text-gray-500 font-mono pl-8">{m.description ?? ''}</span>
            </button>
          )
        })}
      </div>

      {/* Inline config panel */}
      {configuringData && configuringData.config_schema && (
        <div className="bg-gray-800 border border-yellow-600/40 rounded-xl p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-base">{configuringData.icon}</span>
              <span className="font-mono text-sm text-gray-200 font-semibold">
                {configuringData.label} — Configuration
              </span>
            </div>
            <button
              onClick={() => setConfiguringMode(null)}
              className="text-gray-500 hover:text-gray-300 font-mono text-lg leading-none"
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
                onChange={(val) => setConfigDraft(prev => ({ ...prev, [key]: val }))}
              />
            ))}
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={saveConfig}
              disabled={configSaving}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-mono text-sm rounded-xl py-2.5 font-semibold tracking-wider transition-colors"
            >
              {configSaving ? 'SAVING…' : 'SAVE CONFIG'}
            </button>
            <button
              onClick={() => setConfiguringMode(null)}
              className="bg-gray-700 hover:bg-gray-600 text-gray-300 font-mono text-sm rounded-xl px-4 transition-colors"
            >
              CANCEL
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
