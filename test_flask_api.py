import sys
sys.stdout.reconfigure(encoding='utf-8')
from app import app
import json

client = app.test_client()

# 1. Test GET /
res_index = client.get('/')
assert res_index.status_code == 200, f'Expected 200, got {res_index.status_code}'
print('GET / passed (Status 200)')

# 2. Test POST /api/simulate (Normal)
sc1 = {'crop': 'Tomato', 'maturity': 80, 'quantity': 1000, 'current_price': 30, 'future_price': 32, 'temperature': 24, 'humidity': 55, 'rain_probability': 10, 'storage_duration': 2, 'transport_duration': 2, 'storage_condition': 'Ambient'}
res_sim = client.post('/api/simulate', json=sc1)
assert res_sim.status_code == 200, f'Expected 200, got {res_sim.status_code}'
sim_data = res_sim.get_json()
assert 'timeline' in sim_data and len(sim_data['timeline']) == 11, 'Timeline missing or not 11 days'
assert 'markets' in sim_data and len(sim_data['markets']) == 3, 'Markets missing or not 3'
assert 'baseline_comparison' in sim_data, 'Baseline comparison missing'
rec_en = sim_data["recommendation"]["decision_en"]
efv = sim_data["recommendation"]["expected_farmer_value"]
print(f'POST /api/simulate passed. Rec: {rec_en}, EFV: Rs {efv}')

# 3. Test GET /api/metrics
res_metrics = client.get('/api/metrics')
assert res_metrics.status_code == 200, f'Expected 200, got {res_metrics.status_code}'
m_data = res_metrics.get_json()
assert m_data['records_evaluated'] == 800, 'Expected 800 evaluated records'
print(f'GET /api/metrics passed. Win Rate: {m_data["win_rate_pct"]}%, Avg Improvement: Rs {m_data["average_value_improvement"]}')

# 4. Test Edge Case Missing Data (Fallback)
res_missing = client.post('/api/simulate', json={'crop': 'Tomato', 'current_price': None})
assert res_missing.status_code == 200, f'Expected 200, got {res_missing.status_code}'
miss_data = res_missing.get_json()
assert miss_data['fallback_used'] == True, 'Expected fallback_used == True'
print('Edge Case Missing Data passed. Fallback used:', miss_data['fallback_used'])
print('ALL FLASK ENDPOINT TESTS PASSED!')
