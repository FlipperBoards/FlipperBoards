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

    # Center each line and convert to codes
    matrix = []
    for line in lines:
        padding = (cols - len(line)) // 2
        centered = " " * padding + line
        matrix.append(text_to_row(centered, cols))

    # Fill remaining rows with blank
    while len(matrix) < rows:
        matrix.append([0] * cols)

    return matrix


def blank_matrix(rows: int, cols: int) -> list[list[int]]:
    return [[0] * cols for _ in range(rows)]
