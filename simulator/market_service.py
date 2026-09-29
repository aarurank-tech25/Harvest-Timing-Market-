"""
simulator/market_service.py

Live Market Price Service with Agmarknet / e-NAM integration,
in-memory caching, validation, and reliable offline fallback.
"""

import time
import requests
from config import Config

# Realistic agricultural mandi baseline prices (INR / kg)
COMMODITY_FALLBACKS = {
    'tomato': {'price': 30.0, 'min_price': 18.0, 'max_price': 45.0, 'unit': '₹/kg', 'mandi': 'APMC Regional Hub'},
    'potato': {'price': 22.0, 'min_price': 15.0, 'max_price': 32.0, 'unit': '₹/kg', 'mandi': 'APMC Regional Hub'},
    'onion':  {'price': 28.0, 'min_price': 16.0, 'max_price': 48.0, 'unit': '₹/kg', 'mandi': 'APMC Regional Hub'},
    'rice':   {'price': 38.0, 'min_price': 28.0, 'max_price': 52.0, 'unit': '₹/kg', 'mandi': 'APMC Regional Hub'},
    'mango':  {'price': 55.0, 'min_price': 35.0, 'max_price': 90.0, 'unit': '₹/kg', 'mandi': 'APMC Regional Hub'},
}

# Cache store: {cache_key: {'data': dict, 'timestamp': float}}
_MARKET_CACHE = {}

def clear_market_cache():
    """Clear all entries in the in-memory market price cache."""
    _MARKET_CACHE.clear()

def get_market_price(crop: str, state: str = "Tamil Nadu", market: str = "All") -> dict:
    """
    Retrieves current market price for the specified commodity.
    Prioritizes:
      1. Live API (Agmarknet / e-NAM public endpoint)
      2. Valid unexpired cached data
      3. Offline fallback baseline
    
    Returns:
      dict with keys: commodity, price, unit, source ('live', 'cached', 'fallback'),
                      timestamp, mandi, min_price, max_price, is_live
    """
    crop_clean = (crop or 'Tomato').strip().lower()
    cache_key = f"{crop_clean}_{str(state or 'Tamil Nadu').lower()}_{str(market or 'All').lower()}"
    fallback_info = COMMODITY_FALLBACKS.get(crop_clean, COMMODITY_FALLBACKS['tomato'])

    # 1. Check if Live API is configured and attempt fetch
    # Data.gov.in requires API key; mock/proxy/custom endpoints may not
    has_credentials = bool(Config.MARKET_API_KEY) or ('api.data.gov.in' not in (Config.MARKET_API_URL or ''))
    if Config.MARKET_API_URL and has_credentials:
        try:
            params = {
                'format': 'json',
                'filters[commodity]': crop_clean.capitalize(),
                'limit': 5
            }
            if Config.MARKET_API_KEY:
                params['api-key'] = Config.MARKET_API_KEY
            if state and state != 'All':
                params['filters[state]'] = state

            response = requests.get(
                Config.MARKET_API_URL,
                params=params,
                timeout=Config.MARKET_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    records = data.get('records', [])
                    if isinstance(records, list) and len(records) > 0:
                        first_record = records[0]
                        if isinstance(first_record, dict):
                            raw_modal = float(first_record.get('modal_price', 0))
                            # Convert Quintal (100 kg) to kg if > 150
                            price_per_kg = (raw_modal / 100.0) if raw_modal > 150 else raw_modal
                            
                            # Validate price bounds
                            if 1.0 <= price_per_kg <= 500.0:
                                mandi_name = str(first_record.get('market', fallback_info['mandi']))
                                result = {
                                    'commodity': crop_clean.capitalize(),
                                    'price': round(price_per_kg, 2),
                                    'unit': '₹/kg',
                                    'source': 'live',
                                    'is_live': True,
                                    'mandi': mandi_name,
                                    'min_price': round(price_per_kg * 0.85, 2),
                                    'max_price': round(price_per_kg * 1.15, 2),
                                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                    'message': f"Live Agmarknet price fetched for {crop_clean.capitalize()} at {mandi_name}."
                                }
                                # Update cache
                                _MARKET_CACHE[cache_key] = {
                                    'data': result,
                                    'timestamp': time.time()
                                }
                                return result
        except Exception:
            # Network failure, timeout, or invalid format - proceed to cache or fallback
            pass

    # 2. Check Cache
    cached = _MARKET_CACHE.get(cache_key)
    if cached:
        age = time.time() - cached['timestamp']
        if age < Config.CACHE_TTL_MARKET:
            cached_data = dict(cached['data'])
            cached_data['source'] = 'cached'
            cached_data['is_live'] = False
            cached_data['message'] = f"Using cached price from {cached_data['timestamp']} ({int(age // 60)} min ago)."
            return cached_data

    # 3. Fallback to Agronomic Mandi Baseline
    return {
        'commodity': crop_clean.capitalize(),
        'price': fallback_info['price'],
        'unit': '₹/kg',
        'source': 'fallback',
        'is_live': False,
        'mandi': fallback_info['mandi'],
        'min_price': fallback_info['min_price'],
        'max_price': fallback_info['max_price'],
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'message': f"Offline fallback price applied for {crop_clean.capitalize()}."
    }
