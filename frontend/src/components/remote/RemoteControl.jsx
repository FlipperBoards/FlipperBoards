import React, { useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import SplitFlapDisplay from '../SplitFlapDisplay'
import TextInput from './TextInput'
import ModeSelector from './ModeSelector'
import SettingsPanel from './SettingsPanel'
import ImageUpload from './ImageUpload'
import UniversalPlaylist from './UniversalPlaylist'
import ScreenManager from './ScreenManager'
import ScreenDesigner from './ScreenDesigner'
import { useDisplayState } from '../../hooks/useDisplayState'

const TABS = [
  { id: 'display',  label: 'Modes',   Icon: IconModes },
  { id: 'text',     label: 'Text',    Icon: IconText },
  { id: 'image',    label: 'Image',   Icon: IconImage },
  { id: 'design',   label: 'Design',  Icon: IconDesign },
  { id: 'playlist', label: 'Queue',   Icon: IconQueue },
  { id: 'screens',  label: 'Screens', Icon: IconScreens },
  { id: 'settings', label: 'Config',  Icon: IconSettings },
]

function IconModes({ active }) {
  const c = active ? '#3b82f6' : '#475569'
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect x="2.5" y="2.5" width="6.5" height="6.5" rx="1.5" fill={c}/>
      <rect x="11"  y="2.5" width="6.5" height="6.5" rx="1.5" fill={c}/>
      <rect x="2.5" y="11"  width="6.5" height="6.5" rx="1.5" fill={c}/>
      <rect x="11"  y="11"  width="6.5" height="6.5" rx="1.5" fill={c}/>
    </svg>
  )
}

function IconText({ active }) {
  const c = active ? '#3b82f6' : '#475569'
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill={c} aria-hidden>
      <rect x="3" y="4"  width="14" height="2" rx="1"/>
      <rect x="3" y="9"  width="10" height="2" rx="1"/>
      <rect x="3" y="14" width="12" height="2" rx="1"/>
    </svg>
  )
}

function IconImage({ active }) {
  const c = active ? '#3b82f6' : '#475569'
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect x="2" y="3.5" width="16" height="13" rx="2" stroke={c} strokeWidth="1.5"/>
      <circle cx="7" cy="8" r="1.5" fill={c}/>
      <path d="M2 14l4.5-4.5 3 2.5 3-3.5 5 5" stroke={c} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
    </svg>
  )
}

function IconDesign({ active }) {
  const c = active ? '#3b82f6' : '#475569'
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect x="2" y="2" width="7" height="7" rx="1" fill={c} opacity="0.9"/>
      <rect x="11" y="2" width="7" height="7" rx="1" fill={c} opacity="0.5"/>
      <rect x="2" y="11" width="7" height="7" rx="1" fill={c} opacity="0.5"/>
      <rect x="11" y="11" width="7" height="7" rx="1" fill={c} opacity="0.9"/>
      <path d="M13.5 13.5l3 3M13.5 16.5l3-3" stroke={active ? '#fff' : '#1e293b'} strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  )
}

function IconQueue({ active }) {
  const c = active ? '#3b82f6' : '#475569'
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill={c} aria-hidden>
      <rect x="2.5" y="5"   width="3" height="3" rx="0.75"/>
      <rect x="7.5" y="5.5" width="10" height="2" rx="1"/>
      <rect x="2.5" y="9"   width="3" height="3" rx="0.75"/>
      <rect x="7.5" y="9.5" width="10" height="2" rx="1"/>
      <rect x="2.5" y="13"  width="3" height="3" rx="0.75"/>
      <rect x="7.5" y="13.5" width="10" height="2" rx="1"/>
    </svg>
  )
}

function IconScreens({ active }) {
  const c = active ? '#3b82f6' : '#475569'
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect x="2" y="3" width="16" height="11" rx="2" stroke={c} strokeWidth="1.5"/>
      <path d="M7 17h6M10 14v3" stroke={c} strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}

function IconSettings({ active }) {
  const c = active ? '#3b82f6' : '#475569'
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
      <circle cx="10" cy="10" r="2.5" stroke={c} strokeWidth="1.5"/>
      <path
        d="M10 2v1.5M10 16.5V18M2 10h1.5M16.5 10H18M4.4 4.4l1.06 1.06M14.54 14.54l1.06 1.06M15.6 4.4l-1.06 1.06M5.46 14.54l-1.06 1.06"
        stroke={c} strokeWidth="1.5" strokeLinecap="round"
      />
    </svg>
  )
}

