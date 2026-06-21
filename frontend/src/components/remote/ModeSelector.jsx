import React, { useState } from 'react'

export default function ModeSelector({ modes, screenId = 'main', onUpdate }) {
  const [saving, setSaving] = useState(false)

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

  const nextMode = async () => {
    await fetch(`/api/display/next${qs}`, { method: 'POST' })
  }

  const blankDisplay = async () => {
    await fetch(`/api/display/blank${qs}`, { method: 'POST' })
  }

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
        {modes.map((m) => (
          <button
            key={m.mode}
            onClick={() => toggle(m.mode, m.enabled)}
            disabled={saving}
            className={`
              flex flex-col items-start gap-1 rounded-xl p-3 border transition-all text-left
              ${m.enabled
                ? 'bg-blue-900/40 border-blue-600 shadow-lg shadow-blue-900/20'
                : 'bg-gray-800 border-gray-700 opacity-60 hover:opacity-80'
              }
            `}
          >
            <div className="flex items-center gap-2 w-full">
              <span className="text-xl">{m.icon ?? '⬡'}</span>
              <span className="flex-1 font-mono text-sm text-gray-200 font-semibold">{m.label ?? m.mode}</span>
              <div className={`w-2 h-2 rounded-full ${m.enabled ? 'bg-blue-400' : 'bg-gray-600'}`} />
            </div>
            <span className="text-xs text-gray-500 font-mono pl-8">{m.description ?? ''}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
