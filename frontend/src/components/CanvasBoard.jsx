import React, { useEffect, useRef } from 'react'
import { isColorCode } from '../utils/charmap'
import { nextRingCode, RING_SIZE } from '../utils/flipSequence'
import { buildAtlas, ensureFontLoaded, drawColorCard } from '../utils/flapAtlas'
import { playFlipClack } from '../utils/audio'

// Canvas split-flap renderer — one <canvas>, a sprite atlas, one rAF loop.
// Built for weak hardware (Raspberry Pi 3): no DOM/React work in the
// animation path, dirty-rect repaints, 1:1 sprite blits, and the loop stops
// completely when no tile is moving.

const RESERVED_CODE = 70

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

const easeIn = (t) => t * t             // gravity: the flap accelerates as it falls
const easeOut = (t) => 1 - (1 - t) * (1 - t)

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
  renderScale = 1,       // <1 renders at lower resolution, upscaled by CSS — Pi tuning knob
}) {
  const canvasRef = useRef(null)
  const tilesRef = useRef([])          // [{current, target, color, flapStart, jitter}]
  const layoutRef = useRef(null)       // {tileW, tileH, gap, padX, padY} device px
  const atlasRef = useRef(null)
  const rafRef = useRef(null)
  const photoRef = useRef({ url: null, img: null })
  const prevSweepRef = useRef(sweepNonce)

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

  // ── Drawing ────────────────────────────────────────────────────────────────

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
    const skip = !isColorCode(tile.target)
    const to = nextRingCode(from, skip)

    // Revealed top: incoming char. Static bottom: outgoing char (covered later).
    ctx.drawImage(src, to * tileW, 0, tileW, half, x, y, tileW, half)
    ctx.drawImage(src, from * tileW, half, tileW, half, x, y + half, tileW, half)

    if (p < 0.5) {
      // Top flap of the outgoing char folds down toward the hinge
      const q = easeIn(p * 2)
      const sy = Math.cos(q * Math.PI / 2)
      const fh = half * sy
      if (fh >= 1) {
        ctx.drawImage(src, from * tileW, 0, tileW, half, x, y + (half - fh), tileW, fh)
        // The card turns away from the light as it falls
        ctx.fillStyle = `rgba(0,0,0,${(q * 0.45).toFixed(3)})`
        ctx.fillRect(x, y + (half - fh), tileW, fh)
      }
      // Falling flap throws a soft shadow on the lower half
      ctx.fillStyle = `rgba(0,0,0,${(q * 0.28).toFixed(3)})`
      ctx.fillRect(x, y + half, tileW, half)
    } else {
      // Bottom flap of the incoming char swings down into place
      const q = easeOut((p - 0.5) * 2)
      const sy = Math.sin(q * Math.PI / 2)
      const fh = half * sy
      // Shadow fades as the flap seats
      ctx.fillStyle = `rgba(0,0,0,${((1 - q) * 0.28).toFixed(3)})`
      ctx.fillRect(x, y + half, tileW, half)
      if (fh >= 1) {
        ctx.drawImage(src, to * tileW, half, tileW, half, x, y + half, tileW, fh)
        // Catches light while still angled toward the viewer
        ctx.fillStyle = `rgba(255,255,255,${((1 - q) * 0.10).toFixed(3)})`
        ctx.fillRect(x, y + half, tileW, fh)
      }
    }
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
    const canvas = canvasRef.current
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

  // ── Animation loop ─────────────────────────────────────────────────────────

  // rAF fires into frameRef so a pending callback always runs the latest
  // render's closure — never stale rows/cols/theme after a prop change.
  const frameRef = useRef(null)

  const startLoop = () => {
    if (rafRef.current == null) {
      rafRef.current = requestAnimationFrame((t) => {
        rafRef.current = null
        frameRef.current?.(t)
      })
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
      return
    }
    const ctx = canvas.getContext('2d')
    let animating = 0
    let landed = 0

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const tile = tiles[r * cols + c]
        if (!tile.flapStart) continue
        const flapMs = flapMsRef.current * tile.jitter
        // Fast-forward missed flaps (heavy frames, tab was hidden…)
        let p = (now - tile.flapStart) / flapMs
        if (p > 20) {
          // Way behind — snap to target instead of a silly catch-up blur
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
    if (animating > 0) startLoop()
  }
  frameRef.current = frame

  // ── Retargeting ────────────────────────────────────────────────────────────

  const applyMatrix = (sweep) => {
    if (!layoutRef.current || !atlasRef.current) return
    const tiles = tilesRef.current
    if (tiles.length !== rows * cols) return
    const m = matrixRef.current
    const now = performance.now()
    let kicked = false
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const tile = tiles[r * cols + c]
        const code = m[r]?.[c] ?? 0
        tile.target = code
        if (isColorCode(code) || isColorCode(tile.current)) {
          // Color cards snap — cascading through the ring would flash
          // characters before the solid color appears
          tile.current = code
          tile.flapStart = 0
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
    if (overlayRef.current.mode === 'flap') {
      const ctx = canvasRef.current?.getContext('2d')
      if (ctx) drawBoard(ctx)   // repaint statics (theme/text-color changes, snaps)
      if (kicked) startLoop()
    }
  }

  // ── Layout / atlas lifecycle ───────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false

    const rebuild = async () => {
      const canvas = canvasRef.current
      if (!canvas) return
      const dpr = Math.min(window.devicePixelRatio || 1, 1) *
        Math.min(1, Math.max(0.3, renderScale))
      const cssW = window.innerWidth
      const cssH = window.innerHeight
      canvas.width = Math.max(1, Math.round(cssW * dpr))
      canvas.height = Math.max(1, Math.round(cssH * dpr))

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
      const ctx = canvas.getContext('2d')
      drawBoard(ctx)
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
  }, [rows, cols, tileColor, tileBgColor, dividerWidth, dividerColor, renderScale])

  // New content / sweep
  useEffect(() => {
    const sweep = sweepNonce !== prevSweepRef.current
    prevSweepRef.current = sweepNonce
    applyMatrix(sweep)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matrix, sweepNonce, textColors])

  // Photo / color overlays
  useEffect(() => {
    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx || !layoutRef.current) return
    if (photoUrl) {
      if (photoRef.current.url !== photoUrl) {
        const img = new Image()
        img.onload = () => {
          photoRef.current = { url: photoUrl, img }
          const c = canvasRef.current?.getContext('2d')
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
