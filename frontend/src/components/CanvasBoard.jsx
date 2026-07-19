import React, { useEffect, useRef, useState } from 'react'
import { isColorCode } from '../utils/charmap'
import { nextRingCode, RING_SIZE } from '../utils/flipSequence'
import { buildAtlas, ensureFontLoaded, drawColorCard, ROW_FALL, ROW_RISE } from '../utils/flapAtlas'
import { playFlipClack } from '../utils/audio'

// Canvas split-flap renderer — one <canvas>, a sprite atlas, one rAF loop.
//
// Built for weak hardware (Raspberry Pi 3):
// - every draw is a same-size alpha blit of a pre-rendered sprite (mid-flip
//   poses included) — no runtime scaling, no fillRects, no allocation
// - the loop draws on a bounded TICK (30fps down to 15fps), independent of
//   flap speed; between ticks the rAF callback just re-schedules
// - an adaptive ladder degrades tick rate, then internal resolution, when
//   the device can't keep up — and remembers the settled rung
// - the loop stops completely when no tile is moving

const RESERVED_CODE = 70

// Degradation ladder: tick rate first (cheap, barely visible), then internal
// resolution (crispness trade). Never climbs back up mid-session.
const RUNGS = [
  { fps: 30, scale: 1 },
  { fps: 20, scale: 1 },
  { fps: 20, scale: 0.75 },
  { fps: 15, scale: 0.5 },
]
const RUNG_KEY = 'fb:renderRung'

function savedRung() {
  try {
    const r = parseInt(localStorage.getItem(RUNG_KEY), 10)
    return r >= 0 && r < RUNGS.length ? r : 0
  } catch { return 0 }
}

function ringBack(code, steps, skipColors = true) {
  let idx = code
  for (let s = 0; s < steps; s++) {
    for (let g = 0; g < RING_SIZE; g++) {
      idx = (idx - 1 + RING_SIZE) % RING_SIZE
      if (idx === RESERVED_CODE) continue
      if (skipColors && isColorCode(idx)) continue
      break
    }
  }
  return idx
}

