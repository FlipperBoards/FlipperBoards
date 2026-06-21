// Maps each tile to the nearest Vestaboard color using Euclidean RGB distance.
// No server-side processing needed — runs entirely in the browser via Canvas API.

// Vestaboard color palette (code -> [R, G, B])
const COLOR_PALETTE = [
  [0,   [26,  26,  26 ]],  // 0  = blank/black
  [71,  [230, 57,  70 ]],  // RED
  [72,  [244, 162, 97 ]],  // ORANGE
  [73,  [233, 196, 106]],  // YELLOW
  [74,  [42,  157, 143]],  // GREEN
  [75,  [69,  123, 157]],  // BLUE
  [76,  [123, 45,  139]],  // VIOLET
  [77,  [241, 250, 238]],  // WHITE
]

function nearestColorCode(r, g, b) {
  let bestCode = 0
  let bestDist = Infinity
  for (const [code, [cr, cg, cb]] of COLOR_PALETTE) {
    const dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
    if (dist < bestDist) { bestDist = dist; bestCode = code }
  }
  return bestCode
}

// Brightness character codes — ordered dark to bright
// Uses characters from our Vestaboard char set that have different visual densities
const BRIGHTNESS_CODES = [
  0,   // blank    — darkest
  47,  // ';'
  46,  // ':'
  57,  // '.'
  38,  // '+'
  68,  // '■'      — brightest
]

function brightnessToCode(r, g, b) {
  const luma = 0.299 * r + 0.587 * g + 0.114 * b  // perceived brightness 0–255
  const idx = Math.round((luma / 255) * (BRIGHTNESS_CODES.length - 1))
  return BRIGHTNESS_CODES[idx]
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

/**
 * Convert an image File into a Vestaboard character matrix.
 * @param {File} file - image file
 * @param {number} rows - display rows
 * @param {number} cols - display columns
 * @param {'color'|'mono'} mode - color mosaic or monochrome character
 * @returns {Promise<number[][]>} matrix of character codes
 */
export async function imageToMatrix(file, rows, cols, mode = 'color') {
  const url = URL.createObjectURL(file)
  try {
    const img = await loadImage(url)

    const canvas = document.createElement('canvas')
    canvas.width = cols
    canvas.height = rows
    const ctx = canvas.getContext('2d')

    // Draw image, fitting it into rows×cols (each "pixel" = one tile)
    ctx.drawImage(img, 0, 0, cols, rows)
    const { data } = ctx.getImageData(0, 0, cols, rows)

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
  } finally {
    URL.revokeObjectURL(url)
  }
}

/**
 * Generate a preview canvas (scaled-up version of what the board will show).
 * Useful for the "before you push" preview in the remote control.
 */
export function matrixToPreviewCanvas(matrix, rows, cols, tileSize = 16) {
  const canvas = document.createElement('canvas')
  canvas.width = cols * tileSize
  canvas.height = rows * tileSize
  const ctx = canvas.getContext('2d')

  const COLOR_HEX = {
    0: '#1a1a1a',
    71: '#e63946', 72: '#f4a261', 73: '#e9c46a',
    74: '#2a9d8f', 75: '#457b9d', 76: '#7b2d8b', 77: '#f1faee',
  }

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const code = matrix[r]?.[c] ?? 0
      ctx.fillStyle = COLOR_HEX[code] || '#2a2a2a'
      ctx.fillRect(c * tileSize, r * tileSize, tileSize - 1, tileSize - 1)
    }
  }
  return canvas
}
