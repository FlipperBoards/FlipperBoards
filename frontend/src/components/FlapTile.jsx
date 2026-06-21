import React, { useState, useEffect, useRef } from 'react'
import { CHARS, COLOR_HEX, isColorCode, codeToChar } from '../utils/charmap'
import { playFlipSound } from '../utils/audio'

// Number of intermediate frames when animating between characters
const FLIP_STEPS = 3
const STEP_DELAY_MS = 60

function getIntermediateChars(fromCode, toCode) {
  const total = CHARS.length
  // For text-to-text transitions, skip color tile codes so they don't flash mid-animation
  const skipColors = !isColorCode(fromCode) && !isColorCode(toCode)
  const steps = []
  let idx = fromCode
  let count = 0
  while (idx !== toCode && count < total) {
    idx = (idx + 1) % total
    if (idx !== toCode && !(skipColors && isColorCode(idx))) {
      steps.push(idx)
    }
    count++
  }
  const stride = Math.max(1, Math.floor(steps.length / FLIP_STEPS))
  const sampled = []
  for (let i = 0; i < steps.length; i += stride) {
    sampled.push(steps[i])
    if (sampled.length >= FLIP_STEPS) break
  }
  return sampled
}

export default function FlapTile({
  code = 0,
  tileColor = '#ffffff',
  tileBgColor = '#2a2a2a',
  size = 'md',
  tileWidth = null,     // explicit px — overrides size preset
  tileHeight = null,    // explicit px — overrides size preset
  tileFill = false,     // when true: fills CSS grid cell (100% × 100%)
  gridFontSize = null,  // CSS font-size string for fill mode, e.g. 'min(calc(...))'
  delay = 0,
  soundEnabled = true,
  extraShadow = undefined,
}) {
  const [displayCode, setDisplayCode] = useState(code)
  const [isFlipping, setIsFlipping] = useState(false)
  const [foldChar, setFoldChar] = useState(codeToChar(code))
  const [riseChar, setRiseChar] = useState(codeToChar(code))
  const prevCodeRef = useRef(code)
  const animTimers = useRef([])

  const sizeMap = {
    xs: { w: 20,  h: 28,  fs: 13 },
    sm: { w: 28,  h: 36,  fs: 17 },
    md: { w: 40,  h: 56,  fs: 24 },
    lg: { w: 56,  h: 80,  fs: 33 },
    xl: { w: 80,  h: 112, fs: 47 },
  }
  const preset = sizeMap[size] || sizeMap.md
  const w  = tileWidth  ?? preset.w
  const h  = tileHeight ?? preset.h
  const fs = tileWidth  ? Math.max(9, Math.floor(Math.min(w, h) * 0.52)) : preset.fs

  useEffect(() => {
    if (code === prevCodeRef.current) return
    const fromCode = prevCodeRef.current
    prevCodeRef.current = code

    animTimers.current.forEach(clearTimeout)
    animTimers.current = []

    const intermediates = getIntermediateChars(fromCode, code)
    const sequence = [...intermediates, code]

    // Apply stagger delay before starting animation
    const staggerTimer = setTimeout(() => {
      sequence.forEach((stepCode, i) => {
        const t = setTimeout(() => {
          setFoldChar(codeToChar(stepCode))
          setRiseChar(codeToChar(stepCode))
          setIsFlipping(true)
          if (soundEnabled && i === 0) playFlipSound()
          const t2 = setTimeout(() => {
            setDisplayCode(stepCode)
            setIsFlipping(stepCode !== code)
          }, STEP_DELAY_MS)
          animTimers.current.push(t2)
        }, i * (STEP_DELAY_MS + 10))
        animTimers.current.push(t)
      })
    }, delay)
    animTimers.current.push(staggerTimer)

    return () => {
      animTimers.current.forEach(clearTimeout)
    }
  }, [code, delay, soundEnabled])

  const isColor = isColorCode(displayCode)
  const targetIsColor = isColorCode(code)
  const char = codeToChar(displayCode)
  const targetChar = codeToChar(code)

  const fontStyle = {
    fontFamily: '"Bebas Neue", "Share Tech Mono", monospace',
    letterSpacing: '0.04em',
  }

  const tileStyle = tileFill
    ? { width: '100%', height: '100%', boxShadow: extraShadow }
    : { width: w, height: h, boxShadow: extraShadow }
  const textStyle = { fontSize: tileFill ? (gridFontSize || '16px') : fs, lineHeight: 1 }

  if (isColor || targetIsColor) {
    const hex = COLOR_HEX[isColor ? displayCode : code] || '#f1faee'
    return (
      <div className="flap-tile rounded-sm" style={{ ...tileStyle, background: hex }} />
    )
  }

  return (
    <div className="flap-tile select-none" style={tileStyle}>
      {/* Top half — shows top of current char */}
      <div className="flap-top" style={{ height: '50%', background: tileBgColor, color: tileColor, ...fontStyle }}>
        <span style={{ ...textStyle, transform: 'translateY(50%)' }}>{char}</span>
      </div>

      {/* Bottom half — shows bottom of current char */}
      <div className="flap-bottom" style={{ height: '50%', background: tileBgColor, color: tileColor, ...fontStyle }}>
        <span style={{ ...textStyle, transform: 'translateY(-50%)' }}>{char}</span>
      </div>

      {/* Fold-down animation — top half folding away */}
      {isFlipping && (
        <div key={`fold-${foldChar}-${Date.now()}`} className="flap-fold animate"
          style={{ background: tileBgColor, color: tileColor, ...fontStyle }}>
          <span style={{ ...textStyle, transform: 'translateY(50%)' }}>{foldChar}</span>
        </div>
      )}

      {/* Rise animation — bottom half of next char appearing */}
      {isFlipping && (
        <div key={`rise-${riseChar}-${Date.now()}`} className="flap-rise animate"
          style={{ background: tileBgColor, color: tileColor, ...fontStyle }}>
          <span style={{ ...textStyle, transform: 'translateY(-50%)' }}>{riseChar}</span>
        </div>
      )}
    </div>
  )
}
