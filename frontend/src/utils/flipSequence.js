// Character-ring stepping shared by the canvas engine and the DOM FlapTile.
// A real split-flap can only advance forward through its character ring, so
// every transition flips through the intermediate characters in ring order.
import { CHARS, isColorCode } from './charmap'

export const RING_SIZE = CHARS.length
const RESERVED_CODE = 70 // duplicate blank — never shown mid-flip

/** One forward step around the ring, skipping the reserved code and — unless
 * the transition involves color cards — the solid color codes. */
export function nextRingCode(code, skipColors = true) {
  let idx = code
  for (let guard = 0; guard < RING_SIZE; guard++) {
    idx = (idx + 1) % RING_SIZE
    if (idx === RESERVED_CODE) continue
    if (skipColors && isColorCode(idx)) continue
    return idx
  }
  return code
}

/** Every intermediate code between from and to in ring order (exclusive of
 * both ends) — the authentic full cascade. */
export function ringPath(fromCode, toCode) {
  const skipColors = !isColorCode(fromCode) && !isColorCode(toCode)
  const steps = []
  let idx = fromCode
  let guard = 0
  while (idx !== toCode && guard < RING_SIZE) {
    idx = nextRingCode(idx, skipColors)
    if (idx !== toCode) steps.push(idx)
    guard++
  }
  return steps
}

/** ringPath sampled down to maxCount evenly-spaced steps — used by the DOM
 * fallback renderer, which can't afford the full cascade. */
export function sampledRingPath(fromCode, toCode, maxCount) {
  const steps = ringPath(fromCode, toCode)
  if (steps.length <= maxCount) return steps
  const stride = Math.ceil(steps.length / maxCount)
  const sampled = []
  for (let i = 0; i < steps.length; i += stride) {
    sampled.push(steps[i])
    if (sampled.length >= maxCount) break
  }
  return sampled
}
