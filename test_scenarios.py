import sys
sys.stdout.reconfigure(encoding='utf-8')
from simulator.engine import run_simulation
import json

sc1 = {'crop': 'Tomato', 'maturity': 80, 'quantity': 1000, 'current_price': 30, 'future_price': 32, 'temperature': 24, 'humidity': 55, 'rain_probability': 10, 'storage_duration': 2, 'transport_duration': 2, 'storage_condition': 'Ambient'}
sc2 = {'crop': 'Tomato', 'maturity': 95, 'quantity': 1000, 'current_price': 30, 'future_price': 38, 'temperature': 39, 'humidity': 85, 'rain_probability': 85, 'storage_duration': 5, 'transport_duration': 6, 'storage_condition': 'Ambient'}
sc3 = {'crop': 'Tomato', 'maturity': 65, 'quantity': 1000, 'current_price': 25, 'future_price': 42, 'temperature': 21, 'humidity': 45, 'rain_probability': 5, 'storage_duration': 2, 'transport_duration': 1.5, 'storage_condition': 'Cold Storage'}

for name, sc in [('SCENARIO 1 (NORMAL)', sc1), ('SCENARIO 2 (HIGH SPOILAGE RISK)', sc2), ('SCENARIO 3 (FUTURE PRICE OPPORTUNITY)', sc3)]:
    res = run_simulation(sc)
    rec = res['recommendation']
    base = res['baseline_comparison']
    mkt = res['best_market']
    print(f"=== {name} ===")
    print(f"Recommended Day: Day {rec['day']} ({rec['decision_en']})")
    print(f"Expected Spoilage: {rec['expected_spoilage']}% | Risk Level: {rec['risk_level']}")
    print(f"Expected Farmer Value: Rs {rec['expected_farmer_value']}")
    print(f"Baseline (Day 0) Value: Rs {base['baseline_farmer_value']} | Improvement: {base['pct_improvement']}%")
    print(f"Best Market: {mkt['name']} (Net: Rs {mkt['net_farmer_value']})")
    print(f"Flip Points Count: {len(res['sensitivity']['flip_points'])}")
    for fp in res['sensitivity']['flip_points'][:2]:
        print(f"  - {fp}")
    print("Explanations:")
    for exp in res['explanations'][:2]:
        print(f"  * {exp}")
    print()
