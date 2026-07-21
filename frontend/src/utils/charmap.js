// Mirrors backend charmap.py — Vestaboard-compatible character set
export const CHARS = [
  ' ',                                                          // 0
  'A','B','C','D','E','F','G','H','I','J',                     // 1-10
  'K','L','M','N','O','P','Q','R','S','T',                     // 11-20
  'U','V','W','X','Y','Z',                                     // 21-26
  '1','2','3','4','5','6','7','8','9','0',                     // 27-36
  '!','@','#','$','(',')','-','+','&','=',                     // 37-46
  ';',':',`'`,'"','%',',','.','/',`?`,'°',                    // 47-56
  '♥','♦','♣','♠',                                            // 57-60
  '★','☆',                                                    // 61-62
  '←','↑','→','↓',                                           // 63-66
  '·','■','○',                                                // 67-69
  ' ',                                                         // 70 reserved
  'RED','ORANGE','YELLOW','GREEN','BLUE','VIOLET','WHITE',     // 71-77 color tiles
]

export const COLOR_HEX = {
  71: '#e63946',
  72: '#f4a261',
  73: '#e9c46a',
  74: '#2a9d8f',
  75: '#457b9d',
  76: '#7b2d8b',
  77: '#f1faee',
}

export const COLOR_NAMES = {
  71: 'RED', 72: 'ORANGE', 73: 'YELLOW',
  74: 'GREEN', 75: 'BLUE', 76: 'VIOLET', 77: 'WHITE',
}

export const isColorCode = (code) => code >= 71 && code <= 77

export const codeToChar = (code) => {
  if (code < 0 || code >= CHARS.length) return ' '
  return CHARS[code]
}

const CHAR_TO_CODE = {}
CHARS.forEach((ch, i) => {
  if (!(ch in CHAR_TO_CODE) || i === 0) CHAR_TO_CODE[ch] = i
})
CHAR_TO_CODE[' '] = 0

export const charToCode = (ch) => CHAR_TO_CODE[ch.toUpperCase()] ?? 0

// ── Text sanitizing — mirrors backend charmap.sanitize_text ──────────────────
// Fold "smart" punctuation and accented letters to ASCII look-alikes and drop
// anything still unrenderable, so text collapses (JOSÉ'S → JOSE'S) instead of
// leaving a blank tile mid-word.
const PUNCT_FOLD = {
  '‘': "'", '’': "'", '‚': "'", '′': "'", '`': "'",
  '“': '"', '”': '"', '„': '"', '″': '"',
  '–': '-', '—': '-', '―': '-', '−': '-',
  '…': '...',
  ' ': ' ', ' ': ' ', ' ': ' ', '​': '',
  '•': '·', '·': '·',
}

export function sanitizeText(text) {
  if (!text) return text ?? ''
  let out = ''
  for (const ch of text) {
    if (ch in PUNCT_FOLD) { out += PUNCT_FOLD[ch]; continue }
    if (ch === '\n' || ch === '\t' || ch.toUpperCase() in CHAR_TO_CODE) { out += ch; continue }
    // Fold accents to base letters, then keep only renderable pieces
    const base = ch.normalize('NFKD').replace(/\p{M}/gu, '')
    for (const b of base) if (b.toUpperCase() in CHAR_TO_CODE) out += b
  }
  return out
}

/** Mirrors backend charmap.text_to_matrix: word-wrap, center each line
 * horizontally, center the block vertically. Used for local previews. */
export function textToMatrix(text, rows, cols) {
  const words = sanitizeText(text).toUpperCase().split(/\s+/).filter(Boolean)
  const lines = []
  let current = ''
  for (let word of words) {
    if (word.length > cols) {
      if (current) { lines.push(current); current = '' }
      while (word) { lines.push(word.slice(0, cols)); word = word.slice(cols) }
    } else if (current.length + word.length + (current ? 1 : 0) <= cols) {
      current = current ? `${current} ${word}` : word
    } else {
      lines.push(current)
      current = word
    }
  }
  if (current) lines.push(current)

  const textRows = lines.slice(0, rows).map(line => {
    const pad = Math.max(0, Math.floor((cols - line.length) / 2))
    const centered = ' '.repeat(pad) + line
    const row = []
    for (let c = 0; c < cols; c++) row.push(charToCode(centered[c] ?? ' '))
    return row
  })

  const topPad = Math.max(0, Math.floor((rows - textRows.length) / 2))
  const matrix = Array.from({ length: topPad }, () => Array(cols).fill(0))
  matrix.push(...textRows)
  while (matrix.length < rows) matrix.push(Array(cols).fill(0))
  return matrix
}

