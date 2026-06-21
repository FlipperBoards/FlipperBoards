import React, { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import SplitFlapDisplay from './SplitFlapDisplay'
import { useDisplayState } from '../hooks/useDisplayState'
import { unlockAudio } from '../utils/audio'

function getTileSize(cols, viewportWidth) {
  const tileWidths = { xs: 20, sm: 28, md: 40, lg: 56, xl: 80 }
  const gap = 2
  const padding = 48
  const sizes = ['xl', 'lg', 'md', 'sm', 'xs']
  for (const sz of sizes) {
    const totalWidth = cols * (tileWidths[sz] + gap) + padding
    if (totalWidth <= viewportWidth) return sz
  }
  return 'xs'
}

function useWakeLock() {
  const lockRef = React.useRef(null)
  useEffect(() => {
    let released = false
    async function acquire() {
      if (!('wakeLock' in navigator)) return
      try {
        lockRef.current = await navigator.wakeLock.request('screen')
        lockRef.current.addEventListener('release', () => {
          if (!released) acquire()
        })
      } catch { /* silent */ }
    }
    acquire()
    const onVisible = () => { if (document.visibilityState === 'visible') acquire() }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      released = true
      lockRef.current?.release()
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])
}

export default function DisplayView() {
  const [searchParams] = useSearchParams()
  const screenId = searchParams.get('screen') || 'main'
  const kiosk = searchParams.get('kiosk') === '1'

  const { matrix, colorMatrix, photoUrl, rows, cols, mode, appSettings, connected } = useDisplayState(screenId)
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [audioUnlocked, setAudioUnlocked] = useState(false)
  const [showControls, setShowControls] = useState(true)
  const idleTimer = React.useRef(null)

  useWakeLock()

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    if (kiosk) return
    const resetIdle = () => {
      setShowControls(true)
      clearTimeout(idleTimer.current)
      idleTimer.current = setTimeout(() => setShowControls(false), 4000)
    }
    resetIdle()
    window.addEventListener('mousemove', resetIdle)
    window.addEventListener('touchstart', resetIdle)
    return () => {
      clearTimeout(idleTimer.current)
      window.removeEventListener('mousemove', resetIdle)
      window.removeEventListener('touchstart', resetIdle)
    }
  }, [kiosk])

  const handleClick = useCallback(() => {
    if (!audioUnlocked) { unlockAudio(); setAudioUnlocked(true) }
  }, [audioUnlocked])

  const toggleFullscreen = useCallback(async () => {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen?.()
      setIsFullscreen(true)
    } else {
      await document.exitFullscreen?.()
      setIsFullscreen(false)
    }
  }, [])

  const tileSize = getTileSize(cols, viewportWidth)
  const bgColor = appSettings.bg_color || '#111111'
  const tileBgColor = appSettings.tile_bg_color || '#2a2a2a'
  const tileColor = appSettings.tile_color || '#ffffff'
  const soundEnabled = appSettings.sound_enabled !== 'false'
  const dividerWidth = parseInt(appSettings.divider_width || '4', 10)
  const dividerColor = appSettings.divider_color || '#111111'
  const physicalMode = appSettings.physical_mode === 'true'

  const modeLabels = {
    clock: 'CLOCK', weather: 'WEATHER', news: 'NEWS',
    quotes: 'QUOTE', calendar: 'CALENDAR', text: 'MESSAGE',
    text_push: 'MESSAGE', matrix_push: 'CUSTOM', blank: 'BLANK',
    image_push: 'IMAGE', photo_push: 'PHOTO', photo_playlist: 'PLAYLIST',
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center select-none"
      style={{ background: bgColor }}
      onClick={handleClick}
    >
      {!connected && !kiosk && (
        <div className="fixed top-4 right-4 bg-red-900/80 text-red-200 text-xs px-3 py-1 rounded-full font-mono animate-pulse">
          CONNECTING...
        </div>
      )}

      {!kiosk && (
        <div
          className="fixed top-4 left-0 right-0 flex items-center justify-between px-4 transition-opacity duration-700"
          style={{ opacity: showControls ? 1 : 0, pointerEvents: showControls ? 'auto' : 'none' }}
        >
          <div className="text-xs font-mono tracking-widest opacity-30" style={{ color: tileColor }}>
            {screenId !== 'main' && <span className="opacity-60">{screenId} · </span>}
            {modeLabels[mode] || mode.toUpperCase()}
          </div>
          <div className="flex gap-3">
            <button onClick={toggleFullscreen}
              className="text-xs font-mono opacity-20 hover:opacity-60 transition-opacity"
              style={{ color: tileColor }}>
              {isFullscreen ? '⊡' : '⊞'}
            </button>
            <a href={`/?screen=${screenId}`}
              className="text-xs font-mono opacity-20 hover:opacity-60 transition-opacity"
              style={{ color: tileColor }}>
              CONTROL →
            </a>
          </div>
        </div>
      )}

      <SplitFlapDisplay
        matrix={matrix}
        colorMatrix={colorMatrix}
        photoUrl={photoUrl}
        rows={rows}
        cols={cols}
        tileColor={tileColor}
        tileBgColor={tileBgColor}
        bgColor="transparent"
        tileSize={tileSize}
        soundEnabled={soundEnabled && audioUnlocked}
        dividerWidth={dividerWidth}
        dividerColor={dividerColor}
        physicalMode={physicalMode}
      />

      {!audioUnlocked && !kiosk && (
        <div className="fixed bottom-6 left-0 right-0 text-center text-xs font-mono opacity-20"
          style={{ color: tileColor }}>
          TAP TO ENABLE SOUND
        </div>
      )}
    </div>
  )
}
