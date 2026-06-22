import React from 'react'

const SIZE_MAP = {
  xs: { w: 20,  h: 28  },
  sm: { w: 28,  h: 36  },
  md: { w: 40,  h: 56  },
  lg: { w: 56,  h: 80  },
  xl: { w: 80,  h: 112 },
}

/**
 * Renders one tile's portion of a photo using CSS background-position.
 * The image is scaled so it fills the entire rows×cols grid, and each
 * tile clips its own section — no JS image processing needed.
 */
export default function PhotoTile({
  imageUrl,
  row,
  col,
  rows,
  cols,
  size = 'md',
  tileWidth = null,
  tileHeight = null,
  tileFill = false,
  physicalMode = false,
}) {
  const preset = SIZE_MAP[size] || SIZE_MAP.md
  const sz = tileFill ? { w: '100%', h: '100%' } : { w: tileWidth ?? preset.w, h: tileHeight ?? preset.h }

  // % position: tile (col, row) → what % of the scaled image starts here
  const posX = cols > 1 ? (col / (cols - 1)) * 100 : 0
  const posY = rows > 1 ? (row / (rows - 1)) * 100 : 0

  const shadow = physicalMode
    ? 'inset 0 1px 2px rgba(0,0,0,0.5), inset 0 -1px 1px rgba(255,255,255,0.04)'
    : undefined

  return (
    <div
      style={{
        width: sz.w,
        height: sz.h,
        position: 'relative',
        borderRadius: 3,
        overflow: 'hidden',
        boxShadow: shadow,
      }}
    >
      {/* Image background — fills the entire grid, each tile clips its section */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: `url(${imageUrl})`,
          backgroundSize: `${cols * 100}% ${rows * 100}%`,
          backgroundPosition: `${posX}% ${posY}%`,
          backgroundRepeat: 'no-repeat',
        }}
      />
      {/* Split-flap center seam — keeps the physical board aesthetic */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: '50%',
          height: '1px',
          background: 'rgba(0,0,0,0.45)',
          zIndex: 1,
        }}
      />
    </div>
  )
}
