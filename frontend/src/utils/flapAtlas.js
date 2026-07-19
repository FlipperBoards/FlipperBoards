// Pre-rendered split-flap sprites for the canvas renderer.
//
// Every character card is drawn ONCE per (size, theme, text-color) into an
// offscreen atlas — including the mid-flip POSES, so the animation loop is
// nothing but same-size alpha blits (no runtime scaling, no fillRects, no
// gradient/string allocation). That keeps a full-board cascade inside a
// Raspberry Pi 3's software-raster budget.
//
// Atlas layout per color variant (one canvas, 3 rows × 78 columns):
//   row FACE — the full card: matte face, rounded corners, split line, glyph
//   row FALL — overlay: the char's top half folded ~55° toward the hinge,
//              with baked turn-darkening and a baked shadow on the lower half
//   row RISE — overlay: the char's bottom half partially risen from the
//              hinge, with baked landing highlight and fading lower shadow
//
// The Vestaboard look is baked into the face sprite itself: matte card with
// rounded corners, a vertical sheen that suggests the curved flap, and the
// horizontal split line through the middle where the two flaps meet.
import { CHARS, COLOR_HEX, isColorCode, codeToChar } from './charmap'

const FONT_FAMILY = '"Bebas Neue", "Share Tech Mono", monospace'

// Row indices — exported for the renderer's blit math
export const ROW_FACE = 0
export const ROW_FALL = 1
export const ROW_RISE = 2

const FALL_SCALE = Math.cos(55 * Math.PI / 180)  // ≈ 0.57 — flap folded ~55°
const RISE_SCALE = Math.sin(50 * Math.PI / 180)  // ≈ 0.77 — flap mostly risen

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

  // ── Row FACE: full card faces ──
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
      ctx.fillText(ch, x + tileW / 2, tileH / 2 + fs * 0.045, tileW * 0.94)
    }
    drawSplitLine(ctx, x, 0, tileW, tileH)
  }

  // ── Pose rows — sample the face row we just drew, all shading baked ──
  const half = tileH / 2
  for (let code = 0; code < CHARS.length; code++) {
    const x = code * tileW

    // Row FALL: shadow thrown on the lower half, then the top half of this
    // char folded toward the hinge and darkened as it turns away
    {
      const y = ROW_FALL * tileH
      ctx.fillStyle = 'rgba(0,0,0,0.16)'
      ctx.fillRect(x, y + half, tileW, half)
      const fh = Math.max(1, Math.round(half * FALL_SCALE))
      ctx.drawImage(canvas, x, 0, tileW, half, x, y + half - fh, tileW, fh)
      ctx.fillStyle = 'rgba(0,0,0,0.26)'
      ctx.fillRect(x, y + half - fh, tileW, fh)
    }

    // Row RISE: fading shadow on the lower half, then the bottom half of
    // this char mostly risen into place, still catching the light
    {
      const y = ROW_RISE * tileH
      ctx.fillStyle = 'rgba(0,0,0,0.10)'
      ctx.fillRect(x, y + half, tileW, half)
      const fh = Math.max(1, Math.round(half * RISE_SCALE))
      ctx.drawImage(canvas, x, half, tileW, half, x, y + half, tileW, fh)
      ctx.fillStyle = 'rgba(255,255,255,0.06)'
      ctx.fillRect(x, y + half, tileW, fh)
    }
  }
}

/**
 * Build a sprite atlas for a given tile size + theme. Variants for markup
 * text colors are rendered lazily — the palette is bounded (default + 7).
 *
 * `canvasFor(color)` returns the atlas canvas whose glyphs use that text
 * color. Source rect for a code is (code * tileW, row * tileH, tileW, tileH)
 * with row one of ROW_FACE / ROW_FALL / ROW_RISE.
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
      canvas.height = tileH * 3
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
