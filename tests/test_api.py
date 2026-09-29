"""
tests/test_api.py

API integration tests:
- GET /health
- POST /api/simulate (valid, invalid, missing weather, missing price, extreme inputs)
- GET /api/market-price
- GET /api/weather
"""

import unittest
from app import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health_endpoint(self):
        """Health check returns status ok and version."""
        res = self.client.get('/health')
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertEqual(data.get('status'), 'ok')
        self.assertIn('version', data)

    def test_simulate_valid(self):
        """Simulate endpoint returns 200 for valid input."""
        payload = {
            'crop': 'Tomato',
            'maturity': 80.0,
            'quantity': 1000.0,
            'current_price': 30.0,
            'future_price': 35.0,
            'temperature': 25.0,
            'humidity': 60.0,
            'rain_probability': 20.0,
            'storage_duration': 2.0,
            'transport_duration': 2.0,
            'storage_condition': 'Ambient'
        }
        res = self.client.post('/api/simulate', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertIn('recommendation', data)
        self.assertIn('optimal_horizon', data)
        self.assertEqual(len(data.get('markets', [])), 4)

    def test_simulate_invalid_negative(self):
        """Simulate endpoint rejects explicitly invalid negative inputs with 400."""
        payload = {
            'maturity': 80.0,
            'quantity': -500.0,
            'current_price': 30.0,
            'future_price': 35.0
        }
        res = self.client.post('/api/simulate', json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn('error', res.json)

    def test_simulate_missing_weather(self):
        """Missing weather fields are gracefully defaulted without crashing."""
        payload = {
            'crop': 'Tomato',
            'maturity': 75.0,
            'quantity': 1000.0,
            'current_price': 30.0,
            'future_price': 35.0
            # weather fields omitted
        }
        res = self.client.post('/api/simulate', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertTrue(data.get('is_fallback'))
        self.assertGreater(len(data.get('warnings', [])), 0)

    def test_simulate_missing_price(self):
        """Missing market price fields are gracefully defaulted."""
        payload = {
            'crop': 'Onion',
            'maturity': 60.0,
            'quantity': 800.0
            # prices omitted
        }
        res = self.client.post('/api/simulate', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertTrue(data.get('is_fallback'))

    def test_simulate_extreme_inputs(self):
        """Extreme temperature triggers critical warning and safe recommendation."""
        payload = {
            'crop': 'Tomato',
            'maturity': 96.0,
            'quantity': 1000.0,
            'current_price': 30.0,
            'future_price': 45.0,
            'temperature': 45.0,
            'humidity': 90.0,
            'rain_probability': 90.0,
            'storage_duration': 2.0,
            'transport_duration': 2.0
        }
        res = self.client.post('/api/simulate', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertEqual(data.get('recommended_day'), 0)
        warnings = " ".join(data.get('warnings', []))
        self.assertIn("Weather Alert", warnings)

    def test_market_price_api(self):
        """Market price endpoint returns commodity price and source."""
        res = self.client.get('/api/market-price?crop=Tomato')
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertIn('price', data)
        self.assertIn('source', data)
        self.assertIn(data['source'], ['live', 'cached', 'fallback'])

    def test_weather_api(self):
        """Weather endpoint returns temperature, humidity and source."""
        res = self.client.get('/api/weather?district=dindigul')
        self.assertEqual(res.status_code, 200)
        data = res.json
        self.assertIn('temperature', data)
        self.assertIn('humidity', data)
        self.assertIn('source', data)
        self.assertIn(data['source'], ['live', 'cached', 'fallback'])

if __name__ == '__main__':
    unittest.main()
