import React, { useState, useEffect, useRef } from 'react'
import { CHARS, COLOR_HEX, isColorCode, codeToChar } from '../utils/charmap'
import { playFlipSound } from '../utils/audio'

// Number of intermediate frames when animating between characters
const FLIP_STEPS = 3
const STEP_DELAY_MS = 60

function getIntermediateChars(fromCode, toCode) {
  const total = CHARS.length
  const steps = []
  let idx = fromCode
  let count = 0
  while (idx !== toCode && count < total) {
    idx = (idx + 1) % total
    if (idx !== toCode) steps.push(idx)
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
  delay = 0,        // stagger delay in ms
  soundEnabled = true,
}) {
  const [displayCode, setDisplayCode] = useState(code)
  const [isFlipping, setIsFlipping] = useState(false)
  const [foldChar, setFoldChar] = useState(codeToChar(code))
  const [riseChar, setRiseChar] = useState(codeToChar(code))
  const prevCodeRef = useRef(code)
  const animTimers = useRef([])

  const sizeMap = {
    xs: { tile: 'w-5 h-7', text: 'text-[10px]', gap: '1px' },
    sm: { tile: 'w-7 h-9', text: 'text-xs', gap: '1px' },
    md: { tile: 'w-10 h-14', text: 'text-base', gap: '2px' },
    lg: { tile: 'w-14 h-20', text: 'text-xl', gap: '2px' },
    xl: { tile: 'w-20 h-28', text: 'text-3xl', gap: '3px' },
  }
  const sz = sizeMap[size] || sizeMap.md

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
    fontFamily: '"Share Tech Mono", "Courier New", monospace',
    letterSpacing: '0.02em',
  }

  if (isColor || targetIsColor) {
    const hex = COLOR_HEX[isColor ? displayCode : code] || '#f1faee'
    return (
      <div
        className={`flap-tile ${sz.tile} rounded-sm`}
        style={{ background: hex, margin: sz.gap }}
      />
    )
  }

  return (
    <div
      className={`flap-tile ${sz.tile} select-none`}
      style={{ margin: sz.gap }}
    >
      {/* Top half — shows top of current char */}
      <div
        className="flap-top"
        style={{
          height: '50%',
          background: tileBgColor,
          color: tileColor,
          ...fontStyle,
        }}
      >
        <span className={sz.text} style={{ lineHeight: 1, transform: 'translateY(50%)' }}>
          {char}
        </span>
      </div>

      {/* Bottom half — shows bottom of current char */}
      <div
        className="flap-bottom"
        style={{
          height: '50%',
          background: tileBgColor,
          color: tileColor,
          ...fontStyle,
        }}
      >
        <span className={sz.text} style={{ lineHeight: 1, transform: 'translateY(-50%)' }}>
          {char}
        </span>
      </div>

      {/* Fold-down animation — top half folding away */}
      {isFlipping && (
        <div
          key={`fold-${foldChar}-${Date.now()}`}
          className="flap-fold animate"
          style={{
            background: tileBgColor,
            color: tileColor,
            ...fontStyle,
          }}
        >
          <span className={sz.text} style={{ lineHeight: 1, transform: 'translateY(50%)' }}>
            {foldChar}
          </span>
        </div>
      )}

      {/* Rise animation — bottom half of next char appearing */}
      {isFlipping && (
        <div
          key={`rise-${riseChar}-${Date.now()}`}
          className="flap-rise animate"
          style={{
            background: tileBgColor,
            color: tileColor,
            ...fontStyle,
          }}
        >
          <span className={sz.text} style={{ lineHeight: 1, transform: 'translateY(-50%)' }}>
            {riseChar}
          </span>
        </div>
      )}
    </div>
  )
}
