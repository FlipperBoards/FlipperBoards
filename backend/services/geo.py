"""Coordinate parsing shared by location-aware services (weather, drive times).

Accepts decimal pairs (`45.52, -122.68`) and the DMS format Google Maps
copies on right-click (`33°26'43.8"N 111°59'21.0"W`).
"""
import re

_COORD_RE = re.compile(r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")

# 33°26'43.8"N — degrees, optional minutes/seconds, hemisphere letter.
# Accepts straight and typographic quote marks (Google Maps uses both).
_DMS_PART = (r"(\d{1,3})\s*°\s*"
             r"(?:(\d{1,2}(?:\.\d+)?)\s*['′’]\s*)?"
             r"(?:(\d{1,2}(?:\.\d+)?)\s*[\"″”]\s*)?"
             r"([NSEW])")
_DMS_RE = re.compile(rf"^\s*{_DMS_PART}[\s,]+{_DMS_PART}\s*$", re.IGNORECASE)


def _dms_to_decimal(deg, minutes, seconds, hemi) -> float:
    value = float(deg) + float(minutes or 0) / 60 + float(seconds or 0) / 3600
    return -value if hemi.upper() in ("S", "W") else value


def parse_coords(place: str) -> tuple[float, float] | None:
    """`45.52, -122.68` or `33°26'43.8\"N 111°59'21.0\"W` → (lat, lng)."""
    m = _COORD_RE.match(place)
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))
    else:
        m = _DMS_RE.match(place)
        if not m:
            return None
        a = _dms_to_decimal(m.group(1), m.group(2), m.group(3), m.group(4))
        b = _dms_to_decimal(m.group(5), m.group(6), m.group(7), m.group(8))
        # Lat first is conventional, but accept either order via hemisphere
        if m.group(4).upper() in ("N", "S"):
            lat, lng = a, b
        else:
            lat, lng = b, a
    if -90 <= lat <= 90 and -180 <= lng <= 180:
        return lat, lng
    return None
