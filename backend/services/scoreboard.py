"""Scoreboard rendering — two teams with live scores.

Layout on a 6x22 board:

    . . . . . . . . . . . . . . . . . . . . . .
    G . H A W K S . . . . . . . . . . . . . 1 2
    . . . . . . . . . . . . . . . . . . . . . .
    R . O W L S . . . . . . . . . . . . . . . 7
    . . . . . . . . . . . . . . . . . . . . . .
    . . . . . . . . . . . . . . . . . . . . . .

G/R = green/red color accent tiles. Names left-aligned, scores
right-aligned so a score change only flips its own digit tiles.
"""

from charmap import blank_matrix, char_to_code, sanitize_text

HOME_ACCENT = 74  # green
AWAY_ACCENT = 71  # red


def _clamp_score(value) -> int:
    try:
        return max(0, min(999, int(value)))
    except (TypeError, ValueError):
        return 0


def _team_row(cols: int, accent: int, name: str, score: int) -> list[int]:
    row = [0] * cols
    score_str = str(score)
    if cols < 4:
        for i, ch in enumerate(score_str[: cols]):
            row[i] = char_to_code(ch)
        return row

    row[0] = accent
    # Right-align score; keep a gap column between name and score
    score_start = cols - len(score_str)
    name_max = score_start - 3  # accent + space before name, space before score
    name = sanitize_text((name or "").strip()).upper()[: max(0, name_max)]
    for i, ch in enumerate(name):
        row[2 + i] = char_to_code(ch)
    for i, ch in enumerate(score_str):
        row[score_start + i] = char_to_code(ch)
    return row


def get_scoreboard_matrix(rows: int, cols: int,
                          home_name: str = "HOME", away_name: str = "AWAY",
                          home_score=0, away_score=0) -> list[list[int]]:
    home_score = _clamp_score(home_score)
    away_score = _clamp_score(away_score)

    if rows == 1:
        # Single combined row: HOM 3-1 AWY
        home_abbr = sanitize_text(home_name or "H").upper()[:3] or "H"
        away_abbr = sanitize_text(away_name or "A").upper()[:3] or "A"
        text = f"{home_abbr} {home_score}-{away_score} {away_abbr}"
        row = [0] * cols
        start = max(0, (cols - len(text)) // 2)
        for i, ch in enumerate(text[: cols - start]):
            row[start + i] = char_to_code(ch)
        return [row]

    matrix = blank_matrix(rows, cols)
    spacer = 1 if rows >= 3 else 0
    block_rows = 2 + spacer
    top_pad = (rows - block_rows) // 2

    matrix[top_pad] = _team_row(cols, HOME_ACCENT, home_name, home_score)
    matrix[top_pad + 1 + spacer] = _team_row(cols, AWAY_ACCENT, away_name, away_score)
    return matrix