// ── Colored text markup — mirrors backend charmap.parse_colored_text ─────────
// {red}HAPPY HOUR{/} colors the enclosed characters.

export const MARKUP_COLORS = {
  red: '#e63946', orange: '#f4a261', yellow: '#e9c46a',
  green: '#2a9d8f', blue: '#457b9d', violet: '#7b2d8b',
  white: '#f1faee',
}

const MARKUP_RE = /\{(red|orange|yellow|green|blue|violet|white|\/)\}/gi

/** Strip {color}…{/} markup. Returns [cleanText, perCharHexOrNull[]]. */
export function parseColoredText(text) {
  const cleanParts = []
  const colors = []
  let current = null
  let pos = 0
  MARKUP_RE.lastIndex = 0
  let m
  while ((m = MARKUP_RE.exec(text)) !== null) {
    const seg = text.slice(pos, m.index)
    cleanParts.push(seg)
    for (let i = 0; i < seg.length; i++) colors.push(current)
    const tag = m[1].toLowerCase()
    current = tag === '/' ? null : MARKUP_COLORS[tag]
    pos = m.index + m[0].length
  }
  const seg = text.slice(pos)
  cleanParts.push(seg)
  for (let i = 0; i < seg.length; i++) colors.push(current)
  return [cleanParts.join(''), colors]
}

/** Like textToMatrix but honoring color markup. Returns [matrix, colorMap]
 * — colorMap is rows×cols of hex-or-null, or null when no markup. */
export function textToMatrixColored(text, rows, cols) {
  const [clean, charColors] = parseColoredText(text)

  // Fold/strip unrenderable characters, keeping each survivor's color, then
  // split into words — mirrors textToMatrix's wrapping. A char may vanish
  // (emoji) or expand (… → ...); colors follow one-to-one.
  const words = []
  let currentWord = []
  for (let i = 0; i < clean.length; i++) {
    for (const c of sanitizeText(clean[i])) {
      if (/\s/.test(c)) {
        if (currentWord.length) { words.push(currentWord); currentWord = [] }
      } else {
        currentWord.push([c.toUpperCase(), charColors[i]])
      }
    }
  }
  if (currentWord.length) words.push(currentWord)

  const lines = []
  let line = []
  for (let word of words) {
    if (word.length > cols) {
      if (line.length) { lines.push(line); line = [] }
      while (word.length) { lines.push(word.slice(0, cols)); word = word.slice(cols) }
    } else if (line.length + word.length + (line.length ? 1 : 0) <= cols) {
      if (line.length) line.push([' ', null])
      line.push(...word)
    } else {
      lines.push(line)
      line = word
    }
  }
  if (line.length) lines.push(line)

  const matrixRows = []
  const colorRows = []
  for (const ln of lines.slice(0, rows)) {
    const pad = Math.max(0, Math.floor((cols - ln.length) / 2))
    const row = Array(cols).fill(0)
    const crow = Array(cols).fill(null)
    ln.forEach(([ch, color], i) => {
      if (pad + i < cols) {
        row[pad + i] = charToCode(ch)
        crow[pad + i] = color
      }
    })
    matrixRows.push(row)
    colorRows.push(crow)
  }

  const topPad = Math.max(0, Math.floor((rows - matrixRows.length) / 2))
  const matrix = Array.from({ length: topPad }, () => Array(cols).fill(0))
  const cmap = Array.from({ length: topPad }, () => Array(cols).fill(null))
  matrix.push(...matrixRows)
  cmap.push(...colorRows)
  while (matrix.length < rows) {
    matrix.push(Array(cols).fill(0))
    cmap.push(Array(cols).fill(null))
  }

  const hasColor = cmap.some(r => r.some(c => c !== null))
  return [matrix, hasColor ? cmap : null]
}
