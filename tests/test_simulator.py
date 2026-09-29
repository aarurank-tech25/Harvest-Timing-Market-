"""
tests/test_simulator.py

Unit tests for simulator core engine:
- Day 0 calculation
- Day 10 calculation
- Spoilage calculation & physical overrides
- Farmer value calculation
- Market channel calculations (4 channels)
"""

import unittest
from simulator.engine import SpoilageSimulator, simulate_horizon, simulate_market_options, run_simulation

class TestSimulatorEngine(unittest.TestCase):
    def setUp(self):
        self.sim = SpoilageSimulator()
        self.base_inputs = {
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

    def test_spoilage_bounds(self):
        """Spoilage percentage must always remain within [0.0, 100.0]."""
        # Normal
        s1 = self.sim.predict_spoilage_pct(70, 20, 50, 10, 1, 1, False)
        self.assertGreaterEqual(s1, 0.0)
        self.assertLessEqual(s1, 100.0)

        # Extreme thermal stress
        s2 = self.sim.predict_spoilage_pct(110, 48, 95, 95, 20, 24, True)
        self.assertEqual(s2, 100.0)

        # Favorable cold conditions
        s3 = self.sim.predict_spoilage_pct(40, 5, 30, 0, 0, 0, False)
        self.assertGreaterEqual(s3, 0.0)
        self.assertLessEqual(s3, 20.0)

    def test_day_0_calculation(self):
        """Test Day 0 horizon calculation."""
        res_d0 = simulate_horizon(self.base_inputs, 0, self.sim)
        self.assertEqual(res_d0['day'], 0)
        self.assertEqual(res_d0['maturity'], 80.0)
        self.assertEqual(res_d0['expected_price'], 30.0)
        self.assertGreater(res_d0['usable_qty'], 0)
        self.assertGreater(res_d0['net_farmer_value'], 0)
        self.assertEqual(res_d0['gross_revenue'], 1000.0 * 30.0)

    def test_day_10_calculation(self):
        """Test Day 10 horizon calculation."""
        res_d10 = simulate_horizon(self.base_inputs, 10, self.sim)
        self.assertEqual(res_d10['day'], 10)
        self.assertEqual(res_d10['maturity'], 80.0 + (10 * 2.5))
        self.assertGreater(res_d10['spoilage_pct'], 0)
        self.assertIn('net_farmer_value', res_d10)

    def test_farmer_value_accounting(self):
        """Verify strict accounting: Gross Revenue - Spoilage Loss = Net Revenue."""
        h = simulate_horizon(self.base_inputs, 0, self.sim)
        expected_net_rev = h['gross_revenue'] - h['spoilage_loss']
        self.assertAlmostEqual(h['net_revenue'], expected_net_rev, places=1)
        # Net Farmer Value = Net Revenue - Storage - Transport - Risk
        expected_farmer_val = h['net_revenue'] - h['storage_cost'] - h['transport_cost'] - h['risk_penalty']
        self.assertAlmostEqual(h['net_farmer_value'], expected_farmer_val, places=1)

    def test_market_channel_calculations(self):
        """Verify all 4 market channels are generated with full cost breakdowns."""
        markets = simulate_market_options(
            chosen_price=30.0,
            chosen_maturity=80.0,
            quantity=1000.0,
            temp=25.0,
            humidity=60.0,
            rain_prob=20.0,
            storage_duration=2.0,
            ambient_storage=True,
            sim=self.sim
        )
        self.assertEqual(len(markets), 4)
        market_ids = [m['id'] for m in markets]
        self.assertIn('local', market_ids)
        self.assertIn('wholesale', market_ids)
        self.assertIn('premium', market_ids)
        self.assertIn('farm_gate', market_ids)

        for m in markets:
            self.assertIn('gross_revenue', m)
            self.assertIn('spoilage_loss', m)
            self.assertIn('transport_cost', m)
            self.assertIn('storage_cost', m)
            self.assertIn('handling_cost', m)
            self.assertIn('commission', m)
            self.assertIn('expected_market_value', m)
            self.assertIn('reason', m)

        # Markets must be sorted descending by expected_market_value
        values = [m['expected_market_value'] for m in markets]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_run_simulation_completeness(self):
        """Verify complete simulation response object structure."""
        out = run_simulation(self.base_inputs)
        self.assertIn('recommendation', out)
        self.assertIn('recommendation_ta', out)
        self.assertIn('recommendation_hi', out)
        self.assertIn('recommended_day', out)
        self.assertIn('optimal_horizon', out)
        self.assertIn('baseline', out)
        self.assertIn('proposed', out)
        self.assertIn('best_market', out)
        self.assertEqual(len(out['markets']), 4)
        self.assertEqual(len(out['horizons']), 11)

if __name__ == '__main__':
    unittest.main()
