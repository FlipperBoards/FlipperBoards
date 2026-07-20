import httpx
from charmap import text_to_row, blank_matrix
from services.geo import parse_coords

PIRATE_BASE = "https://api.pirateweather.net/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
METEO_URL = "https://api.open-meteo.com/v1/forecast"

# location string → (lat, lon, city, country) — geocoding results are stable
_geo_cache: dict[str, tuple] = {}

WMO_CODES = {
    0: "CLEAR SKY", 1: "MAINLY CLEAR", 2: "PARTLY CLOUDY", 3: "OVERCAST",
    45: "FOGGY", 48: "RIME FOG",
    51: "LIGHT DRIZZLE", 53: "DRIZZLE", 55: "HEAVY DRIZZLE",
    61: "LIGHT RAIN", 63: "RAIN", 65: "HEAVY RAIN",
    71: "LIGHT SNOW", 73: "SNOW", 75: "HEAVY SNOW", 77: "SNOW GRAINS",
    80: "RAIN SHOWERS", 81: "SHOWERS", 82: "HEAVY SHOWERS",
    85: "SNOW SHOWERS", 86: "HEAVY SNOW SHOWERS",
    95: "THUNDERSTORM", 96: "THUNDERSTORM W/ HAIL", 99: "HEAVY T-STORM",
}


async def get_weather_matrix(rows: int, cols: int, api_key: str = "",
                              location: str = "", units: str = "imperial") -> list[list[int]]:
    if not location:
        return _error_matrix(rows, cols, "WEATHER: SET LOCATION IN SETTINGS")

    unit_sym = "F" if units == "imperial" else "C"

    # Try Pirate Weather if a key is provided (pirateweather.net — free tier)
    if api_key:
        result = await _pirate(rows, cols, api_key, location, units, unit_sym)
        if result:
            return result

    # Fallback: Open-Meteo (no API key required)
    return await _open_meteo(rows, cols, location, units, unit_sym)


def resolve_coords(location: str):
    """Coordinate locations skip geocoding. Accepts a `Name |` label prefix:
    `Home | 33.413, -111.604` → (33.413, -111.604, "HOME", "").
    Returns None when the string isn't coordinates (geocode it instead)."""
    label = ""
    place = location
    if "|" in location:
        label, place = location.split("|", 1)
        label, place = label.strip(), place.strip()
    coords = parse_coords(place)
    if not coords:
        return None
    return (coords[0], coords[1], (label or "LOCAL").upper(), "")


async def _geocode(client, location):
    """Location → (lat, lon, city, country); coordinates resolve directly,
    names go through Open-Meteo's geocoder."""
    direct = resolve_coords(location)
    if direct:
        return direct
    cached = _geo_cache.get(location)
    if cached:
        return cached
    resp = await client.get(GEOCODING_URL,
                            params={"name": location, "count": 1, "language": "en"})
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return None
    place = results[0]
    entry = (place["latitude"], place["longitude"],
             place.get("name", location).upper(),
             place.get("country_code", "").upper())
    _geo_cache[location] = entry
    return entry


def parse_pirate(data: dict) -> dict | None:
    """Pirate Weather (Dark Sky format) payload → display fields."""
    try:
        cur = data["currently"]
        temp = round(cur["temperature"])
    except (KeyError, TypeError, ValueError):
        return None
    daily = (data.get("daily", {}).get("data") or [{}])[0]
    return {
        "temp": temp,
        "feels": round(cur.get("apparentTemperature", temp)),
        "humidity": round(float(cur.get("humidity", 0)) * 100),
        "desc": str(cur.get("summary", "")).upper(),
        "high": round(daily.get("temperatureHigh", temp)),
        "low": round(daily.get("temperatureLow", temp)),
    }


async def _pirate(rows, cols, api_key, location, units, unit_sym):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            geo = await _geocode(client, location)
            if not geo:
                return _error_matrix(rows, cols, f"LOCATION NOT FOUND: {location.upper()}")
            lat, lon, city, country = geo
            resp = await client.get(
                f"{PIRATE_BASE}/{api_key}/{lat},{lon}",
                params={"units": "us" if units == "imperial" else "si",
                        "exclude": "minutely,hourly,alerts"})
            resp.raise_for_status()
            w = parse_pirate(resp.json())
        if not w:
            return None
        return _build_matrix(rows, cols, city, country, w["temp"], w["feels"],
                             w["high"], w["low"], w["humidity"], w["desc"], unit_sym)
    except Exception:
        return None


async def _open_meteo(rows, cols, location, units, unit_sym):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            geo = await _geocode(client, location)
            if not geo:
                return _error_matrix(rows, cols, f"LOCATION NOT FOUND: {location.upper()}")
            lat, lon, city, country = geo

            temp_unit = "fahrenheit" if units == "imperial" else "celsius"
            forecast = await client.get(
                METEO_URL,
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code",
                    "daily": "temperature_2m_max,temperature_2m_min",
                    "temperature_unit": temp_unit,
                    "forecast_days": 1,
                    "timezone": "auto",
                }
            )
            forecast.raise_for_status()
            fdata = forecast.json()

        cur = fdata.get("current", {})
        daily = fdata.get("daily", {})
        temp = round(cur.get("temperature_2m", 0))
        feels = round(cur.get("apparent_temperature", temp))
        humidity = round(cur.get("relative_humidity_2m", 0))
        wmo = cur.get("weather_code", 0)
        desc = WMO_CODES.get(wmo, f"WMO {wmo}")
        highs = daily.get("temperature_2m_max", [temp])
        lows = daily.get("temperature_2m_min", [temp])
        high = round(highs[0]) if highs else temp
        low = round(lows[0]) if lows else temp

        return _build_matrix(rows, cols, city, country, temp, feels, high, low, humidity, desc, unit_sym)
    except Exception:
        return _error_matrix(rows, cols, "WEATHER UNAVAILABLE")


def _build_matrix(rows, cols, city, country, temp, feels, high, low, humidity, desc, unit_sym):
    place = f"{city}, {country}" if country else city
    lines = [
        f"{place}  {temp}°{unit_sym}",
        desc,
        f"H:{high}° L:{low}°  FEELS {feels}°",
        f"HUMIDITY: {humidity}%",
    ]
    content = lines[:rows]
    top = (rows - len(content)) // 2
    matrix = blank_matrix(rows, cols)
    for i, line in enumerate(content):
        matrix[top + i] = text_to_row(_center(line, cols), cols)
    return matrix


def _center(text: str, cols: int) -> str:
    pad = max(0, (cols - len(text)) // 2)
    return " " * pad + text


def _error_matrix(rows: int, cols: int, msg: str) -> list[list[int]]:
    matrix = blank_matrix(rows, cols)
    matrix[0] = text_to_row(_center(msg[:cols], cols), cols)
    return matrix
