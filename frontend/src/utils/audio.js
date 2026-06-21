// Synthesized split-flap clack sound using Web Audio API — no audio files needed.
let _ctx = null

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

let _muted = false
let _volume = 0.15  // 0–1

export function setAudioMuted(muted) { _muted = muted }
export function setAudioVolume(vol) { _volume = Math.max(0, Math.min(1, vol)) }

/**
 * Plays a short mechanical clack — a noise burst shaped like a real flap hitting.
 * Takes ~3ms of CPU, plays for ~30ms.
 */
export function playFlipSound() {
  if (_muted || _volume === 0) return
  const ctx = getCtx()
  if (!ctx) return

  const now = ctx.currentTime
  const duration = 0.025  // 25ms

  // White noise buffer (small)
  const bufLen = Math.floor(ctx.sampleRate * duration)
  const buffer = ctx.createBuffer(1, bufLen, ctx.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < bufLen; i++) {
    data[i] = Math.random() * 2 - 1
  }

  const source = ctx.createBufferSource()
  source.buffer = buffer

  // Bandpass filter — center around 3kHz for that click
  const bpf = ctx.createBiquadFilter()
  bpf.type = 'bandpass'
  bpf.frequency.value = 3000
  bpf.Q.value = 0.5

  // Sharp attack, fast decay envelope
  const gain = ctx.createGain()
  gain.gain.setValueAtTime(0, now)
  gain.gain.linearRampToValueAtTime(_volume, now + 0.002)
  gain.gain.exponentialRampToValueAtTime(0.0001, now + duration)

  source.connect(bpf)
  bpf.connect(gain)
  gain.connect(ctx.destination)
  source.start(now)
  source.stop(now + duration)
}

/** Call once on first user interaction to unlock audio context */
export function unlockAudio() {
  getCtx()
}
