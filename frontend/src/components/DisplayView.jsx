import React, { useState, useEffect } from 'react'
import SplitFlapDisplay from './SplitFlapDisplay'
import { useDisplayState } from '../hooks/useDisplayState'

function getTileSize(cols, viewportWidth) {
  // Auto-scale tile size based on cols and viewport
  const tileWidths = { xs: 20, sm: 28, md: 40, lg: 56, xl: 80 }
  const gap = 2
  const padding = 32 + 16  // frame padding
  const sizes = ['xl', 'lg', 'md', 'sm', 'xs']
  for (const sz of sizes) {
    const totalWidth = cols * (tileWidths[sz] + gap) + padding
    if (totalWidth <= viewportWidth) return sz
  }
  return 'xs'
}

export default function DisplayView() {
  const { matrix, rows, cols, mode, appSettings, connected } = useDisplayState()
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth)

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const tileSize = getTileSize(cols, viewportWidth)
  const bgColor = appSettings.bg_color || '#111111'
  const tileBgColor = appSettings.tile_bg_color || '#2a2a2a'
  const tileColor = appSettings.tile_color || '#ffffff'

  const modeLabels = {
    clock: 'CLOCK',
    weather: 'WEATHER',
    news: 'NEWS',
    quotes: 'QUOTE',
    calendar: 'CALENDAR',
    text: 'MESSAGE',
    text_push: 'MESSAGE',
    matrix_push: 'CUSTOM',
    blank: 'BLANK',
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center"
      style={{ background: bgColor }}
    >
      {/* Connection status */}
      {!connected && (
        <div className="fixed top-4 right-4 bg-red-900 text-red-200 text-xs px-3 py-1 rounded-full font-mono">
          CONNECTING...
        </div>
      )}

      {/* Mode indicator */}
      <div
        className="fixed top-4 left-1/2 -translate-x-1/2 text-xs font-mono tracking-widest opacity-40"
        style={{ color: tileColor }}
      >
        {modeLabels[mode] || mode.toUpperCase()}
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
      />

      {/* Remote control link */}
      <a
        href="/"
        className="fixed bottom-4 right-4 text-xs font-mono opacity-20 hover:opacity-60 transition-opacity"
        style={{ color: tileColor }}
      >
        CONTROL →
      </a>
    </div>
  )
}
