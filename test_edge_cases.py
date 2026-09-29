import sys
sys.stdout.reconfigure(encoding='utf-8')
from simulator.engine import run_simulation

print("--- EDGE CASE 1: Extreme heat + high spoilage risk + future price increase ---")
ec1 = {
    'crop': 'Tomato', 'maturity': 98, 'quantity': 1000,
    'current_price': 30, 'future_price': 60,
    'temperature': 45, 'humidity': 90, 'rain_probability': 90,
    'storage_duration': 4, 'transport_duration': 6, 'storage_condition': 'Ambient'
}
res1 = run_simulation(ec1)
print(f"Rec Day: {res1['recommendation']['day']} | Spoilage: {res1['recommendation']['expected_spoilage']}% | Risk: {res1['recommendation']['risk_level']}")
print(f"Net Value: Rs {res1['recommendation']['expected_farmer_value']} | Baseline: Rs {res1['baseline_comparison']['baseline_farmer_value']}")
print(f"Best Market: {res1['best_market']['name']}")

print("\n--- EDGE CASE 2: Very long storage/transport duration ---")
ec2 = {
    'crop': 'Tomato', 'maturity': 80, 'quantity': 1000,
    'current_price': 30, 'future_price': 35,
    'temperature': 25, 'humidity': 60, 'rain_probability': 20,
    'storage_duration': 14, 'transport_duration': 24, 'storage_condition': 'Ambient'
}
res2 = run_simulation(ec2)
print(f"Rec Day: {res2['recommendation']['day']} | Spoilage: {res2['recommendation']['expected_spoilage']}% | Storage Cost: Rs {res2['recommendation']['storage_cost']}")
print(f"Net Value: Rs {res2['recommendation']['expected_farmer_value']} | Best Market: {res2['best_market']['name']}")

print("\n--- EDGE CASE 3: Missing weather and price data (Fallback trigger) ---")
ec3 = {
    'crop': 'Tomato', 'maturity': 75, 'quantity': 1000,
    'current_price': None, 'future_price': None,
    'temperature': None, 'humidity': None, 'rain_probability': None
}
res3 = run_simulation(ec3)
print(f"Fallback Used: {res3['fallback_used']}")
print(f"Warnings: {res3['warnings']}")
print(f"Rec Day: {res3['recommendation']['day']} | Net Value: Rs {res3['recommendation']['expected_farmer_value']}")

print("\n--- EDGE CASE 4: Zero quantity, negative price, maturity > 100 ---")
ec4 = {
    'crop': 'Tomato', 'maturity': 115, 'quantity': 0,
    'current_price': -10, 'future_price': -20,
    'temperature': 25, 'humidity': 50, 'rain_probability': 10
}
res4 = run_simulation(ec4)
print(f"Handled safely without crash: Qty={res4['inputs']['quantity']}, Maturity={res4['inputs']['maturity']}, Price={res4['inputs']['current_price']}")
print(f"Warnings: {res4['warnings']}")
