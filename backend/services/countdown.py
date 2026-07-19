"""Countdown / count-up rendering.

    ······ NEW YEARS ······
    ······ 165 DAYS ······
    ······ 07:23:45 ······

Re-rendered by the 1-second tick loop, so only the second digits flip.
"""
from datetime import datetime

import pytz

from charmap import blank_matrix, text_to_row


def _center_row(text: str, cols: int) -> list[int]:
    text = text[:cols]
    pad = max(0, (cols - len(text)) // 2)
    return text_to_row(" " * pad + text, cols)


def _parse_target(target: str, tz) -> datetime | None:
    target = (target or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return tz.localize(datetime.strptime(target, fmt))
        except ValueError:
            continue
    return None


def get_countdown_matrix(rows: int, cols: int, target: str = "",
                         label: str = "", done_text: str = "",
                         count_up: bool = False,
                         timezone: str = "UTC",
                         now: datetime | None = None) -> list[list[int]]:
    try:
        tz = pytz.timezone(timezone)
    except Exception:
        tz = pytz.utc

    matrix = blank_matrix(rows, cols)
    target_dt = _parse_target(target, tz)
    if target_dt is None:
        matrix[rows // 2] = _center_row("SET A TARGET DATE", cols)
        return matrix

    now = now or datetime.now(tz)
    delta = (now - target_dt) if count_up else (target_dt - now)

    if delta.total_seconds() < 0 and not count_up:
        # Countdown finished
        lines = [(label or "").strip().upper(), (done_text or "IT'S TIME!").strip().upper()]
    else:
        seconds = max(0, int(delta.total_seconds()))
        days, rem = divmod(seconds, 86400)
        h, rem = divmod(rem, 3600)
        m, s = divmod(rem, 60)
        clock = f"{h:02d}:{m:02d}:{s:02d}"
        day_line = f"{days} DAY" + ("" if days == 1 else "S") if days else ""
        lines = [(label or "").strip().upper(), day_line, clock]

    lines = [ln for ln in lines if ln][:rows]
    top = max(0, (rows - len(lines)) // 2)
    for i, line in enumerate(lines):
        matrix[top + i] = _center_row(line, cols)
    return matrix
