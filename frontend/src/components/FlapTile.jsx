import React, { useState, useEffect, useRef } from 'react'
import { CHARS, COLOR_HEX, isColorCode, codeToChar } from '../utils/charmap'
import { playFlipSound } from '../utils/audio'

// Show every intermediate character for short jumps; sample longer ones to this cap.
const MAX_INTERMEDIATE = 10

function getIntermediateChars(fromCode, toCode) {
  const total = CHARS.length
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
  if (steps.length <= MAX_INTERMEDIATE) return steps
  // Long jump: sample evenly so we still show visible progression
  const stride = Math.ceil(steps.length / MAX_INTERMEDIATE)
  const sampled = []
  for (let i = 0; i < steps.length; i += stride) {
    sampled.push(steps[i])
    if (sampled.length >= MAX_INTERMEDIATE) break
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
  flipDuration = 120,   // ms per step (fold + rise each use this duration)
  extraShadow = undefined,
}) {
  const [displayCode, setDisplayCode] = useState(code)
  const [isFlipping, setIsFlipping] = useState(false)
  const [foldChar, setFoldChar] = useState(codeToChar(code))
  const [riseChar, setRiseChar] = useState(codeToChar(code))
  const prevCodeRef = useRef(code)
  const animTimers = useRef([])
  const delayRef = useRef(delay)
  const soundEnabledRef = useRef(soundEnabled)
  const flipDurationRef = useRef(flipDuration)
  delayRef.current = delay
  soundEnabledRef.current = soundEnabled
  flipDurationRef.current = flipDuration

  const sizeMap = {
    xs: { w: 20,  h: 28,  fs: 25 },
    sm: { w: 28,  h: 36,  fs: 32 },
    md: { w: 40,  h: 56,  fs: 50 },
    lg: { w: 56,  h: 80,  fs: 71 },
    xl: { w: 80,  h: 112, fs: 100 },
  }
  const preset = sizeMap[size] || sizeMap.md
  const w  = tileWidth  ?? preset.w
  const h  = tileHeight ?? preset.h
  const fs = tileWidth  ? Math.max(9, Math.floor(Math.min(w, h) * 0.9)) : preset.fs

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
        const stepMs = flipDurationRef.current
        const t = setTimeout(() => {
          setFoldChar(codeToChar(stepCode))
          setRiseChar(codeToChar(stepCode))
          setIsFlipping(true)
          if (soundEnabledRef.current && i === 0) playFlipSound()
          const t2 = setTimeout(() => {
            setDisplayCode(stepCode)
            setIsFlipping(stepCode !== code)
          }, stepMs)
          animTimers.current.push(t2)
        }, i * (stepMs + 10))
        animTimers.current.push(t)
      })
    }, delayRef.current)
    animTimers.current.push(staggerTimer)

    return () => {
      animTimers.current.forEach(clearTimeout)
    }
  }, [code])

  const isColor = isColorCode(displayCode)
  const targetIsColor = isColorCode(code)
  const char = codeToChar(displayCode)
  const targetChar = codeToChar(code)

  const fontStyle = {
    fontFamily: '"Bebas Neue", "Share Tech Mono", monospace',
    letterSpacing: '0.04em',
  }

  const flipDur = `${flipDuration}ms`
  const tileStyle = tileFill
    ? { width: '100%', height: '100%', boxShadow: extraShadow, '--flip-dur': flipDur }
    : { width: w, height: h, boxShadow: extraShadow, '--flip-dur': flipDur }
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
