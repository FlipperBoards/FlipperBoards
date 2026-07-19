import React, { useState, useEffect, useRef } from 'react'
import { COLOR_HEX, isColorCode, codeToChar } from '../utils/charmap'
import { nextRingCode, sampledRingPath } from '../utils/flipSequence'
import { playFlipSound } from '../utils/audio'

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
  sweepNonce = 0,       // increments to force a flip cycle even when code is unchanged
}) {
  const [displayCode, setDisplayCode] = useState(code)
  const [isFlipping, setIsFlipping] = useState(false)
  const [foldChar, setFoldChar] = useState(codeToChar(code))
  const [riseChar, setRiseChar] = useState(codeToChar(code))
  const [stepId, setStepId] = useState(0)  // keys the fold/rise divs per step
  const prevCodeRef = useRef(code)
  const prevSweepRef = useRef(sweepNonce)
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

  const runFlipSequence = (fromCode, toCode) => {
    animTimers.current.forEach(clearTimeout)
    animTimers.current = []

    // Cap so the full animation (stagger delay + steps) settles before the next 1s clock tick.
    // Allow 0 intermediates when budget is tight — still shows fold+rise for the final char.
    const stepMs = flipDurationRef.current
    const budget = 900 - delayRef.current
    const maxIntermediates = Math.max(0, Math.floor(budget / (stepMs + 10)) - 1)
    let intermediates
    if (fromCode === toCode) {
      // Sweep cycle: a few forward neighbors in the ring, ending back on the same char
      intermediates = []
      let idx = fromCode
      const want = Math.min(3, maxIntermediates)
      while (intermediates.length < want) {
        idx = nextRingCode(idx)
        if (idx === toCode) break
        intermediates.push(idx)
      }
    } else {
      intermediates = sampledRingPath(fromCode, toCode, maxIntermediates)
    }
    const sequence = [...intermediates, toCode]

    // Apply stagger delay before starting animation
    const staggerTimer = setTimeout(() => {
      sequence.forEach((stepCode, i) => {
        const t = setTimeout(() => {
          setFoldChar(codeToChar(stepCode))
          setRiseChar(codeToChar(stepCode))
          setStepId(s => s + 1)
          setIsFlipping(true)
          if (soundEnabledRef.current && i === 0) playFlipSound()
          const t2 = setTimeout(() => {
            setDisplayCode(stepCode)
            setIsFlipping(i < sequence.length - 1)
          }, stepMs)
          animTimers.current.push(t2)
        }, i * (stepMs + 10))
        animTimers.current.push(t)
      })
    }, delayRef.current)
    animTimers.current.push(staggerTimer)
  }

  useEffect(() => {
    if (code === prevCodeRef.current) return
    const fromCode = prevCodeRef.current
    prevCodeRef.current = code
    // Consume any sweep arriving in this same commit — the tile is already flipping
    prevSweepRef.current = sweepNonce
    // Color tiles snap: animating through the ring would flash characters
    // (or multi-char color names) before the solid color appears
    if (isColorCode(code) || isColorCode(fromCode)) {
      animTimers.current.forEach(clearTimeout)
      animTimers.current = []
      setDisplayCode(code)
      setIsFlipping(false)
      return
    }
    runFlipSequence(fromCode, code)

    return () => {
      animTimers.current.forEach(clearTimeout)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code])

  // Full-board sweep: flip even though the character didn't change.
  // Declared after the code effect so a same-commit code change wins (it
  // consumes the nonce above and this effect no-ops).
  useEffect(() => {
    if (sweepNonce === prevSweepRef.current) return
    prevSweepRef.current = sweepNonce
    if (isColorCode(code)) return
    runFlipSequence(code, code)

    return () => {
      animTimers.current.forEach(clearTimeout)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sweepNonce])

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

      {/* Fold-down animation — top half folding away.
          Keyed by step counter (not wall-clock) so unrelated re-renders
          don't remount mid-animation and stutter the flip. */}
      {isFlipping && (
        <div key={`fold-${stepId}`} className="flap-fold animate"
          style={{ background: tileBgColor, color: tileColor, ...fontStyle }}>
          <span style={{ ...textStyle, transform: 'translateY(50%)' }}>{foldChar}</span>
        </div>
      )}

      {/* Rise animation — bottom half of next char appearing */}
      {isFlipping && (
        <div key={`rise-${stepId}`} className="flap-rise animate"
          style={{ background: tileBgColor, color: tileColor, ...fontStyle }}>
          <span style={{ ...textStyle, transform: 'translateY(-50%)' }}>{riseChar}</span>
        </div>
      )}
    </div>
  )
}
