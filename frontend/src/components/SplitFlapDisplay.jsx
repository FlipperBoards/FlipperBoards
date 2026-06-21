import React, { useMemo, useRef } from 'react'
import FlapTile from './FlapTile'

const STAGGER_MS_PER_COL = 30

export default function SplitFlapDisplay({
  matrix = [],
  rows = 6,
  cols = 22,
  tileColor = '#ffffff',
  tileBgColor = '#2a2a2a',
  bgColor = '#1a1a1a',
  tileSize = 'md',
  soundEnabled = true,
  dividerWidth = 4,    // gap between tiles in px — represents dowel rods
  dividerColor = '#111111',
  physicalMode = false, // adds depth shadows for physical frame look
}) {
  const prevMatrixRef = useRef([])

  const normalizedMatrix = useMemo(() => {
    const result = []
    for (let r = 0; r < rows; r++) {
      const row = matrix[r] || []
      const normalized = []
      for (let c = 0; c < cols; c++) {
        normalized.push(row[c] ?? 0)
      }
      result.push(normalized)
    }
    return result
  }, [matrix, rows, cols])

  const staggerMap = useMemo(() => {
    const map = []
    for (let r = 0; r < rows; r++) {
      const row = []
      for (let c = 0; c < cols; c++) {
        const prevCode = prevMatrixRef.current?.[r]?.[c] ?? -1
        const newCode = normalizedMatrix[r]?.[c] ?? 0
        row.push(prevCode !== newCode ? c * STAGGER_MS_PER_COL : 0)
      }
      map.push(row)
    }
    prevMatrixRef.current = normalizedMatrix
    return map
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [normalizedMatrix])

  // Physical mode tile shadow — makes each tile look inset/3D
  const tileShadow = physicalMode
    ? 'inset 0 1px 2px rgba(0,0,0,0.7), inset 0 -1px 1px rgba(255,255,255,0.04)'
    : undefined

  const colGap = `${dividerWidth}px`
  const rowGap = `${dividerWidth}px`

  return (
    <div
      className="inline-flex flex-col items-center rounded-lg shadow-2xl"
      style={{
        background: bgColor,
        padding: physicalMode ? `${dividerWidth * 3}px` : '16px',
        boxShadow: physicalMode
          ? `0 8px 32px rgba(0,0,0,0.9), inset 0 0 0 2px rgba(255,255,255,0.04)`
          : `0 0 40px rgba(0,0,0,0.8), inset 0 0 20px rgba(0,0,0,0.5)`,
      }}
    >
      {/* Header bar */}
      {!physicalMode && (
        <div className="w-full flex items-center justify-between mb-2 px-2">
          <div className="flex gap-1">
            <div className="w-2 h-2 rounded-full bg-red-600 opacity-70" />
            <div className="w-2 h-2 rounded-full bg-yellow-500 opacity-70" />
            <div className="w-2 h-2 rounded-full bg-green-500 opacity-70" />
          </div>
          <div className="text-xs text-gray-600 font-mono tracking-widest uppercase">FlipperBoards</div>
          <div className="w-2 h-2 rounded-full bg-blue-500 opacity-40 animate-pulse" />
        </div>
      )}

      {/* Tile grid — background color fills the divider gaps */}
      <div
        className="flex flex-col"
        style={{
          gap: rowGap,
          background: dividerColor,
          borderRadius: physicalMode ? '2px' : '4px',
          padding: physicalMode ? `${dividerWidth}px` : '0',
        }}
      >
        {normalizedMatrix.map((row, r) => (
          <div key={r} className="flex" style={{ gap: colGap }}>
            {row.map((code, c) => (
              <FlapTile
                key={`${r}-${c}`}
                code={code}
                tileColor={tileColor}
                tileBgColor={tileBgColor}
                size={tileSize}
                delay={staggerMap[r]?.[c] ?? 0}
                soundEnabled={soundEnabled}
                extraShadow={tileShadow}
              />
            ))}
          </div>
        ))}
      </div>

      {!physicalMode && (
        <div className="w-full mt-2">
          <div className="h-px bg-gray-700 w-full opacity-50" />
        </div>
      )}
    </div>
  )
}
