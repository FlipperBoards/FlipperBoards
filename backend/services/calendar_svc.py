import httpx
from datetime import datetime
import pytz
from charmap import text_to_row, blank_matrix


def _compact_time(dt: datetime) -> str:
    """Shortest legible time: 7P, 11A, 12P (noon), 12A (midnight), 7:15P."""
    hour = dt.hour % 12 or 12
    meridian = "A" if dt.hour < 12 else "P"
    if dt.minute == 0:
        return f"{hour}{meridian}"
    return f"{hour}:{dt.minute:02d}{meridian}"


def _event_line(cols: int, date_str: str, time_str: str, title: str) -> str:
    """`7/20 PUTTING PRACTICE  7P` — short date left, time right-aligned (or
    absent for all-day), title fills everything in between."""
    gaps = 2 if time_str else 1
    available = cols - len(date_str) - len(time_str) - gaps
    title = (title or "").strip().upper()
    if available < 1:
        available = 1
    if len(title) > available:
        title = title[: available - 1] + "." if available > 1 else title[:1]

    left = f"{date_str} {title}"
    if time_str:
        # Right-align the time, keeping at least one column of gap
        pad = max(1, cols - len(left) - len(time_str))
        return (left + " " * pad + time_str)[:cols]
    return left[:cols]


async def get_calendar_matrix(rows: int, cols: int, ical_url: str = "",
                               timezone: str = "UTC") -> list[list[int]]:
    matrix = blank_matrix(rows, cols)

    if not ical_url:
        msg = "CALENDAR: NO ICAL URL SET"
        pad = max(0, (cols - len(msg)) // 2)
        matrix[0] = text_to_row(" " * pad + msg, cols)
        return matrix

    events = await _fetch_events(ical_url, timezone)

    if not events:
        msg = "NO UPCOMING EVENTS"
        pad = max(0, (cols - len(msg)) // 2)
        matrix[0] = text_to_row(" " * pad + msg, cols)
        return matrix

    # Show header
    header = "UPCOMING EVENTS"
    pad = max(0, (cols - len(header)) // 2)
    matrix[0] = text_to_row(" " * pad + header, cols)

    for i, event in enumerate(events[:rows - 1]):
        dt = event["start"]
        date_str = f"{dt.month}/{dt.day}"
        time_str = "" if event.get("all_day") else _compact_time(dt)
        line = _event_line(cols, date_str, time_str, event["title"])
        matrix[i + 1] = text_to_row(line, cols)

    return matrix


async def _fetch_events(ical_url: str, timezone: str) -> list:
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(ical_url)
            resp.raise_for_status()
            content = resp.text
    except Exception:
        return []

    try:
        tz = pytz.timezone(timezone)
    except Exception:
        tz = pytz.utc

    now = datetime.now(tz)
    events = []

    # RFC 5545 line unfolding: continuation lines start with a space/tab and
    # belong to the previous line (long SUMMARYs are folded by every provider)
    unfolded: list[str] = []
    for raw in content.splitlines():
        if raw[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += raw[1:]
        else:
            unfolded.append(raw)

    # Simple iCal parser (single events only — RRULE recurrences not expanded)
    current_event = {}
    in_event = False
    for line in unfolded:
        line = line.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
            current_event = {}
        elif line == "END:VEVENT" and in_event:
            in_event = False
            start = current_event.get("start")
            title = current_event.get("title", "UNTITLED")
            if start and start > now:
                events.append({"start": start, "title": title,
                               "all_day": current_event.get("all_day", False)})
        elif in_event:
            if line.startswith("SUMMARY"):
                current_event["title"] = line.split(":", 1)[-1].strip()
            elif line.startswith("DTSTART"):
                dt_str = line.split(":", 1)[-1].strip()
                start_dt = _parse_ical_dt(dt_str, tz)
                if start_dt:
                    current_event["start"] = start_dt
                    # Date-only DTSTART (no time component) → all-day event
                    current_event["all_day"] = "T" not in dt_str

    events.sort(key=lambda e: e["start"])
    return events[:10]


def _parse_ical_dt(dt_str: str, tz) -> datetime | None:
    # A trailing Z means the timestamp is UTC — parse as UTC, then convert
    # to the display timezone (stripping it silently shifts every event by
    # the local UTC offset).
    is_utc = dt_str.endswith("Z")
    if is_utc:
        dt_str = dt_str[:-1]
    formats = ["%Y%m%dT%H%M%S", "%Y%m%d"]
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if is_utc:
                dt = pytz.utc.localize(dt).astimezone(tz)
            else:
                dt = tz.localize(dt)
            return dt
        except ValueError:
            continue
    return None
