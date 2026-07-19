# Vestaboard-compatible character set
# Index 0 = blank, 1-26 = A-Z, 27-36 = 1-0, 37+ = symbols, 71-77 = colors

CHARS = [
    ' ',  # 0  blank
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',  # 1-10
    'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',  # 11-20
    'U', 'V', 'W', 'X', 'Y', 'Z',                        # 21-26
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',   # 27-36
    '!', '@', '#', '$', '(', ')', '-', '+', '&', '=',    # 37-46
    ';', ':', "'", '"', '%', ',', '.', '/', '?', '°',    # 47-56
    '♥', '♦', '♣', '♠',               # 57-60 hearts/diamonds/clubs/spades
    '★', '☆',                                    # 61-62 star/outline star
    '←', '↑', '→', '↓',               # 63-66 arrows
    '·',                                              # 67 middle dot
    '■',                                              # 68 filled square
    '○',                                              # 69 circle
    ' ',                                                   # 70 reserved
    'RED', 'ORANGE', 'YELLOW', 'GREEN', 'BLUE', 'VIOLET', 'WHITE',  # 71-77 color tiles
]

CHAR_TO_CODE = {}
for i, ch in enumerate(CHARS):
    if ch not in CHAR_TO_CODE and ch != ' ' or i == 0:
        CHAR_TO_CODE[ch] = i

# Additional mappings for common chars
CHAR_TO_CODE.update({
    ' ': 0,
    '\n': 0,
    '\t': 0,
})

COLOR_CODES = {
    'RED': 71, 'ORANGE': 72, 'YELLOW': 73,
    'GREEN': 74, 'BLUE': 75, 'VIOLET': 76, 'WHITE': 77,
}

COLOR_HEX = {
    71: '#e63946',  # red
    72: '#f4a261',  # orange
    73: '#e9c46a',  # yellow
    74: '#2a9d8f',  # green
    75: '#457b9d',  # blue
    76: '#7b2d8b',  # violet
    77: '#f1faee',  # white
}


def char_to_code(ch: str) -> int:
    ch_upper = ch.upper()
    if ch_upper in CHAR_TO_CODE:
        return CHAR_TO_CODE[ch_upper]
    return 0  # unknown -> blank


def text_to_row(text: str, cols: int) -> list[int]:
    row = []
    for ch in text.upper():
        row.append(char_to_code(ch))
        if len(row) >= cols:
            break
    while len(row) < cols:
        row.append(0)
    return row


def text_to_matrix(text: str, rows: int, cols: int) -> list[list[int]]:
    """Word-wrap text into a rows×cols matrix."""
    words = text.upper().split()
    lines = []
    current = ""
    for word in words:
        if len(word) > cols:
            # Split long word
            if current:
                lines.append(current)
                current = ""
            while word:
                lines.append(word[:cols])
                word = word[cols:]
        elif len(current) + len(word) + (1 if current else 0) <= cols:
            current = (current + " " + word).strip() if current else word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    # Truncate to available rows
    lines = lines[:rows]

    # Center each line horizontally and convert to codes
    text_rows = []
    for line in lines:
        padding = (cols - len(line)) // 2
        centered = " " * padding + line
        text_rows.append(text_to_row(centered, cols))

    # Vertical centering: blank rows above so text block is centered
    top_pad = (rows - len(text_rows)) // 2
    matrix = [[0] * cols for _ in range(top_pad)]
    matrix.extend(text_rows)
    while len(matrix) < rows:
        matrix.append([0] * cols)

    return matrix


def blank_matrix(rows: int, cols: int) -> list[list[int]]:
    return [[0] * cols for _ in range(rows)]


# ── Colored text markup ───────────────────────────────────────────────────────
# {red}HAPPY HOUR{/} — colors the enclosed characters. Something a physical
# split-flap board can't do.

import re as _re

MARKUP_COLORS = {
    "red": "#e63946", "orange": "#f4a261", "yellow": "#e9c46a",
    "green": "#2a9d8f", "blue": "#457b9d", "violet": "#7b2d8b",
    "white": "#f1faee",
}

_MARKUP_RE = _re.compile(r"\{(red|orange|yellow|green|blue|violet|white|/)\}", _re.IGNORECASE)


def parse_colored_text(text: str) -> tuple[str, list]:
    """Strip {color}…{/} markup. Returns (clean_text, per-char hex-or-None)."""
    clean_parts: list[str] = []
    colors: list = []
    current = None
    pos = 0
    for m in _MARKUP_RE.finditer(text):
        seg = text[pos:m.start()]
        clean_parts.append(seg)
        colors.extend([current] * len(seg))
        tag = m.group(1).lower()
        current = None if tag == "/" else MARKUP_COLORS[tag]
        pos = m.end()
    seg = text[pos:]
    clean_parts.append(seg)
    colors.extend([current] * len(seg))
    return "".join(clean_parts), colors


def text_to_matrix_colored(text: str, rows: int, cols: int):
    """Like text_to_matrix but honoring color markup. Returns
    (matrix, color_map) — color_map is rows×cols of hex-or-None, or None
    when the text carries no markup."""
    clean, char_colors = parse_colored_text(text)

    # Words as (char, color) pair lists, mirroring text_to_matrix's wrapping
    words: list[list] = []
    current_word: list = []
    for ch, color in zip(clean, char_colors, strict=True):
        if ch.isspace():
            if current_word:
                words.append(current_word)
                current_word = []
        else:
            current_word.append((ch.upper(), color))
    if current_word:
        words.append(current_word)

    lines: list[list] = []
    line: list = []
    for word in words:
        if len(word) > cols:
            if line:
                lines.append(line)
                line = []
            while word:
                lines.append(word[:cols])
                word = word[cols:]
        elif len(line) + len(word) + (1 if line else 0) <= cols:
            if line:
                line.append((" ", None))
            line.extend(word)
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    lines = lines[:rows]

    matrix_rows, color_rows = [], []
    for ln in lines:
        pad = max(0, (cols - len(ln)) // 2)
        row = [0] * cols
        crow = [None] * cols
        for i, (ch, color) in enumerate(ln):
            if pad + i < cols:
                row[pad + i] = char_to_code(ch)
                crow[pad + i] = color
        matrix_rows.append(row)
        color_rows.append(crow)

    top_pad = max(0, (rows - len(matrix_rows)) // 2)
    matrix = [[0] * cols for _ in range(top_pad)]
    cmap = [[None] * cols for _ in range(top_pad)]
    matrix.extend(matrix_rows)
    cmap.extend(color_rows)
    while len(matrix) < rows:
        matrix.append([0] * cols)
        cmap.append([None] * cols)

    if all(c is None for r in cmap for c in r):
        cmap = None
    return matrix, cmap
