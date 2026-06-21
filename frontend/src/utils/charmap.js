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
