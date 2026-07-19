// Synthesized split-flap clack sound using Web Audio API — no audio files needed.
let _ctx = null
let _noiseBuffer = null

function getCtx() {
  if (!_ctx) {
    try {
      _ctx = new (window.AudioContext || window.webkitAudioContext)()
    } catch {
      return null
    }
  }
  // Resume if suspended (browser autoplay policy)
  if (_ctx.state === 'suspended') _ctx.resume()
  return _ctx
}

const DURATION = 0.025 // 25ms
const _volume = 0.15   // 0–1

// One shared noise buffer — allocating per clack costs real CPU on a Pi
function getNoiseBuffer(ctx) {
  if (!_noiseBuffer) {
    const bufLen = Math.floor(ctx.sampleRate * DURATION)
    _noiseBuffer = ctx.createBuffer(1, bufLen, ctx.sampleRate)
    const data = _noiseBuffer.getChannelData(0)
    for (let i = 0; i < bufLen; i++) {
      data[i] = Math.random() * 2 - 1
    }
  }
  return _noiseBuffer
}

function clack(gainLevel) {
  const ctx = getCtx()
  if (!ctx) return

  const now = ctx.currentTime
  const source = ctx.createBufferSource()
  source.buffer = getNoiseBuffer(ctx)

  // Bandpass filter — center around 3kHz for that click
  const bpf = ctx.createBiquadFilter()
  bpf.type = 'bandpass'
  bpf.frequency.value = 3000
  bpf.Q.value = 0.5

  // Sharp attack, fast decay envelope
  const gain = ctx.createGain()
  gain.gain.setValueAtTime(0, now)
  gain.gain.linearRampToValueAtTime(gainLevel, now + 0.002)
  gain.gain.exponentialRampToValueAtTime(0.0001, now + DURATION)

  source.connect(bpf)
  bpf.connect(gain)
  gain.connect(ctx.destination)
  source.start(now)
  source.stop(now + DURATION)
}

/**
 * Plays a short mechanical clack — a noise burst shaped like a real flap hitting.
 */
export function playFlipSound() {
  if (_volume === 0) return
  clack(_volume)
}

let _lastClackAt = 0

/**
 * Canvas-engine clatter: one clack per animation frame no matter how many
 * flaps landed, gain scaled by the count so a full-board cascade sounds
 * bigger than a single digit — without spawning 132 audio graphs.
 */
export function playFlipClack(count = 1) {
  if (_volume === 0 || count <= 0) return
  const t = performance.now()
  if (t - _lastClackAt < 25) return
  _lastClackAt = t
  clack(Math.min(0.5, _volume * Math.sqrt(count)))
}

/** Call once on first user interaction to unlock audio context */
export function unlockAudio() {
  getCtx()
}
