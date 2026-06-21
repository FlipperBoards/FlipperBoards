import httpx
from charmap import text_to_row, blank_matrix

BASE_URL = "https://api.openweathermap.org/data/2.5"


async def get_weather_matrix(rows: int, cols: int, api_key: str,
                              location: str, units: str = "imperial") -> list[list[int]]:
    if not api_key or not location:
        return _error_matrix(rows, cols, "WEATHER: NO API KEY/LOCATION")

    unit_sym = "F" if units == "imperial" else "C"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/weather",
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

        matrix = blank_matrix(rows, cols)
        loc_str = f"{city}, {country}  {temp}°{unit_sym}"
        matrix[0] = text_to_row(_center(loc_str, cols), cols)

        if rows > 1:
            matrix[1] = text_to_row(_center(desc, cols), cols)
        if rows > 2:
            detail = f"H:{high}° L:{low}°  FEELS {feels}°"
            matrix[2] = text_to_row(_center(detail, cols), cols)
        if rows > 3:
            hum_str = f"HUMIDITY: {humidity}%"
            matrix[3] = text_to_row(_center(hum_str, cols), cols)

        return matrix

    except Exception as e:
        return _error_matrix(rows, cols, f"WEATHER ERROR")


def _center(text: str, cols: int) -> str:
    pad = max(0, (cols - len(text)) // 2)
    return " " * pad + text


def _error_matrix(rows: int, cols: int, msg: str) -> list[list[int]]:
    matrix = blank_matrix(rows, cols)
    matrix[0] = text_to_row(_center(msg, cols), cols)
    return matrix
