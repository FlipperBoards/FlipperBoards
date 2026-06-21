// Canvas-based image → tile matrix conversion. Runs entirely in the browser.

// ── Vestaboard 8-color palette ───────────────────────────────────────────────

const COLOR_PALETTE = [
  [0,   [26,  26,  26 ]],  // blank/black
  [71,  [230, 57,  70 ]],  // RED
  [72,  [244, 162, 97 ]],  // ORANGE
  [73,  [233, 196, 106]],  // YELLOW
  [74,  [42,  157, 143]],  // GREEN
  [75,  [69,  123, 157]],  // BLUE
  [76,  [123, 45,  139]],  // VIOLET
  [77,  [241, 250, 238]],  // WHITE
]

function nearestColorCode(r, g, b) {
  let bestCode = 0, bestDist = Infinity
  for (const [code, [cr, cg, cb]] of COLOR_PALETTE) {
    const dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
    if (dist < bestDist) { bestDist = dist; bestCode = code }
  }
  return bestCode
}

// ── Brightness character codes (dark → bright) ───────────────────────────────

const BRIGHTNESS_CODES = [0, 47, 46, 57, 38, 68]

function brightnessToCode(r, g, b) {
  const luma = 0.299 * r + 0.587 * g + 0.114 * b
  return BRIGHTNESS_CODES[Math.round((luma / 255) * (BRIGHTNESS_CODES.length - 1))]
}

// ── Shared canvas helper ──────────────────────────────────────────────────────

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

async function getPixelData(file, cols, rows) {
  const url = URL.createObjectURL(file)
  try {
    const img = await loadImage(url)
    const canvas = document.createElement('canvas')
    canvas.width = cols
    canvas.height = rows
    canvas.getContext('2d').drawImage(img, 0, 0, cols, rows)
    return canvas.getContext('2d').getImageData(0, 0, cols, rows).data
  } finally {
    URL.revokeObjectURL(url)
  }
}

function toHex(r, g, b) {
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Convert image to a Vestaboard character code matrix (8-color or mono).
 * Returns number[][]
 */
export async function imageToMatrix(file, rows, cols, mode = 'color') {
  const data = await getPixelData(file, cols, rows)
  const matrix = []
  for (let r = 0; r < rows; r++) {
    const row = []
    for (let c = 0; c < cols; c++) {
      const i = (r * cols + c) * 4
      const [R, G, B] = [data[i], data[i + 1], data[i + 2]]
      row.push(mode === 'color' ? nearestColorCode(R, G, B) : brightnessToCode(R, G, B))
    }
    matrix.push(row)
  }
  return matrix
}

/**
 * Convert image to a full-color hex matrix — every tile gets its exact RGB color.
 * Returns string[][] of CSS hex colors (e.g. "#ff5733")
 */
export async function imageToColorMatrix(file, rows, cols) {
  const data = await getPixelData(file, cols, rows)
  const matrix = []
  for (let r = 0; r < rows; r++) {
    const row = []
    for (let c = 0; c < cols; c++) {
      const i = (r * cols + c) * 4
      row.push(toHex(data[i], data[i + 1], data[i + 2]))
    }
    matrix.push(row)
  }
  return matrix
}

// ── Preview canvas generators ─────────────────────────────────────────────────

const CHAR_CODE_HEX = {
  0: '#1a1a1a',
  71: '#e63946', 72: '#f4a261', 73: '#e9c46a',
  74: '#2a9d8f', 75: '#457b9d', 76: '#7b2d8b', 77: '#f1faee',
}

/** Preview for 8-color or mono matrix (number[][]) */
export function matrixToPreviewCanvas(matrix, rows, cols, tileSize = 16) {
  const canvas = document.createElement('canvas')
  canvas.width = cols * tileSize
  canvas.height = rows * tileSize
  const ctx = canvas.getContext('2d')
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const code = matrix[r]?.[c] ?? 0
      ctx.fillStyle = CHAR_CODE_HEX[code] || '#2a2a2a'
      ctx.fillRect(c * tileSize, r * tileSize, tileSize - 1, tileSize - 1)
    }
  }
  return canvas
}

/** Preview for full-color matrix (string[][]) */
export function colorMatrixToPreviewCanvas(colorMatrix, rows, cols, tileSize = 16) {
  const canvas = document.createElement('canvas')
  canvas.width = cols * tileSize
  canvas.height = rows * tileSize
  const ctx = canvas.getContext('2d')
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      ctx.fillStyle = colorMatrix[r]?.[c] ?? '#000'
      ctx.fillRect(c * tileSize, r * tileSize, tileSize - 1, tileSize - 1)
    }
  }
  return canvas
}
