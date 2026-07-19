// Pre-rendered split-flap character sprites for the canvas renderer.
//
// Every character card is drawn ONCE per (size, theme, text-color) into an
// offscreen atlas — the animation loop then just blits halves of these
// sprites, so the per-frame cost is a handful of drawImage calls no matter
// how weak the GPU is (Raspberry Pi 3 target).
//
// The Vestaboard look is baked into the sprite itself: matte card face with
// rounded corners, a vertical sheen that suggests the curved flap, and the
// horizontal split line through the middle where the two flaps meet.
import { CHARS, COLOR_HEX, isColorCode, codeToChar } from './charmap'

const FONT_FAMILY = '"Bebas Neue", "Share Tech Mono", monospace'

function roundedRectPath(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function drawCard(ctx, x, y, w, h, faceColor) {
  const r = Math.max(1.5, Math.min(w, h) * 0.07)
  roundedRectPath(ctx, x + 0.5, y + 0.5, w - 1, h - 1, r)
  ctx.fillStyle = faceColor
  ctx.fill()

  // Curved-flap sheen: each half is lighter toward the split hinge and
  // darker toward the outer edge — reads as two slightly bowed cards.
  ctx.save()
  ctx.clip()
  const top = ctx.createLinearGradient(0, y, 0, y + h / 2)
  top.addColorStop(0, 'rgba(255,255,255,0.10)')
  top.addColorStop(0.6, 'rgba(255,255,255,0.02)')
  top.addColorStop(1, 'rgba(0,0,0,0.05)')
  ctx.fillStyle = top
  ctx.fillRect(x, y, w, h / 2)

  const bottom = ctx.createLinearGradient(0, y + h / 2, 0, y + h)
  bottom.addColorStop(0, 'rgba(255,255,255,0.04)')
  bottom.addColorStop(0.5, 'rgba(0,0,0,0.08)')
  bottom.addColorStop(1, 'rgba(0,0,0,0.22)')
  ctx.fillStyle = bottom
  ctx.fillRect(x, y + h / 2, w, h / 2)
  ctx.restore()
}

function drawSplitLine(ctx, x, y, w, h) {
  // The gap where the two flaps meet — dark slot with a faint highlight
  // on the lower lip. Drawn last so it cuts through the glyph.
  const lw = Math.max(1, h * 0.018)
  ctx.fillStyle = 'rgba(0,0,0,0.65)'
  ctx.fillRect(x, y + h / 2 - lw / 2, w, lw)
  ctx.fillStyle = 'rgba(255,255,255,0.05)'
  ctx.fillRect(x, y + h / 2 + lw / 2, w, Math.max(1, lw * 0.6))
}

/** A solid color card with the same face treatment as the atlas sprites —
 * used by the canvas renderer's color-matrix (image mosaic) mode where the
 * per-tile colors are arbitrary and can't be pre-rendered. */
export function drawColorCard(ctx, x, y, w, h, color) {
  drawCard(ctx, x, y, w, h, color)
  drawSplitLine(ctx, x, y, w, h)
}

function drawVariant(canvas, tileW, tileH, bgColor, textColor) {
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  const fs = Math.min(tileW * 1.7, tileH * 0.9)
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.font = `${fs}px ${FONT_FAMILY}`

  for (let code = 0; code < CHARS.length; code++) {
    const x = code * tileW
    if (isColorCode(code)) {
      drawCard(ctx, x, 0, tileW, tileH, COLOR_HEX[code])
      drawSplitLine(ctx, x, 0, tileW, tileH)
      continue
    }
    drawCard(ctx, x, 0, tileW, tileH, bgColor)
    const ch = codeToChar(code)
    if (ch !== ' ') {
      ctx.fillStyle = textColor
      // Bebas Neue's middle baseline sits high — nudge down for optical center
      ctx.font = `${fs}px ${FONT_FAMILY}`
      ctx.fillText(ch, x + tileW / 2, tileH / 2 + fs * 0.045, tileW * 0.94)
    }
    drawSplitLine(ctx, x, 0, tileW, tileH)
  }
}

/**
 * Build a sprite atlas for a given tile size + theme. Variants for markup
 * text colors are rendered lazily — the palette is bounded (default + 7).
 *
 * `canvasFor(color)` returns the atlas canvas whose glyphs use that text
 * color; source rect for a code is (code * tileW, 0, tileW, tileH), halves
 * are the top/bottom tileH/2 of that rect.
 */
export function buildAtlas({ tileW, tileH, bgColor, textColor }) {
  tileW = Math.max(2, Math.round(tileW))
  tileH = Math.max(2, Math.round(tileH))
  const variants = new Map()

  function canvasFor(color) {
    const key = color || textColor
    let canvas = variants.get(key)
    if (!canvas) {
      canvas = document.createElement('canvas')
      canvas.width = tileW * CHARS.length
      canvas.height = tileH
      drawVariant(canvas, tileW, tileH, bgColor, key)
      variants.set(key, canvas)
    }
    return canvas
  }

  canvasFor(textColor)
  return { tileW, tileH, canvasFor }
}

/** Resolve the board font at the size the atlas will draw it, so sprites
 * never bake the fallback font. Resolves quickly if already loaded. */
export async function ensureFontLoaded(px) {
  if (!document.fonts?.load) return
  try {
    await document.fonts.load(`${Math.round(px)}px "Bebas Neue"`)
  } catch { /* fallback font is acceptable */ }
}
