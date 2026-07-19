"""Menu / price-list rendering — the classic bar board.

    ····· HAPPY HOUR ·····
    IPA DRAFT········6.50
    HOUSE RED········8.00
    NACHOS··········12.00

Dot leaders use tile code 67 (·). Prices right-aligned so a price change
flips only its own digits. More entries than rows paginate per rotation
tick using a per-screen cursor.
"""
from charmap import blank_matrix, char_to_code

DOT = 67

_cursor: dict[str, int] = {}


def _entry_row(cols: int, name: str, price: str) -> list[int]:
    row = [0] * cols
    price = (price or "").strip().upper()
    name = (name or "").strip().upper()
    price_start = cols - len(price)
    name_max = max(0, price_start - 2)  # at least one dot + breathing room
    name = name[:name_max]
    for i, ch in enumerate(name):
        row[i] = char_to_code(ch)
    # Dot leaders between name and price
    for i in range(len(name) + 1, price_start - 1):
        row[i] = DOT
    for i, ch in enumerate(price):
        row[price_start + i] = char_to_code(ch)
    return row


def get_menu_matrix(rows: int, cols: int, title: str = "",
                    entries: list | None = None,
                    screen_id: str = "main") -> list[list[int]]:
    entries = [e for e in (entries or [])
               if (e.get("name") or "").strip() or (e.get("price") or "").strip()]
    matrix = blank_matrix(rows, cols)

    title = (title or "").strip().upper()
    has_title = bool(title) and rows >= 3
    body_rows = rows - (2 if has_title else 0)  # title + spacer row

    if has_title:
        pad = max(0, (cols - len(title)) // 2)
        for i, ch in enumerate(title[:cols]):
            matrix[0][pad + i] = char_to_code(ch)

    if not entries:
        return matrix

    # Paginate when the menu is longer than the board
    start = 0
    if len(entries) > body_rows:
        key = screen_id
        page = _cursor.get(key, 0)
        pages = (len(entries) + body_rows - 1) // body_rows
        start = (page % pages) * body_rows
        _cursor[key] = page + 1

    offset = 2 if has_title else 0
    for i, entry in enumerate(entries[start:start + body_rows]):
        matrix[offset + i] = _entry_row(cols, entry.get("name", ""), entry.get("price", ""))

    return matrix
