from services.scoreboard import get_scoreboard_matrix, HOME_ACCENT, AWAY_ACCENT


def test_layout_6x22():
    m = get_scoreboard_matrix(6, 22, "HAWKS", "OWLS", 12, 7)
    assert len(m) == 6 and all(len(r) == 22 for r in m)
    home_row = m[1]
    away_row = m[3]
    assert home_row[0] == HOME_ACCENT
    assert away_row[0] == AWAY_ACCENT
    # scores right-aligned
    assert home_row[20] == 27  # '1'
    assert home_row[21] == 28  # '2'
    assert away_row[21] == 33  # '7'


def test_score_bump_flips_only_changed_digit():
    a = get_scoreboard_matrix(6, 22, "HAWKS", "OWLS", 12, 7)
    b = get_scoreboard_matrix(6, 22, "HAWKS", "OWLS", 13, 7)
    diff = [(r, c) for r in range(6) for c in range(22) if a[r][c] != b[r][c]]
    assert diff == [(1, 21)]


def test_score_clamping():
    m = get_scoreboard_matrix(6, 22, "A", "B", -5, 100000)
    # -5 clamps to 0, 100000 clamps to 999
    assert m[1][21] == 36        # '0'
    assert m[3][19:22] == [35, 35, 35]  # '999'


def test_bad_score_types():
    m = get_scoreboard_matrix(6, 22, "A", "B", "abc", None)
    assert m[1][21] == 36  # falls back to 0


def test_long_names_truncated():
    m = get_scoreboard_matrix(6, 22, "X" * 50, "Y" * 50, 0, 0)
    assert all(len(r) == 22 for r in m)


def test_single_row_board():
    m = get_scoreboard_matrix(1, 22, "HAWKS", "OWLS", 3, 1)
    assert len(m) == 1 and len(m[0]) == 22
    assert any(m[0])


def test_two_row_board():
    m = get_scoreboard_matrix(2, 10, "AAA", "BBB", 1, 2)
    assert m[0][0] == HOME_ACCENT
    assert m[1][0] == AWAY_ACCENT
