import httpx
from charmap import text_to_row, blank_matrix

OWM_BASE = "https://api.openweathermap.org/data/2.5"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
METEO_URL = "https://api.open-meteo.com/v1/forecast"

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

    # Try OpenWeatherMap if key is provided
    if api_key:
        result = await _owm(rows, cols, api_key, location, units, unit_sym)
        if result:
            return result

    # Fallback: Open-Meteo (no API key required)
    return await _open_meteo(rows, cols, location, units, unit_sym)


async def _owm(rows, cols, api_key, location, units, unit_sym):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{OWM_BASE}/weather",
                params={"q": location, "appid": api_key, "units": units}
            )
            resp.raise_for_status()
            data = resp.json()

        city = data.get("name", location).upper()
        country = data.get("sys", {}).get("country", "").upper()
        temp = round(data.get("main", {}).get("temp", 0))
        feels = round(data.get("main", {}).get("feels_like", 0))
        high = round(data.get("main", {}).get("temp_max", 0))
        low = round(data.get("main", {}).get("temp_min", 0))
        humidity = data.get("main", {}).get("humidity", 0)
        desc = data.get("weather", [{}])[0].get("description", "").upper()

        return _build_matrix(rows, cols, city, country, temp, feels, high, low, humidity, desc, unit_sym)
    except Exception:
        return None


async def _open_meteo(rows, cols, location, units, unit_sym):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Geocode the location name
            geo_resp = await client.get(
                GEOCODING_URL,
                params={"name": location, "count": 1, "language": "en"}
            )
            geo_resp.raise_for_status()
            geo = geo_resp.json()

            results = geo.get("results", [])
            if not results:
                return _error_matrix(rows, cols, f"LOCATION NOT FOUND: {location.upper()}")

            place = results[0]
            lat = place["latitude"]
            lon = place["longitude"]
            city = place.get("name", location).upper()
            country = place.get("country_code", "").upper()

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
    lines = [
        f"{city}, {country}  {temp}°{unit_sym}",
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