export default function RemoteControl() {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeScreenId = searchParams.get('screen') || 'main'

  const { matrix, colorMatrix, photoUrl, rows, cols, mode, appSettings, modes, screens, connected } =
    useDisplayState(activeScreenId)

  const [activeTab, setActiveTab] = useState('display')
  const [refreshKey, setRefreshKey] = useState(0)

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  const selectScreen = useCallback((sid) => {
    setSearchParams(sid === 'main' ? {} : { screen: sid })
  }, [setSearchParams])

  const bgColor        = appSettings.bg_color        || '#1a1a1a'
  const tileBgColor    = appSettings.tile_bg_color   || '#2a2a2a'
  const tileColor      = appSettings.tile_color      || '#ffffff'
  const dividerWidth   = parseInt(appSettings.divider_width || '4', 10)
  const dividerColor   = appSettings.divider_color   || '#111111'
  const physicalMode   = appSettings.physical_mode   === 'true'

  const activeScreen = screens.find(s => s.id === activeScreenId)

  return (
    <div className="min-h-screen font-mono" style={{ background: 'var(--bg-base)' }}>

      {/* ── Header ── */}
      <header
        className="sticky top-0 z-40 flex items-center justify-between px-4 h-14"
        style={{
          background: 'rgba(9,9,19,0.85)',
          backdropFilter: 'blur(16px)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        {/* Wordmark */}
        <span className="text-sm font-bold tracking-[0.2em] uppercase" style={{ color: 'var(--text-1)' }}>
          Flipper<span style={{ color: 'var(--accent)' }}>Boards</span>
        </span>

        {/* Center: screen indicator */}
        <button
          onClick={() => setActiveTab('screens')}
          className="flex items-center gap-2 rounded-full px-3 py-1 text-xs transition-all"
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            color: 'var(--text-2)',
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ background: connected ? '#4ade80' : '#ef4444', boxShadow: connected ? '0 0 6px #4ade80' : 'none' }}
          />
          <span className="max-w-[120px] truncate" style={{ color: 'var(--text-1)' }}>
            {activeScreen?.name || activeScreenId}
          </span>
          <span style={{ color: 'var(--text-3)' }}>▾</span>
        </button>

        {/* Display link */}
        <a
          href={`/display?screen=${activeScreenId}`}
          target="_blank"
          rel="noreferrer"
          className="text-xs transition-colors"
          style={{ color: 'var(--text-3)' }}
          onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-1)' }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-3)' }}
        >
          Display ↗
        </a>
      </header>

      {/* ── Scrollable content ── */}
      <main className="max-w-2xl mx-auto px-4 pt-5 pb-28 space-y-5">

        {/* Mini preview */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{
            background: 'rgba(0,0,0,0.4)',
            border: '1px solid var(--border)',
            padding: '16px',
          }}
        >
          <div className="overflow-x-auto">
            <div className="flex justify-center">
              <SplitFlapDisplay
                matrix={matrix}
                colorMatrix={colorMatrix}
                photoUrl={photoUrl}
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
          {/* Status row */}
          <div className="flex items-center justify-between mt-3 px-1">
            <span
              className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full"
              style={{
                background: 'var(--accent-dim)',
                color: 'var(--accent)',
                border: '1px solid var(--accent-border)',
                letterSpacing: '0.12em',
              }}
            >
              {mode || 'clock'}
            </span>
            <span className="text-[10px]" style={{ color: 'var(--text-3)' }}>
              {cols} × {rows}
            </span>
          </div>
        </div>

        {/* ── Tab panels ── */}
        <div>
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
              rows={rows}
              cols={cols}
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
          {activeTab === 'design' && (
            <ScreenDesigner
              key={`${activeScreenId}-${refreshKey}`}
              rows={rows}
              cols={cols}
              screenId={activeScreenId}
            />
          )}
          {activeTab === 'playlist' && (
            <UniversalPlaylist
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

      {/* ── Bottom navigation ── */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-50"
        style={{
          background: 'rgba(9,9,19,0.90)',
          backdropFilter: 'blur(20px)',
          borderTop: '1px solid var(--border)',
        }}
      >
        <div className="max-w-2xl mx-auto flex">
          {TABS.map(({ id, label, Icon }) => {
            const isActive = activeTab === id
            return (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className="relative flex-1 flex flex-col items-center justify-center gap-1 py-2.5 transition-all"
                style={{ color: isActive ? 'var(--accent)' : 'var(--text-3)' }}
              >
                {isActive && (
                  <span
                    className="absolute top-0 left-1/2 -translate-x-1/2 rounded-b-full"
                    style={{
                      width: '28px',
                      height: '2px',
                      background: 'var(--accent)',
                      boxShadow: '0 0 8px var(--accent-glow)',
                    }}
                  />
                )}
                <Icon active={isActive} />
                <span
                  className="leading-none"
                  style={{
                    fontSize: '9px',
                    fontWeight: isActive ? '600' : '400',
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                  }}
                >
                  {label}
                </span>
                {id === 'screens' && screens.length > 1 && (
                  <span
                    className="absolute top-2 right-[calc(50%-12px)] text-[8px] font-bold leading-none flex items-center justify-center rounded-full"
                    style={{
                      width: '14px',
                      height: '14px',
                      background: 'var(--accent)',
                      color: '#fff',
                    }}
                  >
                    {screens.length}
                  </span>
                )}
              </button>
            )
          })}
        </div>
        {/* iOS safe area spacer */}
        <div style={{ height: 'env(safe-area-inset-bottom, 0px)' }} />
      </nav>
    </div>
  )
}
