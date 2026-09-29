import os

class Config:
    """Application configuration with environment variable support."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'harvest-risk-sim-secret-key-2026')
    DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')
    PORT = int(os.environ.get('PORT', 5000))
    HOST = os.environ.get('HOST', '0.0.0.0')

    # Market Price API Configuration
    # Agmarknet / e-NAM / Government Data API
    MARKET_API_URL = os.environ.get('MARKET_API_URL', 'https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070')
    MARKET_API_KEY = os.environ.get('MARKET_API_KEY', '')
    MARKET_TIMEOUT = float(os.environ.get('MARKET_TIMEOUT', 3.0))

    # Weather API Configuration (Default: Open-Meteo public non-commercial endpoint)
    WEATHER_API_URL = os.environ.get('WEATHER_API_URL', 'https://api.open-meteo.com/v1/forecast')
    WEATHER_TIMEOUT = float(os.environ.get('WEATHER_TIMEOUT', 3.0))

    # Cache TTLs (in seconds)
    CACHE_TTL_MARKET = int(os.environ.get('CACHE_TTL_MARKET', 3600))     # 1 hour
    CACHE_TTL_WEATHER = int(os.environ.get('CACHE_TTL_WEATHER', 1800))   # 30 minutes
