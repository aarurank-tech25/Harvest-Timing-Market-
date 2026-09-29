"""
simulator/weather_service.py

Live Weather & Agro-meteorological Service supporting GPS, manual coordinates,
district presets, in-memory caching, validation, and offline fallback.
"""

import time
import requests
from config import Config

# Regional district defaults across major horticulture belts in India
DISTRICT_PRESETS = {
    'dindigul': {'name': 'Dindigul (Tamil Nadu)', 'lat': 10.3624, 'lon': 77.9695, 'temp': 28.0, 'humidity': 65.0, 'rain_prob': 20.0},
    'kolar':    {'name': 'Kolar (Karnataka)', 'lat': 13.1367, 'lon': 78.1291, 'temp': 26.0, 'humidity': 60.0, 'rain_prob': 15.0},
    'nashik':   {'name': 'Nashik (Maharashtra)', 'lat': 19.9975, 'lon': 73.7898, 'temp': 27.0, 'humidity': 55.0, 'rain_prob': 10.0},
    'pune':     {'name': 'Pune (Maharashtra)', 'lat': 18.5204, 'lon': 73.8567, 'temp': 26.0, 'humidity': 58.0, 'rain_prob': 15.0},
    'varanasi': {'name': 'Varanasi (Uttar Pradesh)', 'lat': 25.3176, 'lon': 82.9739, 'temp': 30.0, 'humidity': 62.0, 'rain_prob': 25.0},
    'guntur':   {'name': 'Guntur (Andhra Pradesh)', 'lat': 16.3067, 'lon': 80.4365, 'temp': 31.0, 'humidity': 70.0, 'rain_prob': 30.0},
}

# Cache store: {cache_key: {'data': dict, 'timestamp': float}}
_WEATHER_CACHE = {}

def clear_weather_cache():
    """Clear all entries in the in-memory weather cache."""
    _WEATHER_CACHE.clear()

def get_live_weather(lat: float = None, lon: float = None, district: str = None) -> dict:
    """
    Fetches real-time agro-weather data (temperature, relative humidity, rain probability).
    Supports GPS latitude/longitude or manual district selection.
    
    Returns:
      dict with: temperature, humidity, rain_probability, condition,
                 source ('live', 'cached', 'fallback'), is_live, location_name, timestamp
    """
    resolved_lat = None
    resolved_lon = None
    location_name = "Custom Location"

    # Match district preset if provided
    if district and str(district).strip().lower() in DISTRICT_PRESETS:
        preset = DISTRICT_PRESETS[str(district).strip().lower()]
        resolved_lat = preset['lat']
        resolved_lon = preset['lon']
        location_name = preset['name']
    elif lat is not None and lon is not None:
        try:
            f_lat = float(lat)
            f_lon = float(lon)
            if -90.0 <= f_lat <= 90.0 and -180.0 <= f_lon <= 180.0:
                resolved_lat = f_lat
                resolved_lon = f_lon
                location_name = f"GPS ({f_lat:.3f}, {f_lon:.3f})"
        except (ValueError, TypeError):
            pass

    # Default to Dindigul preset if no coordinates given or invalid
    if resolved_lat is None or resolved_lon is None:
        preset = DISTRICT_PRESETS['dindigul']
        resolved_lat = preset['lat']
        resolved_lon = preset['lon']
        location_name = preset['name']

    cache_key = f"{resolved_lat:.3f}_{resolved_lon:.3f}"

    # 1. Attempt Live Weather Fetch from Open-Meteo
    if Config.WEATHER_API_URL and resolved_lat is not None and resolved_lon is not None:
        try:
            params = {
                'latitude': round(resolved_lat, 4),
                'longitude': round(resolved_lon, 4),
                'current': 'temperature_2m,relative_humidity_2m,precipitation,weather_code',
                'hourly': 'precipitation_probability',
                'forecast_days': 1
            }
            res = requests.get(Config.WEATHER_API_URL, params=params, timeout=Config.WEATHER_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict):
                    current = data.get('current')
                    if isinstance(current, dict) and 'temperature_2m' in current and 'relative_humidity_2m' in current:
                        temp = float(current.get('temperature_2m', 25.0))
                        humidity = float(current.get('relative_humidity_2m', 60.0))
                        
                        # Plausible physical bounds check
                        if -30.0 <= temp <= 65.0 and 0.0 <= humidity <= 100.0:
                            # Extract rain probability (max in next 12 hrs or current precip)
                            hourly_rain = data.get('hourly', {}).get('precipitation_probability', [])
                            if isinstance(hourly_rain, list) and hourly_rain:
                                rain_prob = float(max(hourly_rain[:12]))
                            else:
                                precip = float(current.get('precipitation', 0.0))
                                rain_prob = min(100.0, max(0.0, precip * 20.0))
                            rain_prob = max(0.0, min(100.0, rain_prob))

                            # Weather condition text
                            code = int(current.get('weather_code', 0))
                            if code in [0, 1]:
                                condition = 'Sunny / Clear'
                            elif code in [2, 3]:
                                condition = 'Cloudy'
                            elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
                                condition = 'Rainy'
                            else:
                                condition = 'Humid / Muggy' if humidity > 70 else 'Cloudy'

                            result = {
                                'temperature': round(temp, 1),
                                'humidity': round(humidity, 1),
                                'rain_probability': round(rain_prob, 1),
                                'condition': condition,
                                'source': 'live',
                                'is_live': True,
                                'location_name': location_name,
                                'latitude': resolved_lat,
                                'longitude': resolved_lon,
                                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'message': f"Live weather fetched for {location_name}."
                            }

                            _WEATHER_CACHE[cache_key] = {
                                'data': result,
                                'timestamp': time.time()
                            }
                            return result
        except Exception:
            # Network issue, timeout, or unreachable endpoint - fallback to cache or preset
            pass

    # 2. Check Cache
    cached = _WEATHER_CACHE.get(cache_key)
    if cached:
        age = time.time() - cached['timestamp']
        if age < Config.CACHE_TTL_WEATHER:
            cached_data = dict(cached['data'])
            cached_data['source'] = 'cached'
            cached_data['is_live'] = False
            cached_data['message'] = f"Using cached weather from {cached_data['timestamp']} ({int(age // 60)} min ago)."
            return cached_data

    # 3. Fallback to Regional Preset
    fallback = DISTRICT_PRESETS.get(district.lower() if district else 'dindigul', DISTRICT_PRESETS['dindigul'])
    return {
        'temperature': fallback['temp'],
        'humidity': fallback['humidity'],
        'rain_probability': fallback['rain_prob'],
        'condition': 'Sunny / Clear' if fallback['rain_prob'] < 30 else 'Cloudy',
        'source': 'fallback',
        'is_live': False,
        'location_name': location_name,
        'latitude': resolved_lat,
        'longitude': resolved_lon,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'message': f"Offline fallback weather applied for {location_name}."
    }
