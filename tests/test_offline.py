"""
tests/test_offline.py

Tests offline functionality & resilience against network failures:
- Market API failure falls back gracefully
- Weather API failure falls back gracefully
- Complete simulation works without internet connectivity
"""

import unittest
from unittest.mock import patch
import requests
from simulator.market_service import get_market_price, COMMODITY_FALLBACKS, _MARKET_CACHE
from simulator.weather_service import get_live_weather, DISTRICT_PRESETS, _WEATHER_CACHE
from simulator.engine import run_simulation

class TestOfflineResilience(unittest.TestCase):
    def setUp(self):
        """Ensure clean cache before each offline test."""
        _WEATHER_CACHE.clear()
        _MARKET_CACHE.clear()

    @patch('requests.get', side_effect=requests.exceptions.ConnectionError("Network disconnected"))
    def test_market_api_offline_fallback(self, mock_get):
        """When market API is disconnected, fallback baseline is returned with source='fallback'."""
        result = get_market_price('Tomato')
        self.assertEqual(result['source'], 'fallback')
        self.assertFalse(result['is_live'])
        self.assertEqual(result['price'], COMMODITY_FALLBACKS['tomato']['price'])
        self.assertIn('mandi', result)

    @patch('requests.get', side_effect=requests.exceptions.Timeout("Weather service timeout"))
    def test_weather_api_offline_fallback(self, mock_get):
        """When weather API times out, regional preset is returned with source='fallback'."""
        result = get_live_weather(district='dindigul')
        self.assertEqual(result['source'], 'fallback')
        self.assertFalse(result['is_live'])
        self.assertEqual(result['temperature'], DISTRICT_PRESETS['dindigul']['temp'])
        self.assertEqual(result['humidity'], DISTRICT_PRESETS['dindigul']['humidity'])

    def test_full_simulation_offline_mode(self):
        """Simulator executes without any external calls when provided offline inputs."""
        inputs = {
            'crop': 'Potato',
            'maturity': 70.0,
            'quantity': 1200.0,
            'current_price': 22.0,
            'future_price': 26.0,
            'temperature': 24.0,
            'humidity': 55.0,
            'rain_probability': 10.0,
            'storage_duration': 3.0,
            'transport_duration': 2.0,
            'storage_condition': 'Ambient'
        }
        res = run_simulation(inputs)
        self.assertIn(res['recommended_day'], list(range(11)))
        self.assertGreater(res['proposed']['net_farmer_value'], 0)
        self.assertGreater(res['best_market']['expected_market_value'], 0)
        self.assertEqual(len(res['markets']), 4)

if __name__ == '__main__':
    unittest.main()
