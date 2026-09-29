"""
tests/test_multiplot.py

Tests multi-plot and multi-crop farm simulation:
- Single plot evaluation
- Multi-plot portfolio evaluation
- Different crops
- Different maturity levels
- Portfolio aggregation (total quantity, value, spoilage)
"""

import unittest
from simulator.engine import simulate_farm_plots

class TestMultiPlot(unittest.TestCase):
    def test_single_plot(self):
        """Single plot farm evaluation."""
        plots = [
            {'id': 'p1', 'name': 'Plot 1', 'crop': 'Tomato', 'quantity': 1000.0, 'maturity': 70.0}
        ]
        res = simulate_farm_plots(plots)
        self.assertEqual(len(res['plots']), 1)
        self.assertEqual(res['summary']['total_plots'], 1)
        self.assertEqual(res['summary']['total_quantity_kg'], 1000.0)
        self.assertGreater(res['summary']['total_expected_value'], 0)

    def test_multiple_plots_different_crops(self):
        """Multi-plot farm with different crops and maturities."""
        plots = [
            {'id': 'p1', 'name': 'Plot 1', 'crop': 'Tomato', 'quantity': 1000.0, 'maturity': 70.0, 'current_price': 30.0, 'future_price': 35.0},
            {'id': 'p2', 'name': 'Plot 2', 'crop': 'Onion', 'quantity': 750.0, 'maturity': 45.0, 'current_price': 28.0, 'future_price': 32.0},
            {'id': 'p3', 'name': 'Plot 3', 'crop': 'Potato', 'quantity': 1200.0, 'maturity': 85.0, 'current_price': 22.0, 'future_price': 24.0}
        ]
        res = simulate_farm_plots(plots)
        self.assertEqual(len(res['plots']), 3)
        self.assertEqual(res['summary']['total_plots'], 3)
        self.assertEqual(res['summary']['total_quantity_kg'], 2950.0)
        
        # Verify each plot has independent recommendations
        p_res = res['plots']
        self.assertEqual(p_res[0]['crop'], 'Tomato')
        self.assertEqual(p_res[1]['crop'], 'Onion')
        self.assertEqual(p_res[2]['crop'], 'Potato')

        for p in p_res:
            self.assertIn(p['recommended_day'], list(range(11)))
            self.assertIn('recommended_market', p)
            self.assertGreater(p['expected_farmer_value'], 0)
            self.assertIn('spoilage_risk', p)

    def test_different_maturity_decisions(self):
        """Higher maturity crops should face higher spoilage pressure."""
        plots = [
            {'id': 'young', 'name': 'Young Crop', 'crop': 'Tomato', 'quantity': 1000.0, 'maturity': 40.0, 'temperature': 30.0},
            {'id': 'overripe', 'name': 'Overripe Crop', 'crop': 'Tomato', 'quantity': 1000.0, 'maturity': 98.0, 'temperature': 30.0}
        ]
        res = simulate_farm_plots(plots)
        young_plot = res['plots'][0]
        overripe_plot = res['plots'][1]

        # Overripe crop should have higher spoilage percentage than young crop
        self.assertGreater(overripe_plot['spoilage_pct'], young_plot['spoilage_pct'])

    def test_empty_plots_handling(self):
        """Empty plot list returns clean empty structure without crash."""
        res = simulate_farm_plots([])
        self.assertEqual(res['plots'], [])
        self.assertEqual(res['summary'], {})

if __name__ == '__main__':
    unittest.main()
