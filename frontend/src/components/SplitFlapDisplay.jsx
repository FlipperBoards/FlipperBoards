import React, { useMemo, useRef } from 'react'
import FlapTile from './FlapTile'

const STAGGER_MS_PER_COL = 30  // delay increment per column position

export default function SplitFlapDisplay({
  matrix = [],
  rows = 6,
  cols = 22,
  tileColor = '#ffffff',
  tileBgColor = '#2a2a2a',
  bgColor = '#1a1a1a',
  tileSize = 'md',
  soundEnabled = true,
}) {
  const prevMatrixRef = useRef([])

  // Ensure matrix is always rows×cols
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

  // Build stagger delay map: tiles that changed get a delay based on column
  const staggerMap = useMemo(() => {
    const map = []
    for (let r = 0; r < rows; r++) {
      const row = []
      for (let c = 0; c < cols; c++) {
        const prevCode = prevMatrixRef.current?.[r]?.[c] ?? -1
        const newCode = normalizedMatrix[r]?.[c] ?? 0
        const changed = prevCode !== newCode
        row.push(changed ? c * STAGGER_MS_PER_COL : 0)
      }
      map.push(row)
    }
    prevMatrixRef.current = normalizedMatrix
    return map
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [normalizedMatrix])

  return (
    <div
      className="inline-flex flex-col items-center rounded-lg p-4 shadow-2xl"
      style={{
        background: bgColor,
        boxShadow: `0 0 40px rgba(0,0,0,0.8), inset 0 0 20px rgba(0,0,0,0.5)`,
      }}
    >
      {/* Board frame top bar */}
      <div className="w-full flex items-center justify-between mb-2 px-2">
        <div className="flex gap-1">
          <div className="w-2 h-2 rounded-full bg-red-600 opacity-70" />
          <div className="w-2 h-2 rounded-full bg-yellow-500 opacity-70" />
          <div className="w-2 h-2 rounded-full bg-green-500 opacity-70" />
        </div>
        <div className="text-xs text-gray-600 font-mono tracking-widest uppercase">
          FlipperBoards
        </div>
        <div className="w-2 h-2 rounded-full bg-blue-500 opacity-40 animate-pulse" />
      </div>

      {/* Tile grid */}
      <div className="flex flex-col" style={{ gap: '3px' }}>
        {normalizedMatrix.map((row, r) => (
          <div key={r} className="flex" style={{ gap: '2px' }}>
            {row.map((code, c) => (
              <FlapTile
                key={`${r}-${c}`}
                code={code}
                tileColor={tileColor}
                tileBgColor={tileBgColor}
                size={tileSize}
                delay={staggerMap[r]?.[c] ?? 0}
                soundEnabled={soundEnabled}
              />
            ))}
          </div>
        ))}
      </div>

      {/* Board frame bottom bar */}
      <div className="w-full mt-2 flex items-center justify-center">
        <div className="h-px bg-gray-700 w-full opacity-50" />
      </div>
    </div>
  )
}
