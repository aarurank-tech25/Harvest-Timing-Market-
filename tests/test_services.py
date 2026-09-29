"""
tests/test_services.py

Comprehensive tests for Live Market Price & Live Weather Services:
- Market Price Service:
  - live success
  - timeout handling
  - connection failure handling
  - invalid response handling (status_code != 200, malformed JSON, empty records, out-of-bounds price)
  - cache retrieval on subsequent network failure
  - fallback commodity price
- Weather Service:
  - live success
  - timeout handling
  - connection failure handling
  - invalid response handling (status_code != 200, corrupt JSON, extreme temperature bounds)
  - cache retrieval on subsequent network failure
  - fallback regional/district preset
- Location Flow:
  - valid coordinates resolution
  - unavailable GPS (None / empty / exception) fallback to district preset
  - manual district selection fallback
"""

import unittest
from unittest.mock import patch, MagicMock
import requests
from config import Config
from simulator.market_service import (
    get_market_price,
    clear_market_cache,
    COMMODITY_FALLBACKS,
    _MARKET_CACHE
)
from simulator.weather_service import (
    get_live_weather,
    clear_weather_cache,
    DISTRICT_PRESETS,
    _WEATHER_CACHE
)


class TestMarketService(unittest.TestCase):
    def setUp(self):
        clear_market_cache()
        self.orig_api_key = Config.MARKET_API_KEY
        Config.MARKET_API_KEY = 'test-api-key-2026'

    def tearDown(self):
        clear_market_cache()
        Config.MARKET_API_KEY = self.orig_api_key

    @patch('requests.get')
    def test_live_success(self, mock_get):
        """Live API returns 200 and records; price parsed and source is 'live'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'records': [
                {'commodity': 'Tomato', 'modal_price': '3200', 'market': 'Ottanchatram Mandi'}
            ]
        }
        mock_get.return_value = mock_resp

        result = get_market_price('Tomato', state='Tamil Nadu')
        self.assertEqual(result['source'], 'live')
        self.assertTrue(result['is_live'])
        self.assertEqual(result['price'], 32.0)  # 3200 / 100 kg = 32.0/kg
        self.assertEqual(result['mandi'], 'Ottanchatram Mandi')

    @patch('requests.get', side_effect=requests.exceptions.Timeout("Connection timed out"))
    def test_timeout(self, mock_get):
        """API timeout falls back to baseline with source='fallback'."""
        result = get_market_price('Tomato')
        self.assertEqual(result['source'], 'fallback')
        self.assertFalse(result['is_live'])
        self.assertEqual(result['price'], COMMODITY_FALLBACKS['tomato']['price'])

    @patch('requests.get', side_effect=requests.exceptions.ConnectionError("DNS failure"))
    def test_connection_failure(self, mock_get):
        """Connection failure falls back gracefully."""
        result = get_market_price('Potato')
        self.assertEqual(result['source'], 'fallback')
        self.assertFalse(result['is_live'])
        self.assertEqual(result['price'], COMMODITY_FALLBACKS['potato']['price'])

    @patch('requests.get')
    def test_invalid_response_non_200(self, mock_get):
        """HTTP error response (e.g. 500) triggers fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_get.return_value = mock_resp

        result = get_market_price('Onion')
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(result['price'], COMMODITY_FALLBACKS['onion']['price'])

    @patch('requests.get')
    def test_invalid_response_malformed_json(self, mock_get):
        """Malformed JSON triggers fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Invalid JSON string")
        mock_get.return_value = mock_resp

        result = get_market_price('Rice')
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(result['price'], COMMODITY_FALLBACKS['rice']['price'])

    @patch('requests.get')
    def test_invalid_response_empty_records(self, mock_get):
        """Empty records list triggers fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'records': []}
        mock_get.return_value = mock_resp

        result = get_market_price('Tomato')
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(result['price'], COMMODITY_FALLBACKS['tomato']['price'])

    @patch('requests.get')
    def test_invalid_response_out_of_bounds_price(self, mock_get):
        """Unrealistic or negative price triggers fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'records': [{'commodity': 'Tomato', 'modal_price': '-500', 'market': 'Test Mandi'}]
        }
        mock_get.return_value = mock_resp

        result = get_market_price('Tomato')
        self.assertEqual(result['source'], 'fallback')

    @patch('requests.get')
    def test_cache_hit_on_subsequent_failure(self, mock_get):
        """Subsequent request uses cached live price when network fails."""
        # 1. First call succeeds
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'records': [{'commodity': 'Tomato', 'modal_price': '3500', 'market': 'Hub Mandi'}]
        }
        mock_get.return_value = mock_resp

        res1 = get_market_price('Tomato', state='Tamil Nadu')
        self.assertEqual(res1['source'], 'live')
        self.assertEqual(res1['price'], 35.0)

        # 2. Second call fails with network error
        mock_get.side_effect = requests.exceptions.Timeout("Timeout on second fetch")
        res2 = get_market_price('Tomato', state='Tamil Nadu')
        self.assertEqual(res2['source'], 'cached')
        self.assertFalse(res2['is_live'])
        self.assertEqual(res2['price'], 35.0)
        self.assertIn('cached', res2['message'].lower())

    def test_fallback_unrecognized_crop(self):
        """Unrecognized crop safely defaults to base fallback without crashing."""
        result = get_market_price('ExoticCrop')
        self.assertEqual(result['source'], 'fallback')
        self.assertFalse(result['is_live'])
        self.assertGreater(result['price'], 0)


class TestWeatherService(unittest.TestCase):
    def setUp(self):
        clear_weather_cache()

    def tearDown(self):
        clear_weather_cache()

    @patch('requests.get')
    def test_live_success(self, mock_get):
        """Live Open-Meteo API returns valid weather data."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'current': {
                'temperature_2m': 27.4,
                'relative_humidity_2m': 62.0,
                'precipitation': 0.0,
                'weather_code': 1
            },
            'hourly': {
                'precipitation_probability': [10, 15, 10, 5]
            }
        }
        mock_get.return_value = mock_resp

        result = get_live_weather(lat=10.362, lon=77.970)
        self.assertEqual(result['source'], 'live')
        self.assertTrue(result['is_live'])
        self.assertEqual(result['temperature'], 27.4)
        self.assertEqual(result['humidity'], 62.0)
        self.assertEqual(result['rain_probability'], 15.0)
        self.assertEqual(result['condition'], 'Sunny / Clear')

    @patch('requests.get', side_effect=requests.exceptions.Timeout("Weather timeout"))
    def test_timeout(self, mock_get):
        """Weather timeout triggers regional preset fallback."""
        result = get_live_weather(district='kolar')
        self.assertEqual(result['source'], 'fallback')
        self.assertFalse(result['is_live'])
        self.assertEqual(result['temperature'], DISTRICT_PRESETS['kolar']['temp'])
        self.assertEqual(result['humidity'], DISTRICT_PRESETS['kolar']['humidity'])

    @patch('requests.get', side_effect=requests.exceptions.ConnectionError("Weather service down"))
    def test_connection_failure(self, mock_get):
        """Connection failure triggers fallback."""
        result = get_live_weather(district='pune')
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(result['temperature'], DISTRICT_PRESETS['pune']['temp'])

    @patch('requests.get')
    def test_invalid_response_non_200(self, mock_get):
        """HTTP error from Open-Meteo triggers fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"
        mock_get.return_value = mock_resp

        result = get_live_weather(district='nashik')
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(result['temperature'], DISTRICT_PRESETS['nashik']['temp'])

    @patch('requests.get')
    def test_invalid_response_corrupt_data(self, mock_get):
        """Corrupt or missing fields in API response triggers fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': 'error', 'message': 'corrupted payload'}
        mock_get.return_value = mock_resp

        result = get_live_weather(district='varanasi')
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(result['temperature'], DISTRICT_PRESETS['varanasi']['temp'])

    @patch('requests.get')
    def test_invalid_response_extreme_temperature(self, mock_get):
        """Unphysical temperature value (e.g. 150°C) triggers fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'current': {'temperature_2m': 150.0, 'relative_humidity_2m': 50.0}
        }
        mock_get.return_value = mock_resp

        result = get_live_weather(district='guntur')
        self.assertEqual(result['source'], 'fallback')
        self.assertEqual(result['temperature'], DISTRICT_PRESETS['guntur']['temp'])

    @patch('requests.get')
    def test_cache_hit_on_subsequent_failure(self, mock_get):
        """Cached weather is served if live fetch fails afterwards."""
        # 1. First call succeeds
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'current': {'temperature_2m': 29.5, 'relative_humidity_2m': 58.0, 'weather_code': 0},
            'hourly': {'precipitation_probability': [5]}
        }
        mock_get.return_value = mock_resp

        res1 = get_live_weather(lat=10.362, lon=77.970)
        self.assertEqual(res1['source'], 'live')
        self.assertEqual(res1['temperature'], 29.5)

        # 2. Second call fails
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")
        res2 = get_live_weather(lat=10.362, lon=77.970)
        self.assertEqual(res2['source'], 'cached')
        self.assertFalse(res2['is_live'])
        self.assertEqual(res2['temperature'], 29.5)
        self.assertIn('cached', res2['message'].lower())

    def test_fallback_regional_preset(self):
        """Offline regional preset is returned directly when no live fetch is made."""
        clear_weather_cache()
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError("Offline")):
            res = get_live_weather(district='dindigul')
            self.assertEqual(res['source'], 'fallback')
            self.assertEqual(res['temperature'], DISTRICT_PRESETS['dindigul']['temp'])
            self.assertEqual(res['humidity'], DISTRICT_PRESETS['dindigul']['humidity'])


class TestLocationFlow(unittest.TestCase):
    def setUp(self):
        clear_weather_cache()

    def tearDown(self):
        clear_weather_cache()

    @patch('requests.get')
    def test_valid_coordinates(self, mock_get):
        """Valid GPS coordinates resolve and format location name."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'current': {'temperature_2m': 24.0, 'relative_humidity_2m': 55.0, 'weather_code': 0},
            'hourly': {'precipitation_probability': [0]}
        }
        mock_get.return_value = mock_resp

        result = get_live_weather(lat=13.1367, lon=78.1291)
        self.assertIn('13.137', result['location_name'])
        self.assertEqual(result['latitude'], 13.1367)
        self.assertEqual(result['longitude'], 78.1291)

    def test_unavailable_gps(self):
        """When GPS coordinates are None, defaults safely to Dindigul preset."""
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError("Offline")):
            result = get_live_weather(lat=None, lon=None, district=None)
            self.assertEqual(result['source'], 'fallback')
            self.assertEqual(result['location_name'], DISTRICT_PRESETS['dindigul']['name'])

    def test_invalid_gps_coordinates(self):
        """Out of bounds or invalid GPS coordinates safely fall back without exception."""
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError("Offline")):
            result = get_live_weather(lat=999.0, lon=-500.0, district=None)
            self.assertEqual(result['source'], 'fallback')
            self.assertEqual(result['location_name'], DISTRICT_PRESETS['dindigul']['name'])

    def test_manual_district_fallback(self):
        """Manual district selection overrides coordinates when provided."""
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError("Offline")):
            result = get_live_weather(lat=None, lon=None, district='kolar')
            self.assertEqual(result['location_name'], DISTRICT_PRESETS['kolar']['name'])
            self.assertEqual(result['temperature'], DISTRICT_PRESETS['kolar']['temp'])


if __name__ == '__main__':
    unittest.main()
