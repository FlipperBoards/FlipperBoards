import React, { useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import SplitFlapDisplay from '../SplitFlapDisplay'
import TextInput from './TextInput'
import ModeSelector from './ModeSelector'
import SettingsPanel from './SettingsPanel'
import ImageUpload from './ImageUpload'
import ScreenManager from './ScreenManager'
import { useDisplayState } from '../../hooks/useDisplayState'

const TABS = [
  { id: 'screens', label: 'Screens' },
  { id: 'display', label: 'Modes' },
  { id: 'text', label: 'Text' },
  { id: 'image', label: 'Image' },
  { id: 'settings', label: 'Settings' },
]

export default function RemoteControl() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeScreenId = searchParams.get('screen') || 'main'

  const { matrix, rows, cols, mode, appSettings, modes, screens, connected } =
    useDisplayState(activeScreenId)

  const [activeTab, setActiveTab] = useState('display')
  const [refreshKey, setRefreshKey] = useState(0)

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  const selectScreen = useCallback((sid) => {
    setSearchParams(sid === 'main' ? {} : { screen: sid })
  }, [setSearchParams])

  const bgColor = appSettings.bg_color || '#111111'
  const tileBgColor = appSettings.tile_bg_color || '#2a2a2a'
  const tileColor = appSettings.tile_color || '#ffffff'
  const dividerWidth = parseInt(appSettings.divider_width || '4', 10)
  const dividerColor = appSettings.divider_color || '#111111'
  const physicalMode = appSettings.physical_mode === 'true'

  const activeScreen = screens.find(s => s.id === activeScreenId)

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-gray-900 border-b border-gray-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="font-mono font-bold text-lg tracking-widest text-white">
            FLIPPER<span className="text-blue-400">BOARDS</span>
          </div>
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-500'} ${connected ? '' : 'animate-pulse'}`} />
        </div>
        <a
          href={`/display?screen=${activeScreenId}`}
          target="_blank"
          rel="noreferrer"
          className="text-xs font-mono text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 px-3 py-1 rounded-lg transition-all"
        >
          DISPLAY →
        </a>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-5">
        {/* Active screen indicator */}
        {screens.length > 0 && (
          <div className="flex items-center justify-between">
            <div className="text-xs font-mono text-gray-500 uppercase tracking-widest">
              Controlling: <span className="text-blue-400 font-semibold">
                {activeScreen?.name || activeScreenId}
              </span>
            </div>
            <div className="text-xs font-mono text-gray-600">
              {rows} × {cols} · {mode}
            </div>
          </div>
        )}

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
              soundEnabled={false}
              dividerWidth={Math.max(1, Math.floor(dividerWidth / 2))}
              dividerColor={dividerColor}
              physicalMode={physicalMode}
            />
          </div>
        </div>

        {/* Tab nav */}
        <div className="flex border-b border-gray-800 overflow-x-auto">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                flex-shrink-0 px-4 py-2 font-mono text-sm uppercase tracking-wider transition-colors
                ${activeTab === tab.id
                  ? 'text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-500 hover:text-gray-300'
                }
              `}
            >
              {tab.label}
              {tab.id === 'screens' && screens.length > 1 && (
                <span className="ml-1 text-xs bg-blue-900 text-blue-300 rounded-full px-1.5 py-0.5">
                  {screens.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="pb-10">
          {activeTab === 'screens' && (
            <ScreenManager
              key={refreshKey}
              screens={screens}
              activeScreenId={activeScreenId}
              onSelectScreen={selectScreen}
              onRefresh={refresh}
            />
          )}
          {activeTab === 'display' && (
            <ModeSelector
              key={`${activeScreenId}-${refreshKey}`}
              modes={modes}
              screenId={activeScreenId}
              onUpdate={refresh}
            />
          )}
          {activeTab === 'text' && (
            <TextInput
              key={`${activeScreenId}-${refreshKey}`}
              screenId={activeScreenId}
              onRefresh={refresh}
            />
          )}
          {activeTab === 'image' && (
            <ImageUpload
              rows={rows}
              cols={cols}
              screenId={activeScreenId}
            />
          )}
          {activeTab === 'settings' && (
            <SettingsPanel
              key={refreshKey}
              settings={appSettings}
              onUpdate={refresh}
            />
          )}
        </div>
      </main>
    </div>
  )
}
