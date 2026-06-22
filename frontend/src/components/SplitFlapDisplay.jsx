import React, { useMemo, useRef } from 'react'
import FlapTile from './FlapTile'
import ColorTile from './ColorTile'
import PhotoTile from './PhotoTile'

const STAGGER_MS_PER_COL = 30

export default function SplitFlapDisplay({
  matrix = [],
  colorMatrix = null,   // string[][] — averaged color per tile
  photoUrl = null,      // string — image URL; each tile shows its section of the photo
  rows = 6,
  cols = 22,
  tileColor = '#ffffff',
  tileBgColor = '#2a2a2a',
  bgColor = '#1a1a1a',
  tileSize = 'md',
  tilePixelWidth = null,   // explicit px — enables fill mode when set
  tilePixelHeight = null,  // explicit px — enables fill mode when set
  soundEnabled = true,
  dividerWidth = 4,
  dividerColor = '#111111',
  physicalMode = false,
  fillViewport = false,    // when true: no padding/shadow/header, flush fill
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

  if (fillViewport) {
    // Compute explicit tile sizes so grid tracks are always equal — never 1fr.
    // All reference implementations (flipoff, jatovarv, flappyboards, flapstr, …)
    // use fixed computed sizes, never fractional units, for this exact reason.
    const colGaps = (cols - 1) * dividerWidth
    const rowGaps = (rows - 1) * dividerWidth
    const tileCSSW = `calc((100vw - ${colGaps}px) / ${cols})`
    const tileCSSH = `calc((100vh - ${rowGaps}px) / ${rows})`
    // Bebas Neue: cap-height ≈ 0.85em, very condensed (W ≈ 0.55em wide).
    // Height factor 0.9 → ~76% visual fill. Width factor 1.7 keeps wide chars in bounds.
    const gridFontSize = `min(calc((100vw - ${colGaps}px) / ${cols} * 1.7), calc((100vh - ${rowGaps}px) / ${rows} * 0.9))`

    return (
      <div
        style={{
          position: 'fixed',
          inset: 0,
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, ${tileCSSW})`,
          gridTemplateRows: `repeat(${rows}, ${tileCSSH})`,
          gap: `${dividerWidth}px`,
          background: dividerColor,
        }}
      >
        {normalizedMatrix.flatMap((row, r) =>
          row.map((code, c) =>
            photoUrl
              ? <PhotoTile key={`${r}-${c}`} imageUrl={photoUrl} row={r} col={c} rows={rows} cols={cols}
                  tileFill physicalMode={physicalMode} />
              : colorMatrix
                ? <ColorTile key={`${r}-${c}`} color={colorMatrix[r]?.[c] ?? '#1a1a1a'}
                    tileFill delay={staggerMap[r]?.[c] ?? 0} physicalMode={physicalMode} />
                : <FlapTile key={`${r}-${c}`} code={code} tileColor={tileColor} tileBgColor={tileBgColor}
                    tileFill gridFontSize={gridFontSize}
                    delay={staggerMap[r]?.[c] ?? 0} soundEnabled={soundEnabled} extraShadow={tileShadow} />
          )
        )}
      </div>
    )
  }

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
              photoUrl
                ? <PhotoTile key={`${r}-${c}`} imageUrl={photoUrl} row={r} col={c} rows={rows} cols={cols}
                    size={tileSize} physicalMode={physicalMode} />
                : colorMatrix
                  ? <ColorTile key={`${r}-${c}`} color={colorMatrix[r]?.[c] ?? '#1a1a1a'}
                      size={tileSize} delay={staggerMap[r]?.[c] ?? 0} physicalMode={physicalMode} />
                  : <FlapTile key={`${r}-${c}`} code={code} tileColor={tileColor} tileBgColor={tileBgColor}
                      size={tileSize} delay={staggerMap[r]?.[c] ?? 0} soundEnabled={soundEnabled} extraShadow={tileShadow} />
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
