import React, { useRef, useEffect } from 'react'

const SIZE_MAP = {
  xs: { w: 20,  h: 28  },
  sm: { w: 28,  h: 36  },
  md: { w: 40,  h: 56  },
  lg: { w: 56,  h: 80  },
  xl: { w: 80,  h: 112 },
}

// Lerp between two hex colors over `duration` ms using requestAnimationFrame.
// Gives a smooth physical-feeling "color reveal" rather than an instant swap.
function hexToRgb(hex) {
  const n = parseInt(hex.replace('#', ''), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

function rgbToHex(r, g, b) {
  return `#${Math.round(r).toString(16).padStart(2, '0')}${Math.round(g).toString(16).padStart(2, '0')}${Math.round(b).toString(16).padStart(2, '0')}`
}

export default function ColorTile({ color = '#1a1a1a', size = 'md', tileWidth = null, tileHeight = null, delay = 0, physicalMode = false }) {
  const preset = SIZE_MAP[size] || SIZE_MAP.md
  const sz = { w: tileWidth ?? preset.w, h: tileHeight ?? preset.h }
  const topRef = useRef(null)
  const botRef = useRef(null)
  const prevColorRef = useRef(color)
  const animRef = useRef(null)

  useEffect(() => {
    const from = prevColorRef.current
    const to = color
    if (from === to) return
    prevColorRef.current = to

    const delayTimer = setTimeout(() => {
      const fromRgb = hexToRgb(from)
      const toRgb = hexToRgb(to)
      const duration = 200
      const start = performance.now()

      function tick(now) {
        const t = Math.min((now - start) / duration, 1)
        // ease-out quad
        const ease = 1 - (1 - t) * (1 - t)
        const cur = rgbToHex(
          fromRgb[0] + (toRgb[0] - fromRgb[0]) * ease,
          fromRgb[1] + (toRgb[1] - fromRgb[1]) * ease,
          fromRgb[2] + (toRgb[2] - fromRgb[2]) * ease,
        )
        if (topRef.current) topRef.current.style.background = cur
        if (botRef.current) botRef.current.style.background = cur
        if (t < 1) animRef.current = requestAnimationFrame(tick)
      }

      animRef.current = requestAnimationFrame(tick)
    }, delay)

    return () => {
      clearTimeout(delayTimer)
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [color, delay])

  const shadow = physicalMode
    ? 'inset 0 1px 2px rgba(0,0,0,0.6), inset 0 -1px 1px rgba(255,255,255,0.05)'
    : undefined

  return (
    <div
      style={{ width: sz.w, height: sz.h, display: 'flex', flexDirection: 'column', borderRadius: 3, overflow: 'hidden' }}
    >
      {/* Top half */}
      <div
        ref={topRef}
        style={{
          height: '50%',
          background: color,
          borderBottom: '1px solid rgba(0,0,0,0.35)',
          boxShadow: shadow,
        }}
      />
      {/* Bottom half */}
      <div
        ref={botRef}
        style={{
          height: '50%',
          background: color,
          boxShadow: shadow,
        }}
      />
    </div>
  )
}
