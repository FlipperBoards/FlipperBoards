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

/** Mirrors backend charmap.text_to_matrix: word-wrap, center each line
 * horizontally, center the block vertically. Used for local previews. */
export function textToMatrix(text, rows, cols) {
  const words = text.toUpperCase().split(/\s+/).filter(Boolean)
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
