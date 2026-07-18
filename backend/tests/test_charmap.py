from charmap import blank_matrix, char_to_code, text_to_matrix, text_to_row, CHARS


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
