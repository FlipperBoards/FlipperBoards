// Synthesized split-flap clack sound using Web Audio API — no audio files needed.
//
// Tuned for weak hardware: the attack/decay envelope is baked into a shared
// noise buffer and the bandpass filter is a single persistent node, so each
// clack creates exactly one throwaway node (the required one-shot
// BufferSource) plus a tiny gain.
let _ctx = null
let _clackBuffer = null
let _bpf = null

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

// Shared noise buffer with the clack envelope pre-shaped into the samples
function getClackBuffer(ctx) {
  if (!_clackBuffer) {
    const bufLen = Math.floor(ctx.sampleRate * DURATION)
    const attackLen = Math.floor(ctx.sampleRate * 0.002)
    _clackBuffer = ctx.createBuffer(1, bufLen, ctx.sampleRate)
    const data = _clackBuffer.getChannelData(0)
    for (let i = 0; i < bufLen; i++) {
      const attack = i < attackLen ? i / attackLen : 1
      const decay = Math.exp(-5 * (i / bufLen))
      data[i] = (Math.random() * 2 - 1) * attack * decay
    }
  }
  return _clackBuffer
}

// Persistent bandpass — center around 3kHz for that mechanical click
function getFilter(ctx) {
  if (!_bpf) {
    _bpf = ctx.createBiquadFilter()
    _bpf.type = 'bandpass'
    _bpf.frequency.value = 3000
    _bpf.Q.value = 0.5
    _bpf.connect(ctx.destination)
  }
  return _bpf
}

function clack(level) {
  const ctx = getCtx()
  if (!ctx) return
  const source = ctx.createBufferSource()
  source.buffer = getClackBuffer(ctx)
  // Slight pitch variety so a cascade sounds mechanical, not machine-gun
  source.playbackRate.value = 0.9 + Math.random() * 0.25
  const gain = ctx.createGain()
  gain.gain.value = level
  source.connect(gain)
  gain.connect(getFilter(ctx))
  source.start()
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
 * Canvas-engine clatter: rate-capped (~12/s) regardless of how many flaps
 * landed, gain scaled by the count so a full-board cascade sounds bigger
 * than a single digit — without spawning 132 audio graphs.
 */
export function playFlipClack(count = 1) {
  if (_volume === 0 || count <= 0) return
  const t = performance.now()
  if (t - _lastClackAt < 80) return
  _lastClackAt = t
  clack(Math.min(0.5, _volume * Math.sqrt(count)))
}

/** Call once on first user interaction to unlock audio context */
export function unlockAudio() {
  getCtx()
}
