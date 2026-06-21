import React, { useState, useEffect, useCallback } from 'react'
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
          if (!released) acquire()  // re-acquire on visibility change
        })
      } catch {
        // Wake lock not available or permission denied — silent fail
      }
    }

    acquire()
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') acquire()
    })

    return () => {
      released = true
      lockRef.current?.release()
    }
  }, [])
}

export default function DisplayView() {
  const { matrix, rows, cols, mode, appSettings, connected } = useDisplayState()
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

  // Auto-hide controls after 4s of inactivity
  useEffect(() => {
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
  }, [])

  const handleClick = useCallback(() => {
    if (!audioUnlocked) {
      unlockAudio()
      setAudioUnlocked(true)
    }
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

  const modeLabels = {
    clock: 'CLOCK', weather: 'WEATHER', news: 'NEWS',
    quotes: 'QUOTE', calendar: 'CALENDAR', text: 'MESSAGE',
    text_push: 'MESSAGE', matrix_push: 'CUSTOM', blank: 'BLANK',
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center select-none"
      style={{ background: bgColor }}
      onClick={handleClick}
    >
      {/* Connection status */}
      {!connected && (
        <div className="fixed top-4 right-4 bg-red-900/80 text-red-200 text-xs px-3 py-1 rounded-full font-mono animate-pulse">
          CONNECTING...
        </div>
      )}

      {/* Mode indicator + controls (auto-hide) */}
      <div
        className="fixed top-4 left-0 right-0 flex items-center justify-between px-4 transition-opacity duration-700"
        style={{ opacity: showControls ? 1 : 0 }}
      >
        <div className="text-xs font-mono tracking-widest opacity-30" style={{ color: tileColor }}>
          {modeLabels[mode] || mode.toUpperCase()}
        </div>
        <div className="flex gap-3">
          <button
            onClick={toggleFullscreen}
            className="text-xs font-mono opacity-20 hover:opacity-60 transition-opacity"
            style={{ color: tileColor }}
          >
            {isFullscreen ? '⊡' : '⊞'}
          </button>
          <a
            href="/"
            className="text-xs font-mono opacity-20 hover:opacity-60 transition-opacity"
            style={{ color: tileColor }}
          >
            CONTROL →
          </a>
        </div>
      </div>

      {/* Main display */}
      <SplitFlapDisplay
        matrix={matrix}
        rows={rows}
        cols={cols}
        tileColor={tileColor}
        tileBgColor={tileBgColor}
        bgColor="transparent"
        tileSize={tileSize}
        soundEnabled={soundEnabled && audioUnlocked}
      />

      {/* First-tap hint */}
      {!audioUnlocked && (
        <div
          className="fixed bottom-6 left-0 right-0 text-center text-xs font-mono opacity-20 transition-opacity"
          style={{ color: tileColor }}
        >
          TAP TO ENABLE SOUND
        </div>
      )}
    </div>
  )
}
