import React, { useState } from 'react'

const MODE_META = {
  clock:    { label: 'Clock',          icon: '🕐', desc: 'Live time & date' },
  weather:  { label: 'Weather',        icon: '🌤', desc: 'Current conditions' },
  news:     { label: 'News',           icon: '📰', desc: 'Top headlines' },
  quotes:   { label: 'Quotes',         icon: '💬', desc: 'Inspirational quotes' },
  calendar: { label: 'Calendar',       icon: '📅', desc: 'Upcoming events' },
  text:     { label: 'Text Messages',  icon: '✏️', desc: 'Custom messages' },
}

export default function ModeSelector({ modes, onUpdate }) {
  const [saving, setSaving] = useState(false)

  const toggle = async (mode, currentEnabled) => {
    const modeData = modes.find(m => m.mode === mode)
    if (!modeData) return
    setSaving(true)
    await fetch(`/api/modes/${mode}`, {
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
    await fetch('/api/display/next', { method: 'POST' })
  }

  const blankDisplay = async () => {
    await fetch('/api/display/blank', { method: 'POST' })
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
        {modes.map((m) => {
          const meta = MODE_META[m.mode] || { label: m.mode, icon: '⬡', desc: '' }
          return (
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
                <span className="text-xl">{meta.icon}</span>
                <span className="flex-1 font-mono text-sm text-gray-200 font-semibold">{meta.label}</span>
                <div className={`w-2 h-2 rounded-full ${m.enabled ? 'bg-blue-400' : 'bg-gray-600'}`} />
              </div>
              <span className="text-xs text-gray-500 font-mono pl-8">{meta.desc}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
