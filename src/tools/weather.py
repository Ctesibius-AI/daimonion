"""
Weather lookup via Open-Meteo API (free, no key needed).

Takes a city name, geocodes it, returns temperature and conditions.
"""

import httpx

from src.config import DEFAULT_CITY

GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'

# WMO weather codes -> human-readable conditions
WMO_CODES = {
    0: 'clear sky', 1: 'mainly clear', 2: 'partly cloudy', 3: 'overcast',
    45: 'foggy', 48: 'rime fog',
    51: 'light drizzle', 53: 'moderate drizzle', 55: 'dense drizzle',
    61: 'slight rain', 63: 'moderate rain', 65: 'heavy rain',
    71: 'slight snow', 73: 'moderate snow', 75: 'heavy snow',
    80: 'slight rain showers', 81: 'moderate rain showers', 82: 'violent rain showers',
    85: 'slight snow showers', 86: 'heavy snow showers',
    95: 'thunderstorm', 96: 'thunderstorm with slight hail', 99: 'thunderstorm with heavy hail',
}


def get_weather(city: str | None = None) -> str:
    """Get current weather + tomorrow's forecast for a city.

    Args:
        city: City name. Defaults to DEFAULT_CITY from config.

    Returns a conversational weather string.
    Raises ValueError if city not found.
    """
    if city is None:
        city = DEFAULT_CITY

    # Geocode city name
    geo_resp = httpx.get(GEOCODE_URL, params={'name': city, 'count': 1}, timeout=5)
    geo_resp.raise_for_status()
    geo_data = geo_resp.json()

    results = geo_data.get('results', [])
    if not results:
        raise ValueError(f'City not found: {city}')

    loc = results[0]
    lat = loc['latitude']
    lon = loc['longitude']
    city_name = loc.get('name', city)
    country = loc.get('country', '')

    # Fetch weather
    weather_resp = httpx.get(WEATHER_URL, params={
        'latitude': lat,
        'longitude': lon,
        'current': 'temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m',
        'daily': 'temperature_2m_max,temperature_2m_min,weather_code',
        'forecast_days': 2,
        'timezone': 'auto',
    }, timeout=5)
    weather_resp.raise_for_status()
    weather = weather_resp.json()

    # Current conditions
    current = weather.get('current', {})
    temp = current.get('temperature_2m', '?')
    code = current.get('weather_code', 0)
    wind = current.get('wind_speed_10m', '?')
    humidity = current.get('relative_humidity_2m', '?')
    conditions = WMO_CODES.get(code, 'unknown')

    # Tomorrow's forecast
    daily = weather.get('daily', {})
    tomorrow_max = daily.get('temperature_2m_max', [None, None])[1]
    tomorrow_min = daily.get('temperature_2m_min', [None, None])[1]
    tomorrow_code = daily.get('weather_code', [None, None])[1]
    tomorrow_conditions = WMO_CODES.get(tomorrow_code, 'unknown') if tomorrow_code is not None else '?'

    # Build conversational response
    parts = [f'{city_name}, {country}: {temp}\u00b0C right now, {conditions}.']
    parts.append(f'Wind {wind} km/h, humidity {humidity}%.')

    if tomorrow_max is not None:
        parts.append(f'Tomorrow: {tomorrow_min}\u2013{tomorrow_max}\u00b0C, {tomorrow_conditions}.')

    return ' '.join(parts)
