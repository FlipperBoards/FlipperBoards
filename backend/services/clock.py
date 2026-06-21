from datetime import datetime
import pytz
from charmap import text_to_row, blank_matrix


DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def get_clock_matrix(rows: int, cols: int, fmt: str = "12h",
                     show_date: bool = True, timezone: str = "UTC") -> list[list[int]]:
    try:
        tz = pytz.timezone(timezone)
    except Exception:
        tz = pytz.utc

    now = datetime.now(tz)
    matrix = blank_matrix(rows, cols)

    if fmt == "12h":
        hour = now.hour % 12 or 12
        ampm = "AM" if now.hour < 12 else "PM"
        time_str = f"{hour:2d}:{now.minute:02d}:{now.second:02d} {ampm}"
    else:
        time_str = f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}"

    # Center time in first row
    pad = (cols - len(time_str)) // 2
    time_line = " " * pad + time_str
    matrix[0] = text_to_row(time_line, cols)

    if show_date and rows > 1:
        day_name = DAYS[now.weekday()]
        month = MONTHS[now.month - 1]
        date_str = f"{day_name}, {month} {now.day}, {now.year}"
        pad = (cols - len(date_str)) // 2
        date_line = " " * pad + date_str
        matrix[1] = text_to_row(date_line, cols)

    return matrix