export default function CanvasBoard({
  matrix = [],
  colorMatrix = null,
  photoUrl = null,
  rows = 6,
  cols = 22,
  tileColor = '#ffffff',
  tileBgColor = '#2a2a2a',
  dividerWidth = 4,
  dividerColor = '#111111',
  sweepNonce = 0,
  textColors = null,
  soundEnabled = true,
  flipDuration = 120,
  renderScale = null,    // explicit ?scale= override — disables the adaptive ladder
  tickFps = null,        // explicit ?fps= override — disables the adaptive ladder
}) {
  const canvasRef = useRef(null)
  const ctxRef = useRef(null)
  const tilesRef = useRef([])          // [{current, target, flapStart, jitter}]
  const layoutRef = useRef(null)       // {tileW, tileH, gap, padX, padY} device px
  const atlasRef = useRef(null)
  const rafRef = useRef(null)
  const photoRef = useRef({ url: null, img: null })
  const prevSweepRef = useRef(sweepNonce)

  const adaptive = renderScale == null && tickFps == null
  const [rung, setRung] = useState(() => (adaptive ? savedRung() : 0))
  const rungRef = useRef(rung)
  rungRef.current = rung
  const effectiveScale = renderScale ?? RUNGS[rung].scale
  const fpsRef = useRef(30)
  fpsRef.current = tickFps ?? RUNGS[rung].fps

  // Tick pacing + adaptation state — plain refs, no React in the hot path
  const paceRef = useRef({ lastTick: 0, prevAnimTick: 0, slowTicks: 0, lastDegrade: 0 })

  // Live prop mirrors so the rAF loop never closes over stale values
  const flapMsRef = useRef(flipDuration)
  const soundRef = useRef(soundEnabled)
  flapMsRef.current = Math.max(40, flipDuration)
  soundRef.current = soundEnabled

  const overlayMode = photoUrl ? 'photo' : colorMatrix ? 'color' : 'flap'
  const overlayRef = useRef({ mode: overlayMode, colorMatrix, photoUrl })
  overlayRef.current = { mode: overlayMode, colorMatrix, photoUrl }
  const colorsRef = useRef(textColors)
  colorsRef.current = textColors
  // The rebuild path is async (font load) — it must apply the matrix that is
  // current when it FINISHES, not the one captured when it started.
  const matrixRef = useRef(matrix)
  matrixRef.current = matrix

  const getCtx = () => {
    if (!ctxRef.current && canvasRef.current) {
      // Opaque + desynchronized: skips whole-layer alpha compositing and,
      // where supported, the compositor round-trip — both matter in
      // software rasterization
      ctxRef.current = canvasRef.current.getContext('2d', { alpha: false, desynchronized: true })
    }
    return ctxRef.current
  }

  // ── Drawing (all 1:1 blits) ────────────────────────────────────────────────

  const tileXY = (r, c) => {
    const { tileW, tileH, gap, padX, padY } = layoutRef.current
    return [padX + c * (tileW + gap), padY + r * (tileH + gap)]
  }

  const drawStaticTile = (ctx, r, c, code) => {
    const { tileW, tileH } = layoutRef.current
    const [x, y] = tileXY(r, c)
    const src = atlasRef.current.canvasFor(colorsRef.current?.[r]?.[c] || null)
    ctx.drawImage(src, code * tileW, 0, tileW, tileH, x, y, tileW, tileH)
  }

  const drawFlapFrame = (ctx, r, c, tile, p) => {
    const { tileW, tileH } = layoutRef.current
    const [x, y] = tileXY(r, c)
    const src = atlasRef.current.canvasFor(colorsRef.current?.[r]?.[c] || null)
    const half = tileH / 2
    const from = tile.current
    const to = nextRingCode(from, !isColorCode(tile.target))

    // Revealed top: incoming char. Static bottom: outgoing char.
    ctx.drawImage(src, to * tileW, 0, tileW, half, x, y, tileW, half)
    ctx.drawImage(src, from * tileW, half, tileW, half, x, y + half, tileW, half)
    // One pre-rendered pose overlay: outgoing top folding, or incoming
    // bottom rising — shadows and highlights are baked into the sprite
    const poseRow = p < 0.5 ? ROW_FALL : ROW_RISE
    const poseCode = p < 0.5 ? from : to
    ctx.drawImage(src, poseCode * tileW, poseRow * tileH, tileW, tileH, x, y, tileW, tileH)
  }

  const drawBoard = (ctx) => {
    const canvas = canvasRef.current
    if (!canvas || !layoutRef.current || tilesRef.current.length !== rows * cols) return
    ctx.fillStyle = dividerColor
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    const { mode, colorMatrix: cm, photoUrl: pu } = overlayRef.current
    if (mode === 'photo' && photoRef.current.img && photoRef.current.url === pu) {
      drawPhoto(ctx)
      return
    }
    const tiles = tilesRef.current
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (mode === 'color') {
          const { tileW, tileH } = layoutRef.current
          const [x, y] = tileXY(r, c)
          drawColorCard(ctx, x, y, tileW, tileH, cm?.[r]?.[c] || '#1a1a1a')
        } else {
          drawStaticTile(ctx, r, c, tiles[r * cols + c].current)
        }
      }
    }
  }

  const drawPhoto = (ctx) => {
    const { tileW, tileH, gap, padX, padY } = layoutRef.current
    const img = photoRef.current.img
    const boardW = cols * tileW + (cols - 1) * gap
    const boardH = rows * tileH + (rows - 1) * gap
    // Cover-fit the photo over the board area
    const scale = Math.max(boardW / img.width, boardH / img.height)
    const sw = boardW / scale
    const sh = boardH / scale
    ctx.drawImage(img, (img.width - sw) / 2, (img.height - sh) / 2, sw, sh,
      padX, padY, boardW, boardH)
    // Carve the tile grid back out: dividers + per-tile split lines
    ctx.fillStyle = dividerColor
    for (let c = 1; c < cols; c++) {
      ctx.fillRect(padX + c * (tileW + gap) - gap, padY, gap, boardH)
    }
    for (let r = 1; r < rows; r++) {
      ctx.fillRect(padX, padY + r * (tileH + gap) - gap, boardW, gap)
    }
    const lw = Math.max(1, tileH * 0.014)
    ctx.fillStyle = 'rgba(0,0,0,0.4)'
    for (let r = 0; r < rows; r++) {
      ctx.fillRect(padX, padY + r * (tileH + gap) + tileH / 2 - lw / 2, boardW, lw)
    }
  }

  // ── Animation loop: rAF paced down to a bounded tick rate ──────────────────

  // rAF fires into frameRef so a pending callback always runs the latest
  // render's closure — never stale rows/cols/theme after a prop change.
  const frameRef = useRef(null)

  const startLoop = () => {
    if (rafRef.current == null) {
      rafRef.current = requestAnimationFrame((t) => {
        rafRef.current = null
        const tickMs = 1000 / fpsRef.current
        if (t - paceRef.current.lastTick < tickMs - 1) {
          startLoop()   // between ticks: just keep the loop alive (near-free)
          return
        }
        frameRef.current?.(t)
      })
    }
  }

  const maybeDegrade = (now) => {
    // Called once per executed tick while animating. Consecutive ticks that
    // run well over target for ~1s ⇒ the device can't keep up ⇒ step down.
    const pace = paceRef.current
    const target = 1000 / fpsRef.current
    if (pace.prevAnimTick) {
      const interval = now - pace.prevAnimTick
      if (interval > target * 1.6) pace.slowTicks++
      else pace.slowTicks = Math.max(0, pace.slowTicks - 1)
    }
    pace.prevAnimTick = now
    if (adaptive && pace.slowTicks >= fpsRef.current &&
        now - pace.lastDegrade > 2000 && rungRef.current < RUNGS.length - 1) {
      pace.slowTicks = 0
      pace.lastDegrade = now
      const next = rungRef.current + 1
      try { localStorage.setItem(RUNG_KEY, String(next)) } catch { /* private mode */ }
      setRung(next)   // scale rungs rebuild the backing store + atlas
    }
  }

  const frame = (now) => {
    const canvas = canvasRef.current
    if (!canvas || !atlasRef.current) return
    const tiles = tilesRef.current
    if (tiles.length !== rows * cols) return
    if (overlayRef.current.mode !== 'flap') {
      // An overlay (photo/color mosaic) took the board mid-cascade — settle
      // the tiles silently so nothing draws over the overlay
      for (const tile of tiles) {
        tile.current = tile.target
        tile.flapStart = 0
      }
      paceRef.current.prevAnimTick = 0
      return
    }
    paceRef.current.lastTick = now
    const ctx = getCtx()
    let animating = 0
    let landed = 0

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const tile = tiles[r * cols + c]
        if (!tile.flapStart) continue
        const flapMs = flapMsRef.current * tile.jitter
        // Fast-forward flaps that elapsed since the last tick — sampled
        // intermediate characters are exactly how a real board blurs
        let p = (now - tile.flapStart) / flapMs
        if (p > 60) {
          // Way behind (tab was hidden) — snap instead of a silly catch-up
          tile.current = tile.target
          tile.flapStart = 0
          drawStaticTile(ctx, r, c, tile.current)
          continue
        }
        while (p >= 1) {
          tile.current = nextRingCode(tile.current, !isColorCode(tile.target))
          landed++
          if (tile.current === tile.target) {
            tile.flapStart = 0
            break
          }
          tile.flapStart += flapMs
          p = (now - tile.flapStart) / flapMs
        }
        if (!tile.flapStart) {
          drawStaticTile(ctx, r, c, tile.current)
          continue
        }
        drawFlapFrame(ctx, r, c, tile, p)
        animating++
      }
    }

    if (landed > 0 && soundRef.current) playFlipClack(landed)
    if (animating > 0) {
      maybeDegrade(now)
      startLoop()
    } else {
      paceRef.current.prevAnimTick = 0
    }
  }
  frameRef.current = frame

  // ── Retargeting ────────────────────────────────────────────────────────────

  const applyMatrix = (sweep) => {
    if (!layoutRef.current || !atlasRef.current) return
    const tiles = tilesRef.current
    if (tiles.length !== rows * cols) return
    const m = matrixRef.current
    const now = performance.now()
    const ctx = getCtx()
    let kicked = false
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const tile = tiles[r * cols + c]
        const code = m[r]?.[c] ?? 0
        // Unchanged AND settled-or-flying: nothing to do. (A stuck idle tile
        // with current ≠ target still falls through and gets re-kicked.)
        if (tile.target === code && !sweep && (tile.flapStart || tile.current === code)) continue
        tile.target = code
        if (isColorCode(code) || isColorCode(tile.current)) {
          // Color cards snap — cascading through the ring would flash
          // characters before the solid color appears
          tile.current = code
          tile.flapStart = 0
          if (ctx && overlayRef.current.mode === 'flap') drawStaticTile(ctx, r, c, code)
        } else if (sweep && tile.current === code) {
          // Full-board sweep: back the tile a few ring steps so it flips
          // through neighbors and lands on the same character
          tile.current = ringBack(code, 3 + ((r + c) % 3))
          tile.flapStart = now
          kicked = true
        } else if (tile.current !== code && !tile.flapStart) {
          tile.flapStart = now
          kicked = true
        }
        // Mid-flight tiles just keep cascading toward the new target
      }
    }
    // Only tiles that changed are repainted (by the loop, or the snap above) —
    // the clock broadcasts every second and a full-board repaint each time
    // is wasted work on weak devices
    if (kicked && overlayRef.current.mode === 'flap') startLoop()
  }

  // ── Layout / atlas lifecycle ───────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false

    const rebuild = async () => {
      const canvas = canvasRef.current
      if (!canvas) return
      const dpr = Math.min(window.devicePixelRatio || 1, 1) *
        Math.min(1, Math.max(0.3, effectiveScale))
      const cssW = window.innerWidth
      const cssH = window.innerHeight
      canvas.width = Math.max(1, Math.round(cssW * dpr))
      canvas.height = Math.max(1, Math.round(cssH * dpr))
      const ctx = getCtx()
      if (ctx) ctx.imageSmoothingEnabled = false  // reset by resize; all blits are 1:1

      const gap = Math.round(dividerWidth * dpr)
      const tileW = Math.max(2, Math.floor((canvas.width - (cols - 1) * gap) / cols))
      const tileH = Math.max(2, Math.floor((canvas.height - (rows - 1) * gap) / rows))
      const padX = Math.floor((canvas.width - cols * tileW - (cols - 1) * gap) / 2)
      const padY = Math.floor((canvas.height - rows * tileH - (rows - 1) * gap) / 2)
      layoutRef.current = { tileW, tileH, gap, padX, padY }

      await ensureFontLoaded(Math.min(tileW * 1.7, tileH * 0.9))
      if (cancelled) return
      atlasRef.current = buildAtlas({ tileW, tileH, bgColor: tileBgColor, textColor: tileColor })

      if (tilesRef.current.length !== rows * cols) {
        tilesRef.current = Array.from({ length: rows * cols }, () => ({
          current: 0, target: 0, flapStart: 0,
          jitter: 0.92 + Math.random() * 0.16,
        }))
      }
      applyMatrix(false)
      if (ctx) drawBoard(ctx)
      startLoop()
    }

    rebuild()
    const onResize = () => rebuild()
    window.addEventListener('resize', onResize)
    return () => {
      cancelled = true
      window.removeEventListener('resize', onResize)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, cols, tileColor, tileBgColor, dividerWidth, dividerColor, effectiveScale])

  // New content / sweep
  useEffect(() => {
    const sweep = sweepNonce !== prevSweepRef.current
    prevSweepRef.current = sweepNonce
    applyMatrix(sweep)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matrix, sweepNonce])

  // Markup color changes recolor static glyphs — full repaint (rare)
  useEffect(() => {
    const ctx = getCtx()
    if (ctx && overlayRef.current.mode === 'flap') drawBoard(ctx)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textColors])

  // Photo / color overlays
  useEffect(() => {
    const ctx = getCtx()
    if (!ctx || !layoutRef.current) return
    if (photoUrl) {
      if (photoRef.current.url !== photoUrl) {
        const img = new Image()
        img.onload = () => {
          photoRef.current = { url: photoUrl, img }
          const c = getCtx()
          if (c && overlayRef.current.photoUrl === photoUrl) drawBoard(c)
        }
        img.src = photoUrl
      } else {
        drawBoard(ctx)
      }
    } else {
      drawBoard(ctx)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photoUrl, colorMatrix])

  useEffect(() => () => {
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
  }, [])

  // Debug hook for kiosk troubleshooting (chrome devtools / remote debugging):
  // window.__fbBoard() → per-tile engine state summary
  useEffect(() => {
    window.__fbBoard = () => ({
      layout: layoutRef.current,
      looping: rafRef.current != null,
      mode: overlayRef.current.mode,
      rung: rungRef.current,
      fps: fpsRef.current,
      animating: tilesRef.current.filter(t => t.flapStart).length,
      tiles: tilesRef.current.map(t => `${t.current}>${t.target}${t.flapStart ? '*' : ''}`),
    })
    return () => { delete window.__fbBoard }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        inset: 0,
        width: '100vw',
        height: '100vh',
        background: dividerColor,
      }}
    />
  )
}
