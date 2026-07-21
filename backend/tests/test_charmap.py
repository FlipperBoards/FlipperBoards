from charmap import (
    CHARS,
    blank_matrix,
    char_to_code,
    sanitize_text,
    text_to_matrix,
    text_to_matrix_colored,
    text_to_row,
)


def test_char_to_code_roundtrip():
    assert char_to_code("A") == 1
    assert char_to_code("Z") == 26
    assert char_to_code("1") == 27
    assert char_to_code("0") == 36
    assert char_to_code(" ") == 0
    assert char_to_code("a") == 1  # case-insensitive


def test_unknown_char_is_blank():
    assert char_to_code("~") == 0
    assert char_to_code("é") == 0


def test_text_to_row_pads_and_truncates():
    row = text_to_row("HI", 5)
    assert row == [8, 9, 0, 0, 0]
    row = text_to_row("ABCDEFGH", 3)
    assert len(row) == 3


def test_text_to_matrix_dimensions():
    m = text_to_matrix("HELLO WORLD", 6, 22)
    assert len(m) == 6
    assert all(len(r) == 22 for r in m)


def test_text_to_matrix_wraps_words():
    m = text_to_matrix("AAAA BBBB", 6, 5)
    joined = ["".join(CHARS[c] for c in row).strip() for row in m]
    lines = [line for line in joined if line]
    assert "AAAA" in lines and "BBBB" in lines


def test_text_to_matrix_centers_vertically():
    m = text_to_matrix("HI", 6, 22)
    non_blank_rows = [i for i, row in enumerate(m) if any(row)]
    assert non_blank_rows == [2]  # single line centered in 6 rows


def test_long_word_splits():
    m = text_to_matrix("ABCDEFGHIJ", 6, 4)
    assert any(any(row) for row in m)


def test_blank_matrix():
    m = blank_matrix(3, 4)
    assert m == [[0] * 4 for _ in range(3)]


# ── Sanitizing unrenderable characters ────────────────────────────────────────

def test_sanitize_folds_smart_punctuation():
    assert sanitize_text("IT’S") == "IT'S"          # curly apostrophe → straight
    assert sanitize_text("“HI”") == '"HI"'     # curly quotes
    assert sanitize_text("A—B") == "A-B"            # em dash → hyphen
    assert sanitize_text("WAIT…") == "WAIT..."      # ellipsis → ...


def test_sanitize_folds_accents():
    assert sanitize_text("JOSÉ") == "JOSE"          # É → E
    assert sanitize_text("montréal") == "montreal"  # é → e (case kept)
    assert sanitize_text("MUÑOZ") == "MUNOZ"        # Ñ → N


def test_sanitize_strips_unrenderable():
    # A char with no tile and no ASCII fold is dropped, not left as a gap
    assert sanitize_text("A\U0001F600B") == "AB"         # emoji removed
    assert sanitize_text("C★D") == "C★D"       # ★ has a tile, kept
    assert sanitize_text("50°F") == "50°F"     # ° has a tile, kept


def test_sanitize_is_idempotent_on_plain_text():
    plain = "HELLO WORLD 123 -+&"
    assert sanitize_text(plain) == plain


def test_curly_apostrophe_no_blank_gap():
    # The reported bug: a curly apostrophe left a blank tile between word and 'S
    row = text_to_row("IT’S", 6)
    codes = [c for c in row if c != 0]
    # I, T, ', S — four contiguous non-blank tiles, no hole
    assert codes == [char_to_code(c) for c in "IT'S"]


def test_text_to_matrix_folds_feed_content():
    m = text_to_matrix("CAFÉ CLOSED…", 6, 22)
    joined = " ".join("".join(CHARS[c] for c in row).strip() for row in m if any(row))
    assert "CAFE" in joined
    assert "..." in joined


def test_colored_text_stays_aligned_after_fold():
    # {red}…{/} coloring must still line up when a char folds to a different
    # length (… → ...). Folding happens in the matrix builder, not the parser.
    m, cmap = text_to_matrix_colored("{red}CAF…{/}X", 6, 22)
    r = next(i for i, row in enumerate(m) if any(row))
    chars = "".join(CHARS[c] for c in m[r])
    idx = chars.index("CAF")
    assert chars[idx:idx + 7] == "CAF...X"
    assert cmap[r][idx] == "#e63946"        # C red
    assert cmap[r][idx + 5] == "#e63946"    # last '.' of the folded ellipsis, red
    assert cmap[r][idx + 6] is None         # X uncolored


def test_colored_matrix_renders_folded_text():
    m, cmap = text_to_matrix_colored("{green}JOSÉ{/}", 6, 22)
    joined = " ".join("".join(CHARS[c] for c in row).strip() for row in m if any(row))
    assert "JOSE" in joined
    assert cmap is not None
