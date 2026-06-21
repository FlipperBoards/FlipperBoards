import React, { useState, useCallback } from 'react'
import SplitFlapDisplay from '../SplitFlapDisplay'
import TextInput from './TextInput'
import ModeSelector from './ModeSelector'
import SettingsPanel from './SettingsPanel'
import { useDisplayState } from '../../hooks/useDisplayState'

const TABS = [
  { id: 'display', label: 'Modes' },
  { id: 'text', label: 'Text' },
  { id: 'settings', label: 'Settings' },
]

export default function RemoteControl() {
  const { matrix, rows, cols, mode, appSettings, modes, connected } = useDisplayState()
  const [activeTab, setActiveTab] = useState('display')
  const [settingsKey, setSettingsKey] = useState(0)

  const refresh = useCallback(() => setSettingsKey(k => k + 1), [])

  const bgColor = appSettings.bg_color || '#111111'
  const tileBgColor = appSettings.tile_bg_color || '#2a2a2a'
  const tileColor = appSettings.tile_color || '#ffffff'

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-gray-900 border-b border-gray-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="font-mono font-bold text-lg tracking-widest text-white">
            FLIPPER<span className="text-blue-400">BOARDS</span>
          </div>
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-500'} animate-pulse`} />
        </div>
        <a
          href="/display"
          className="text-xs font-mono text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 px-3 py-1 rounded-lg transition-all"
        >
          DISPLAY VIEW →
        </a>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-6">
        {/* Mini preview */}
        <div className="overflow-x-auto">
          <div className="flex justify-center">
            <SplitFlapDisplay
              matrix={matrix}
              rows={rows}
              cols={cols}
              tileColor={tileColor}
              tileBgColor={tileBgColor}
              bgColor={bgColor}
              tileSize="xs"
            />
          </div>
        </div>

        {/* Mode badge */}
        <div className="flex items-center justify-between">
          <div className="text-xs font-mono text-gray-500 uppercase tracking-widest">
            Active: <span className="text-blue-400">{mode}</span>
          </div>
          <div className="text-xs font-mono text-gray-600">
            {rows} × {cols}
          </div>
        </div>

        {/* Tab nav */}
        <div className="flex border-b border-gray-800">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex-1 py-2 font-mono text-sm uppercase tracking-wider transition-colors
                ${activeTab === tab.id
                  ? 'text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-500 hover:text-gray-300'
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="pb-safe">
          {activeTab === 'display' && (
            <ModeSelector modes={modes} onUpdate={refresh} />
          )}
          {activeTab === 'text' && (
            <TextInput onRefresh={refresh} />
          )}
          {activeTab === 'settings' && (
            <SettingsPanel
              key={settingsKey}
              settings={appSettings}
              onUpdate={refresh}
            />
          )}
        </div>
      </main>
    </div>
  )
}
