"""
simulator/engine.py

Comprehensive Risk-Aware Harvest Timing & Market Option Simulator.
Implements:
  - Spoilage risk ML / empirical scoring
  - Usable quantity and transparent net farmer value accounting
  - Harvest Horizon Simulator (Day 0 to Day 10)
  - Independent Price-Only Baseline comparison
  - Configurable 4-Tier Market Option Simulator (Local, Regional Wholesale, Direct Premium, Farm-Gate)
  - Explicit cost breakdown: Gross Rev, Spoilage Loss, Transport, Storage, Handling, Commission
  - Multi-scenario future price analysis (Low, Base, High)
  - Full Sensitivity Analysis across 5 key parameters
  - Edge-case guarding and fallback logic
  - Multilingual (English + Tamil + Hindi) explanation layer with uncertainty categorization
  - Multi-plot and multi-crop farm simulation
"""

import os
import joblib
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'spoilage_model.joblib')

# Storage and transport rates (in INR / kg)
AMBIENT_STORAGE_RATE = 0.50   # Rs / kg / day
COLD_STORAGE_RATE = 1.50      # Rs / kg / day
BASE_TRANSPORT_RATE = 0.80    # Rs / kg / hour of transit

class SpoilageSimulator:
    """
    Predicts post-harvest perishable crop spoilage percentage using trained
    coefficients with empirical non-linear physical overrides.
    """
    def __init__(self):
        # Default fallback coefficients (derived from synthetic dataset)
        self.coef = {
            'maturity': 0.1594,
            'temperature': 0.4834,
            'humidity': 0.1073,
            'rain_probability': 0.0525,
            'storage_duration': 1.1749,
            'transport_duration': 0.2718,
            'ambient_storage': 20.0726,
            'intercept': -34.6903
        }
        self.model_loaded = False
        self.load_model()

    def load_model(self):
        if os.path.exists(MODEL_PATH):
            try:
                model_data = joblib.load(MODEL_PATH)
                features = model_data.get('features', [])
                coefs = model_data.get('coef', [])
                for feat, c in zip(features, coefs):
                    self.coef[feat] = float(c)
                self.coef['intercept'] = float(model_data.get('intercept', self.coef['intercept']))
                self.model_loaded = True
            except Exception:
                self.model_loaded = False

    def predict_spoilage_pct(self, maturity, temp, humidity, rain_prob, storage_days, transport_hours, ambient_storage):
        """
        Calculates bounded spoilage percentage based on physical factors.
        """
        mat = max(0.0, float(maturity))
        t = float(temp)
        hum = max(0.0, min(100.0, float(humidity)))
        rain = max(0.0, min(100.0, float(rain_prob)))
        stor = max(0.0, float(storage_days))
        trans = max(0.0, float(transport_hours))
        amb = 1.0 if ambient_storage else 0.0

        # Linear model core
        score = (
            self.coef['intercept'] +
            self.coef['maturity'] * mat +
            self.coef['temperature'] * t +
            self.coef['humidity'] * hum +
            self.coef['rain_probability'] * rain +
            self.coef['storage_duration'] * stor +
            self.coef['transport_duration'] * trans +
            self.coef['ambient_storage'] * amb
        )

        # Physical safety overrides for extreme boundary conditions
        overrides = 0.0
        # 1. Overmaturity penalty
        if mat >= 100.0:
            overrides += 15.0
        elif mat >= 95.0:
            overrides += 7.5

        # 2. Extreme heat + moisture
        if t > 40.0 and hum > 75.0:
            overrides += 20.0
        elif t > 38.0:
            overrides += 8.0

        # 3. High rain moisture
        if rain > 85.0:
            overrides += 10.0

        # 4. Long transport stress
        if trans > 16.0:
            overrides += 12.0

        # 5. Extended storage in ambient condition
        if amb == 1.0 and stor > 7.0:
            overrides += 15.0

        total_spoilage = score + overrides
        return float(np.clip(total_spoilage, 0.0, 100.0))

    @staticmethod
    def get_risk_level(spoilage_pct: float) -> str:
        if spoilage_pct < 10.0:
            return 'Low Risk'
        elif spoilage_pct <= 22.0:
            return 'Medium Risk'
        else:
            return 'High Risk'

    @staticmethod
    def get_risk_level_ta(risk_level: str) -> str:
        mapping = {
            'Low Risk': 'குறைந்த அபாயம்',
            'Medium Risk': 'நடுத்தர அபாயம்',
            'High Risk': 'அதிக அபாயம்'
        }
        return mapping.get(risk_level, risk_level)

    @staticmethod
    def get_risk_level_hi(risk_level: str) -> str:
        mapping = {
            'Low Risk': 'कम जोखिम',
            'Medium Risk': 'मध्यम जोखिम',
            'High Risk': 'उच्च जोखिम'
        }
        return mapping.get(risk_level, risk_level)


def simulate_horizon(inputs: dict, horizon_days: int, sim: SpoilageSimulator) -> dict:
    """
    Evaluates farmer net value for a specific harvest day d (0 to 10).
    """
    base_maturity = float(inputs.get('maturity', 80.0))
    quantity = max(0.0, float(inputs.get('quantity', 1000.0)))
    current_price = max(0.0, float(inputs.get('current_price', 30.0)))
    future_price = max(0.0, float(inputs.get('future_price', 35.0)))
    temp = float(inputs.get('temperature', 25.0))
    humidity = float(inputs.get('humidity', 60.0))
    rain_prob = float(inputs.get('rain_probability', 20.0))
    storage_duration = max(0.0, float(inputs.get('storage_duration', 2.0)))
    transport_duration = max(0.0, float(inputs.get('transport_duration', 2.0)))
    storage_condition = inputs.get('storage_condition', 'Ambient')
    ambient_storage = (storage_condition == 'Ambient')

    storage_rate = AMBIENT_STORAGE_RATE if ambient_storage else COLD_STORAGE_RATE
    transport_rate = BASE_TRANSPORT_RATE

    # Target duration over which future_price is expected
    target_wait_days = max(1.0, float(inputs.get('target_wait_days', storage_duration if storage_duration > 0 else 5.0)))

    # On-field maturity progression (+2.5% per day standing on the plant)
    maturity_d = min(110.0, base_maturity + (horizon_days * 2.5))

    # Expected market price trajectory
    if target_wait_days > 0:
        price_progression = min(1.0, horizon_days / target_wait_days)
    else:
        price_progression = 1.0 if horizon_days > 0 else 0.0
    price_d = current_price + (future_price - current_price) * price_progression

    # Spoilage post-harvest
    spoilage_pct = sim.predict_spoilage_pct(
        maturity_d, temp, humidity, rain_prob, storage_duration, transport_duration, ambient_storage
    )
    risk_level = sim.get_risk_level(spoilage_pct)

    usable_qty = quantity * (1.0 - (spoilage_pct / 100.0))
    gross_revenue = quantity * price_d
    spoilage_loss = quantity * (spoilage_pct / 100.0) * price_d
    net_revenue = usable_qty * price_d

    # Storage cost applies post-harvest
    storage_cost = quantity * storage_duration * storage_rate
    # Transport cost
    transport_cost = quantity * transport_duration * transport_rate

    # Field holding risk penalty (weather exposure risk while waiting on field)
    field_risk_penalty = 0.0
    if horizon_days > 0:
        # Extra risk of field damage under extreme rain or heat
        field_risk_penalty = quantity * (horizon_days * 0.15) * (1.0 + (rain_prob / 100.0) + max(0.0, temp - 30.0) / 20.0)
        # Severe biological rot penalty under heatwave + humidity + high maturity
        if temp > 40.0 and humidity > 75.0 and base_maturity >= 90.0:
            field_risk_penalty += quantity * price_d * (0.30 * horizon_days)

    net_farmer_value = net_revenue - storage_cost - transport_cost - field_risk_penalty

    return {
        'day': horizon_days,
        'maturity': round(maturity_d, 1),
        'expected_price': round(price_d, 2),
        'spoilage_pct': round(spoilage_pct, 2),
        'usable_qty': round(usable_qty, 1),
        'gross_revenue': round(gross_revenue, 2),
        'spoilage_loss': round(spoilage_loss, 2),
        'net_revenue': round(net_revenue, 2),
        'storage_cost': round(storage_cost, 2),
        'transport_cost': round(transport_cost, 2),
        'risk_penalty': round(field_risk_penalty, 2),
        'net_farmer_value': round(net_farmer_value, 2),
        'risk_level': risk_level,
        'risk_level_ta': sim.get_risk_level_ta(risk_level),
        'risk_level_hi': sim.get_risk_level_hi(risk_level)
    }


def simulate_market_options(chosen_price: float, chosen_maturity: float, quantity: float,
                            temp: float, humidity: float, rain_prob: float,
                            storage_duration: float, ambient_storage: bool, sim: SpoilageSimulator) -> list:
    """
    Evaluates 4 distinct market channels with transparent full accounting:
      1. Local Mandi (Village Market)
      2. Regional Wholesale APMC Hub
      3. Direct Retail / Premium Buyer
      4. Farm-Gate / Distress Sale

    Calculates for each channel:
      Gross Revenue - Spoilage Loss - Transport Cost - Storage Cost - Handling Cost - Commission
      = Expected Farmer Value
    """
    markets_config = [
        {
            'id': 'local',
            'name': 'Local Mandi (Village Market)',
            'name_ta': 'உள்ளூர் சந்தை (கிராம மண்டி)',
            'name_hi': 'स्थानीय मंडी (ग्रामीण बाजार)',
            'price_multiplier': 0.85,
            'transport_hours': 1.0,
            'storage_rate_adj': 0.8,
            'handling_rate': 0.15,
            'commission_rate': 0.01,
            'risk_penalty_pct': 0.02,
            'distance_km': 12,
            'description': 'Short transport distance, quick cash settlement, lower price realization.',
            'description_ta': 'குறைந்த போக்குவரத்து தூரம், உடனடி பணம், குறைந்த விலை.',
            'description_hi': 'कम परिवहन दूरी, त्वरित नकद भुगतान, कम मूल्य प्राप्ति।'
        },
        {
            'id': 'wholesale',
            'name': 'Regional Wholesale APMC Hub',
            'name_ta': 'பிராந்திய மொத்த விற்பனை APMC மையம்',
            'name_hi': 'क्षेत्रीय थोक APMC मंडी',
            'price_multiplier': 1.00,
            'transport_hours': 3.5,
            'storage_rate_adj': 1.0,
            'handling_rate': 0.25,
            'commission_rate': 0.02,
            'risk_penalty_pct': 0.05,
            'distance_km': 55,
            'description': 'Standard regional mandi, benchmark transparent price, standard transit.',
            'description_ta': 'நிலையான பிராந்திய மண்டி, வழக்கமான போக்குவரத்து, நிலையான விலை.',
            'description_hi': 'मानक क्षेत्रीय मंडी, मानक परिवहन, बेंचमार्क मूल्य।'
        },
        {
            'id': 'premium',
            'name': 'Direct Retail / Premium Buyer',
            'name_ta': 'நேரடி சில்லறை / பிரீமியம் வாங்குபவர்',
            'name_hi': 'प्रत्यक्ष खुदरा / प्रीमियम खरीदार',
            'price_multiplier': 1.25,
            'transport_hours': 7.0,
            'storage_rate_adj': 1.5,
            'handling_rate': 0.45,
            'commission_rate': 0.00,
            'risk_penalty_pct': 0.10,
            'distance_km': 140,
            'description': 'Highest price, longer logistics, strict quality grading rejection risk.',
            'description_ta': 'அதிக விலை, நீண்ட போக்குவரத்து, தர நிராகரிப்பு அபாயம்.',
            'description_hi': 'उच्चतम मूल्य, लंबी रसद, सख्त गुणवत्ता अस्वीकृति जोखिम।'
        },
        {
            'id': 'farm_gate',
            'name': 'Farm-Gate / Distress Sale',
            'name_ta': 'பண்ணை வாசல் / அவசர விற்பனை',
            'name_hi': 'खेत पर बिक्री / संकटकालीन सौदा',
            'price_multiplier': 0.70,
            'transport_hours': 0.0,
            'storage_rate_adj': 0.0,
            'handling_rate': 0.05,
            'commission_rate': 0.00,
            'risk_penalty_pct': 0.00,
            'distance_km': 0,
            'description': 'Zero transport and zero storage overhead, buyer collects directly at field, lowest price.',
            'description_ta': 'பூஜ்ஜிய போக்குவரத்து மற்றும் சேமிப்பு செலவு, வாங்குபவர் வயலிலேயே எடுக்கிறார், குறைந்த விலை.',
            'description_hi': 'शून्य परिवहन और शून्य भंडारण लागत, खरीदार खेत से लेता है, न्यूनतम मूल्य।'
        }
    ]

    base_storage_rate = AMBIENT_STORAGE_RATE if ambient_storage else COLD_STORAGE_RATE
    results = []

    for m in markets_config:
        m_price = round(chosen_price * m['price_multiplier'], 2)
        m_trans_hrs = m['transport_hours']
        m_spoilage_pct = sim.predict_spoilage_pct(
            chosen_maturity, temp, humidity, rain_prob, storage_duration, m_trans_hrs, ambient_storage
        )
        usable_qty = quantity * (1.0 - (m_spoilage_pct / 100.0))
        gross_rev = quantity * m_price
        spoilage_loss = quantity * (m_spoilage_pct / 100.0) * m_price
        net_rev = usable_qty * m_price
        trans_cost = quantity * m_trans_hrs * BASE_TRANSPORT_RATE
        store_cost = quantity * storage_duration * (base_storage_rate * m['storage_rate_adj'])
        handling_cost = quantity * m['handling_rate']
        commission_cost = gross_rev * m['commission_rate']
        risk_penalty = net_rev * m['risk_penalty_pct']

        expected_market_value = gross_rev - spoilage_loss - trans_cost - store_cost - handling_cost - commission_cost - risk_penalty

        reason_text = (
            f"Expected price: ₹{m_price:.2f}/kg | Expected spoilage: {m_spoilage_pct:.1f}% | "
            f"Transport: ₹{trans_cost:,.0f} | Storage: ₹{store_cost:,.0f} | "
            f"Handling: ₹{handling_cost:,.0f} | Commission: ₹{commission_cost:,.0f} | "
            f"Expected farmer value: ₹{expected_market_value:,.2f}"
        )

        results.append({
            'id': m['id'],
            'name': m['name'],
            'name_ta': m['name_ta'],
            'name_hi': m['name_hi'],
            'price': m_price,
            'distance_km': m['distance_km'],
            'transport_hours': m_trans_hrs,
            'spoilage_pct': round(m_spoilage_pct, 2),
            'usable_qty': round(usable_qty, 1),
            'gross_revenue': round(gross_rev, 2),
            'revenue': round(net_rev, 2),
            'spoilage_loss': round(spoilage_loss, 2),
            'transport_cost': round(trans_cost, 2),
            'storage_cost': round(store_cost, 2),
            'handling_cost': round(handling_cost, 2),
            'commission': round(commission_cost, 2),
            'risk_penalty': round(risk_penalty, 2),
            'expected_market_value': round(expected_market_value, 2),
            'risk_level': sim.get_risk_level(m_spoilage_pct),
            'risk_level_ta': sim.get_risk_level_ta(sim.get_risk_level(m_spoilage_pct)),
            'risk_level_hi': sim.get_risk_level_hi(sim.get_risk_level(m_spoilage_pct)),
            'description': m['description'],
            'description_ta': m.get('description_ta', m['description']),
            'description_hi': m.get('description_hi', m['description']),
            'reason': reason_text
        })

    # Sort transparently by expected farmer value descending
    results.sort(key=lambda x: x['expected_market_value'], reverse=True)
    return results


def run_sensitivity_analysis(inputs: dict, base_optimal_day: int, sim: SpoilageSimulator) -> dict:
    """
    Executes one-at-a-time sensitivity sweeps across 7 critical parameters:
      1. Future price (-20%, -10%, base, +10%, +20%)
      2. Temperature (20°C, 28°C, 35°C, 42°C)
      3. Humidity (40%, 60%, 75%, 90%)
      4. Rain probability (0%, 25%, 50%, 85%)
      5. Storage duration (1, 3, 5, 8 days)
      6. Transport duration (1, 4, 8, 16 hours)
      7. Maturity (40%, 65%, 80%, 98%)
    """
    sweeps = []
    decision_changing_vars = set()

    # 1. Future price variations
    base_future = float(inputs.get('future_price', 35.0))
    for pct in [-20, -10, 0, 10, 20]:
        mod_inputs = dict(inputs)
        mod_inputs['future_price'] = max(1.0, base_future * (1.0 + pct / 100.0))
        best_d = 0
        best_val = -1e9
        best_spoil = 0
        for d in range(11):
            h = simulate_horizon(mod_inputs, d, sim)
            if h['net_farmer_value'] > best_val:
                best_val = h['net_farmer_value']
                best_d = d
                best_spoil = h['spoilage_pct']
        
        changed = (best_d != base_optimal_day)
        if changed:
            decision_changing_vars.add('Future Price')
        sweeps.append({
            'variable': 'Future Price',
            'variable_ta': 'எதிர்கால விலை',
            'variable_hi': 'भविष्य का मूल्य',
            'change': f"{pct:+d}% (₹{mod_inputs['future_price']:.1f})",
            'recommended_day': best_d,
            'farmer_value': round(best_val, 2),
            'spoilage_pct': round(best_spoil, 1),
            'decision_changed': changed
        })

    # 2. Temperature variations
    for temp_val in [20.0, 28.0, 35.0, 42.0]:
        mod_inputs = dict(inputs)
        mod_inputs['temperature'] = temp_val
        best_d = 0
        best_val = -1e9
        best_spoil = 0
        for d in range(11):
            h = simulate_horizon(mod_inputs, d, sim)
            if h['net_farmer_value'] > best_val:
                best_val = h['net_farmer_value']
                best_d = d
                best_spoil = h['spoilage_pct']
        changed = (best_d != base_optimal_day)
        if changed:
            decision_changing_vars.add('Temperature')
        sweeps.append({
            'variable': 'Temperature',
            'variable_ta': 'வெப்பநிலை',
            'variable_hi': 'तापमान',
            'change': f"{temp_val:.0f}°C",
            'recommended_day': best_d,
            'farmer_value': round(best_val, 2),
            'spoilage_pct': round(best_spoil, 1),
            'decision_changed': changed
        })

    # 3. Humidity variations
    for hum_val in [40.0, 60.0, 75.0, 90.0]:
        mod_inputs = dict(inputs)
        mod_inputs['humidity'] = hum_val
        best_d = 0
        best_val = -1e9
        best_spoil = 0
        for d in range(11):
            h = simulate_horizon(mod_inputs, d, sim)
            if h['net_farmer_value'] > best_val:
                best_val = h['net_farmer_value']
                best_d = d
                best_spoil = h['spoilage_pct']
        changed = (best_d != base_optimal_day)
        if changed:
            decision_changing_vars.add('Humidity')
        sweeps.append({
            'variable': 'Humidity',
            'variable_ta': 'ஈரப்பதம்',
            'variable_hi': 'आर्द्रता',
            'change': f"{hum_val:.0f}%",
            'recommended_day': best_d,
            'farmer_value': round(best_val, 2),
            'spoilage_pct': round(best_spoil, 1),
            'decision_changed': changed
        })

    # 4. Rain probability variations
    for rain_val in [0.0, 25.0, 50.0, 85.0]:
        mod_inputs = dict(inputs)
        mod_inputs['rain_probability'] = rain_val
        best_d = 0
        best_val = -1e9
        best_spoil = 0
        for d in range(11):
            h = simulate_horizon(mod_inputs, d, sim)
            if h['net_farmer_value'] > best_val:
                best_val = h['net_farmer_value']
                best_d = d
                best_spoil = h['spoilage_pct']
        changed = (best_d != base_optimal_day)
        if changed:
            decision_changing_vars.add('Rain Probability')
        sweeps.append({
            'variable': 'Rain Probability',
            'variable_ta': 'மழை வாய்ப்பு',
            'variable_hi': 'बारिश की संभावना',
            'change': f"{rain_val:.0f}%",
            'recommended_day': best_d,
            'farmer_value': round(best_val, 2),
            'spoilage_pct': round(best_spoil, 1),
            'decision_changed': changed
        })

    # 5. Storage duration variations
    for stor_days in [1.0, 3.0, 5.0, 8.0]:
        mod_inputs = dict(inputs)
        mod_inputs['storage_duration'] = stor_days
        best_d = 0
        best_val = -1e9
        best_spoil = 0
        for d in range(11):
            h = simulate_horizon(mod_inputs, d, sim)
            if h['net_farmer_value'] > best_val:
                best_val = h['net_farmer_value']
                best_d = d
                best_spoil = h['spoilage_pct']
        changed = (best_d != base_optimal_day)
        if changed:
            decision_changing_vars.add('Storage Duration')
        sweeps.append({
            'variable': 'Storage Duration',
            'variable_ta': 'சேமிப்பு காலம்',
            'variable_hi': 'भंडारण अवधि',
            'change': f"{stor_days:.0f} days",
            'recommended_day': best_d,
            'farmer_value': round(best_val, 2),
            'spoilage_pct': round(best_spoil, 1),
            'decision_changed': changed
        })

    # 6. Transport duration variations
    for trans_hrs in [1.0, 4.0, 8.0, 16.0]:
        mod_inputs = dict(inputs)
        mod_inputs['transport_duration'] = trans_hrs
        best_d = 0
        best_val = -1e9
        best_spoil = 0
        for d in range(11):
            h = simulate_horizon(mod_inputs, d, sim)
            if h['net_farmer_value'] > best_val:
                best_val = h['net_farmer_value']
                best_d = d
                best_spoil = h['spoilage_pct']
        changed = (best_d != base_optimal_day)
        if changed:
            decision_changing_vars.add('Transport Duration')
        sweeps.append({
            'variable': 'Transport Duration',
            'variable_ta': 'போக்குவரத்து நேரம்',
            'variable_hi': 'परिवहन समय',
            'change': f"{trans_hrs:.0f} hrs",
            'recommended_day': best_d,
            'farmer_value': round(best_val, 2),
            'spoilage_pct': round(best_spoil, 1),
            'decision_changed': changed
        })

    # 7. Maturity variations
    for mat_val in [40.0, 65.0, 80.0, 98.0]:
        mod_inputs = dict(inputs)
        mod_inputs['maturity'] = mat_val
        best_d = 0
        best_val = -1e9
        best_spoil = 0
        for d in range(11):
            h = simulate_horizon(mod_inputs, d, sim)
            if h['net_farmer_value'] > best_val:
                best_val = h['net_farmer_value']
                best_d = d
                best_spoil = h['spoilage_pct']
        changed = (best_d != base_optimal_day)
        if changed:
            decision_changing_vars.add('Maturity')
        sweeps.append({
            'variable': 'Maturity',
            'variable_ta': 'முதிர்ச்சி',
            'variable_hi': 'परिपक्वता',
            'change': f"{mat_val:.0f}%",
            'recommended_day': best_d,
            'farmer_value': round(best_val, 2),
            'spoilage_pct': round(best_spoil, 1),
            'decision_changed': changed
        })

    return {
        'table': sweeps,
        'decision_changing_variables': list(decision_changing_vars),
        'summary': f"Parameters that actively alter optimal harvest timing: {', '.join(decision_changing_vars) if decision_changing_vars else 'None (decision is robust across tested ranges)'}"
    }


def run_simulation(inputs: dict) -> dict:
    """
    Main entry point for running the complete risk-aware simulation.
    Handles input sanitation, edge cases, horizon simulation (0-10),
    independent baseline evaluation, 4-tier market simulation, price scenarios,
    sensitivity analysis, and explanation generation across English, Tamil, and Hindi.
    """
    warnings = []
    ta_warnings = []
    hi_warnings = []
    
    is_fallback = False
    clean_inputs = {}
    defaults = {
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
        'storage_condition': 'Ambient',
        'weather_condition': 'Sunny'
    }

    # Strict validation / sanitize missing or invalid values
    for key, def_val in defaults.items():
        val = inputs.get(key)
        if val is None or val == '':
            is_fallback = True
            clean_inputs[key] = def_val
        else:
            if isinstance(def_val, float):
                try:
                    parsed_val = float(val)
                    # Non-negative checks (except temperature)
                    if parsed_val < 0 and key not in ['temperature']:
                        warnings.append(f"{key.replace('_', ' ').capitalize()} was negative ({parsed_val}); reset to fallback ({def_val}).")
                        ta_warnings.append(f"{key} எதிர்மறையாக இருந்தது; இயல்புநிலைக்கு மாற்றப்பட்டது.")
                        hi_warnings.append(f"{key} नकारात्मक था; डिफ़ॉल्ट मान लागू किया गया।")
                        clean_inputs[key] = def_val
                        is_fallback = True
                    else:
                        clean_inputs[key] = parsed_val
                except (ValueError, TypeError):
                    clean_inputs[key] = def_val
                    is_fallback = True
            else:
                clean_inputs[key] = str(val)

    if is_fallback:
        warnings.append("Missing or incomplete input fields were detected. Conservative agronomic defaults have been applied.")
        ta_warnings.append("விடுபட்ட அல்லது முழுமையற்ற உள்ளீடுகள் கண்டறியப்பட்டன. இயல்புநிலை மதிப்புகள் பயன்படுத்தப்பட்டுள்ளன.")
        hi_warnings.append("लापता या अधूरे इनपुट फ़ील्ड पाए गए। रूढ़िवादी डिफ़ॉल्ट मान लागू किए गए हैं।")

    # Edge Case: Zero or Negative quantity
    if clean_inputs['quantity'] <= 0:
        clean_inputs['quantity'] = 1000.0
        warnings.append("Quantity was zero or negative; adjusted to 1,000 kg standard batch.")
        ta_warnings.append("பயிர் அளவு பூஜ்ஜியம் அல்லது எதிர்மறை; 1,000 கிலோவாக சரிசெய்யப்பட்டது.")
        hi_warnings.append("मात्रा शून्य या नकारात्मक थी; इसे 1,000 किलोग्राम मानक बैच पर समायोजित किया गया।")

    # Edge Case: Extreme Logistics (>14 days storage or >=24h transit)
    if clean_inputs['storage_duration'] >= 14.0 or clean_inputs['transport_duration'] >= 24.0:
        warnings.append("⚠️ Extreme logistics duration detected (≥14 days storage or ≥24 hrs transit). Perishable produce faces extreme risk of total degradation.")
        ta_warnings.append("⚠️ தீவிர போக்குவரத்து/சேமிப்பு காலம் (≥14 நாட்கள் அல்லது ≥24 மணி நேரம்). பயிர் முழுமையாக அழுகும் அபாயம் உள்ளது.")
        hi_warnings.append("⚠️ अत्यधिक भंडारण/परिवहन अवधि (≥14 दिन भंडारण या ≥24 घंटे परिवहन)। खराब होने वाली उपज को भारी नुकसान का खतरा है।")

    # Edge Case: Extreme Climate (Heatwave + High Humidity + Rain)
    if clean_inputs['temperature'] >= 40.0 and clean_inputs['humidity'] >= 75.0:
        warnings.append("⚠️ Critical Weather Alert: High temperature (≥40°C) with high humidity accelerates fungal rot. Immediate harvest strongly recommended.")
        ta_warnings.append("⚠️ தீவிர வானிலை எச்சரிக்கை: அதிக வெப்பநிலை மற்றும் ஈரப்பதம் விரைவான அழுகலை ஏற்படுத்துகிறது. உடனடியாக அறுவடை செய்யவும்.")
        hi_warnings.append("⚠️ गंभीर मौसम चेतावनी: उच्च आर्द्रता के साथ उच्च तापमान (≥40°C) फंगल सड़न को तेज करता है। तत्काल कटाई की सिफारिश की जाती है।")

    # Edge Case: Overmaturity (>100%)
    if clean_inputs['maturity'] > 100.0:
        warnings.append("Crop maturity is past 100% (overripe). Severe on-field shattering and rot penalties applied.")
        ta_warnings.append("பயிர் முதிர்ச்சி 100%க்கு மேல் உள்ளது (அதிக பழுத்தது). கள சேத அபாய தண்டனை விதிக்கப்பட்டுள்ளது.")
        hi_warnings.append("फसल की परिपक्वता 100% से अधिक है (अतिपक्व)। खेत में फल गिरने और सड़न का भारी जोखिम है।")

    sim = SpoilageSimulator()

    # 2. Simulate Harvest Horizons (Day 0 to Day 10)
    horizons = []
    best_horizon = None
    best_net_value = -1e9

    for d in range(11):
        h = simulate_horizon(clean_inputs, d, sim)
        horizons.append(h)
        if h['net_farmer_value'] > best_net_value:
            best_net_value = h['net_farmer_value']
            best_horizon = h

    day_0 = horizons[0]
    optimal_day = best_horizon['day']
    
    # Recommendation strings
    if optimal_day == 0:
        recommendation = "Harvest Now"
        recommendation_ta = "இப்போது அறுவடை செய்க"
        recommendation_hi = "अभी फसल काटें (दिन 0)"
    else:
        recommendation = f"Wait / Harvest on Day {optimal_day}"
        recommendation_ta = f"காத்திருந்து நாள் {optimal_day}-ல் அறுவடை செய்க"
        recommendation_hi = f"प्रतीक्षा करें / दिन {optimal_day} पर फसल काटें"

    # 3. Independent Baseline Comparison
    target_wait_days = int(round(clean_inputs['storage_duration'] if clean_inputs['storage_duration'] > 0 else 5.0))
    target_wait_days = max(1, min(10, target_wait_days))

    if clean_inputs['future_price'] > clean_inputs['current_price']:
        baseline_decision = f"Wait (Target Day {target_wait_days})"
        baseline_decision_ta = f"காத்திருங்கள் (நாள் {target_wait_days})"
        baseline_decision_hi = f"प्रतीक्षा करें (लक्ष्य दिन {target_wait_days})"
        baseline_outcome = horizons[target_wait_days]
    else:
        baseline_decision = "Harvest Now (Day 0)"
        baseline_decision_ta = "இப்போது அறுவடை (நாள் 0)"
        baseline_decision_hi = "अभी फसल काटें (दिन 0)"
        baseline_outcome = day_0

    baseline_net_value = baseline_outcome['net_farmer_value']
    baseline_spoilage = baseline_outcome['spoilage_pct']
    proposed_net_value = best_horizon['net_farmer_value']
    proposed_spoilage = best_horizon['spoilage_pct']

    value_diff = proposed_net_value - baseline_net_value
    value_diff_pct = (value_diff / max(1.0, abs(baseline_net_value))) * 100.0

    spoilage_diff = baseline_spoilage - proposed_spoilage
    spoilage_reduction_pct = (spoilage_diff / max(1.0, baseline_spoilage)) * 100.0

    # 4. Market Options Simulation (4 Channels)
    chosen_price = best_horizon['expected_price']
    chosen_maturity = best_horizon['maturity']
    markets = simulate_market_options(
        chosen_price=chosen_price,
        chosen_maturity=chosen_maturity,
        quantity=clean_inputs['quantity'],
        temp=clean_inputs['temperature'],
        humidity=clean_inputs['humidity'],
        rain_prob=clean_inputs['rain_probability'],
        storage_duration=clean_inputs['storage_duration'],
        ambient_storage=(clean_inputs['storage_condition'] == 'Ambient'),
        sim=sim
    )
    best_market = markets[0]

    # Market recommendation explanation with actual calculated values
    market_explanation = (
        f"Recommended Market Channel: {best_market['name']} (Expected Net Value: ₹{best_market['expected_market_value']:,.2f}). "
        f"Reason: Price realization is ₹{best_market['price']:.2f}/kg with {best_market['spoilage_pct']:.1f}% estimated transit spoilage. "
        f"Transport cost is ₹{best_market['transport_cost']:,.0f}, storage cost is ₹{best_market['storage_cost']:,.0f}, "
        f"and handling/commission overhead is ₹{best_market['handling_cost'] + best_market['commission']:,.0f}."
    )

    # 5. Price Scenarios (Low, Base, High)
    base_future = clean_inputs['future_price']
    price_scenarios = {}
    for sc_name, sc_name_ta, sc_name_hi, mult in [
        ('Low Price', 'குறைந்த விலை', 'कम मूल्य', 0.85),
        ('Base / Expected Price', 'எதிர்பார்க்கப்படும் விலை', 'अपेक्षित मूल्य', 1.00),
        ('High Price', 'அதிக விலை', 'उच्च मूल्य', 1.20)
    ]:
        sc_inputs = dict(clean_inputs)
        sc_inputs['future_price'] = round(base_future * mult, 2)
        sc_best_d = 0
        sc_best_val = -1e9
        sc_spoil = 0
        for d in range(11):
            h_sc = simulate_horizon(sc_inputs, d, sim)
            if h_sc['net_farmer_value'] > sc_best_val:
                sc_best_val = h_sc['net_farmer_value']
                sc_best_d = h_sc['day']
                sc_spoil = h_sc['spoilage_pct']
        price_scenarios[sc_name] = {
            'name_ta': sc_name_ta,
            'name_hi': sc_name_hi,
            'future_price': round(base_future * mult, 2),
            'recommended_day': sc_best_d,
            'expected_farmer_value': round(sc_best_val, 2),
            'spoilage_pct': round(sc_spoil, 1)
        }

    # 6. Sensitivity Analysis
    sensitivity = run_sensitivity_analysis(clean_inputs, optimal_day, sim)

    # 7. Explanation Layer & Uncertainty
    explanations = []
    ta_explanations = []
    hi_explanations = []

    if optimal_day == 0:
        explanations.append(f"Immediate harvest yields highest net value (₹{day_0['net_farmer_value']:,.2f}) by minimizing spoilage risk ({day_0['spoilage_pct']}%) and avoiding storage/field losses.")
        ta_explanations.append(f"இப்போதே அறுவடை செய்வது அழுகல் அபாயத்தைக் குறைத்து அதிக நிகர மதிப்பை (₹{day_0['net_farmer_value']:,.2f}) ஈட்டுகிறது.")
        hi_explanations.append(f"तत्काल कटाई फसल खराबी के जोखिम ({day_0['spoilage_pct']}%) को कम करके उच्चतम शुद्ध लाभ (₹{day_0['net_farmer_value']:,.2f}) देती है।")
        if clean_inputs['future_price'] <= clean_inputs['current_price']:
            explanations.append(f"Expected future price (₹{clean_inputs['future_price']}/kg) offers no premium over current price (₹{clean_inputs['current_price']}/kg).")
            ta_explanations.append(f"எதிர்கால விலை (₹{clean_inputs['future_price']}/கிலோ) தற்போதைய விலையை விட அதிகமாக இல்லை.")
            hi_explanations.append(f"अपेक्षित भविष्य का मूल्य (₹{clean_inputs['future_price']}/किग्रा) वर्तमान मूल्य (₹{clean_inputs['current_price']}/किग्रा) से अधिक नहीं है।")
        else:
            explanations.append(f"Future price gain (+₹{clean_inputs['future_price'] - clean_inputs['current_price']:.1f}/kg) is wiped out by accelerated decay and logistics costs.")
            ta_explanations.append(f"எதிர்கால விலை உயர்வு பயிர் அழுகல் மற்றும் போக்குவரத்து செலவுகளால் இழக்கப்படுகிறது.")
            hi_explanations.append(f"भविष्य की मूल्य वृद्धि (+₹{clean_inputs['future_price'] - clean_inputs['current_price']:.1f}/किग्रा) तेजी से सड़न और रसद लागत से समाप्त हो जाती है।")
    else:
        gain = best_horizon['net_farmer_value'] - day_0['net_farmer_value']
        explanations.append(f"Waiting until Day {optimal_day} increases net farmer earnings by ₹{gain:,.2f} (+{(gain / max(1.0, day_0['net_farmer_value'])) * 100:.1f}%) compared to Day 0.")
        ta_explanations.append(f"நாள் {optimal_day} வரை காத்திருப்பது நாள் 0-ஐ விட கூடுதல் நிகர லாபத்தை (₹{gain:,.2f}) தருகிறது.")
        hi_explanations.append(f"दिन {optimal_day} तक प्रतीक्षा करने से दिन 0 की तुलना में शुद्ध किसान आय में ₹{gain:,.2f} की वृद्धि होती है।")
        explanations.append(f"Market price increase from ₹{clean_inputs['current_price']}/kg to ₹{best_horizon['expected_price']}/kg comfortably exceeds the additional {best_horizon['spoilage_pct'] - day_0['spoilage_pct']:.1f}% spoilage risk.")
        ta_explanations.append(f"விலை உயர்வு கூடுதல் அழுகல் இழப்பை விட அதிகமாக உள்ளது.")
        hi_explanations.append(f"मूल्य में वृद्धि अतिरिक्त {best_horizon['spoilage_pct'] - day_0['spoilage_pct']:.1f}% खराबी के जोखिम से कहीं अधिक लाभकारी है।")

    # Environmental risk driver identification
    if clean_inputs['temperature'] > 35.0:
        explanations.append(f"High ambient temperature ({clean_inputs['temperature']}°C) accelerates biochemical decay.")
        ta_explanations.append("அதிக சுற்றுப்புற வெப்பநிலை பயிர் அழுகலை விரைவுபடுத்துகிறது.")
        hi_explanations.append("उच्च परिवेश तापमान फसल के जैव-रासायनिक क्षय को तेज करता है।")
    if clean_inputs['humidity'] > 75.0:
        explanations.append(f"High relative humidity ({clean_inputs['humidity']}%) creates favorable conditions for fungal growth.")
        ta_explanations.append("அதிக ஈரப்பதம் பூஞ்சை காளான் வளர்ச்சியை ஊக்குவிக்கிறது.")
        hi_explanations.append("उच्च सापेक्ष आर्द्रता फंगल विकास और सड़न को बढ़ावा देती है।")
    if clean_inputs['rain_probability'] > 60.0:
        explanations.append(f"High precipitation forecast ({clean_inputs['rain_probability']}%) poses moisture logging risk.")
        ta_explanations.append("மழைக்கான அதிக வாய்ப்பு ஈரப்பதம் மற்றும் சேதத்தை அதிகரிக்கும்.")
        hi_explanations.append("भारी बारिश का पूर्वानुमान नमी और सड़न के खतरे को बढ़ाता है।")
    if clean_inputs['storage_condition'] == 'Ambient':
        explanations.append("Ambient storage lacks temperature regulation, leading to ~20% higher baseline spoilage than cold storage.")
        ta_explanations.append("சாதாரண சேமிப்பு கிடங்கு குளிர்பதன வசதியை விட 20% அதிக அழுகல் அபாயத்தைக் கொண்டுள்ளது.")
        hi_explanations.append("सामान्य भंडारण में तापमान नियंत्रण न होने के कारण कोल्ड स्टोरेज की तुलना में ~20% अधिक खराबी होती है।")

    # Statistically grounded uncertainty rating
    margin = abs(day_0['net_farmer_value'] - best_horizon['net_farmer_value']) / max(1.0, abs(day_0['net_farmer_value']))
    if clean_inputs['temperature'] > 38.0 or clean_inputs['rain_probability'] > 80.0 or is_fallback:
        confidence_level = "Low"
        confidence_desc = "High environmental volatility or default fallback assumptions increase forecast uncertainty."
        confidence_desc_ta = "அதிக வானிலை நிச்சயமற்ற தன்மை காரணமாக எச்சரிக்கையுடன் முடிவெடுக்கவும்."
        confidence_desc_hi = "उच्च मौसम अस्थिरता या डिफ़ॉल्ट मान्यताओं के कारण पूर्वानुमान अनिश्चितता अधिक है।"
    elif margin > 0.12:
        confidence_level = "High"
        confidence_desc = "Clear profit margin (>12%) separates the optimal decision from alternative horizons."
        confidence_desc_ta = "தெளிவான லாப இடைவெளி (>12%) இந்த முடிவை உறுதிப்படுத்துகிறது."
        confidence_desc_hi = "स्पष्ट लाभ मार्जिन (>12%) इष्टतम निर्णय को अन्य विकल्पों से अलग करता है।"
    else:
        confidence_level = "Medium"
        confidence_desc = "Moderate decision margin. Monitor local weather and spot mandi prices before finalizing."
        confidence_desc_ta = "நடுத்தர லாப இடைவெளி. உள்ளூர் சந்தை நிலவரத்தை கவனித்து முடிவு எடுக்கவும்."
        confidence_desc_hi = "मध्यम निर्णय मार्जिन। अंतिम निर्णय लेने से पहले स्थानीय मंडी भाव की निगरानी करें।"

    return {
        'inputs': clean_inputs,
        'warnings': warnings,
        'ta_warnings': ta_warnings,
        'hi_warnings': hi_warnings,
        'is_fallback': is_fallback,
        'recommendation': recommendation,
        'recommendation_ta': recommendation_ta,
        'recommendation_hi': recommendation_hi,
        'recommended_day': optimal_day,
        'confidence_level': confidence_level,
        'confidence_desc': confidence_desc,
        'confidence_desc_ta': confidence_desc_ta,
        'confidence_desc_hi': confidence_desc_hi,
        'optimal_horizon': best_horizon,
        'day_0': day_0,
        'horizons': horizons,
        'baseline': {
            'decision': baseline_decision,
            'decision_ta': baseline_decision_ta,
            'decision_hi': baseline_decision_hi,
            'net_farmer_value': round(baseline_net_value, 2),
            'spoilage_pct': round(baseline_spoilage, 2),
            'usable_qty': round(baseline_outcome['usable_qty'], 1),
            'day': baseline_outcome['day']
        },
        'proposed': {
            'decision': recommendation,
            'decision_ta': recommendation_ta,
            'decision_hi': recommendation_hi,
            'net_farmer_value': round(proposed_net_value, 2),
            'spoilage_pct': round(proposed_spoilage, 2),
            'usable_qty': round(best_horizon['usable_qty'], 1),
            'day': optimal_day
        },
        'comparison': {
            'value_difference': round(value_diff, 2),
            'value_difference_pct': round(value_diff_pct, 2),
            'spoilage_difference': round(spoilage_diff, 2),
            'spoilage_reduction_pct': round(spoilage_reduction_pct, 2)
        },
        'best_market': best_market,
        'market_explanation': market_explanation,
        'markets': markets,
        'price_scenarios': price_scenarios,
        'sensitivity': sensitivity,
        'explanations': explanations,
        'ta_explanations': ta_explanations,
        'hi_explanations': hi_explanations
    }


def simulate_farm_plots(plots_list: list) -> dict:
    """
    Evaluates multi-plot, multi-crop farm portfolio.
    Each plot possesses independent crop, quantity, maturity, weather,
    storage conditions, transport duration, and market options.
    """
    if not plots_list:
        return {'plots': [], 'summary': {}}

    evaluated_plots = []
    total_qty = 0.0
    total_value = 0.0
    total_spoilage_product = 0.0
    immediate_count = 0
    wait_count = 0

    for idx, p in enumerate(plots_list):
        plot_id = p.get('id', f"plot-{idx+1}")
        plot_name = p.get('name', f"Plot {idx+1}")
        res = run_simulation(p)

        opt_day = res['recommended_day']
        best_market = res['best_market']
        exp_val = res['proposed']['net_farmer_value']
        spoil_pct = res['proposed']['spoilage_pct']
        risk_lvl = res['optimal_horizon']['risk_level']

        if opt_day == 0:
            immediate_count += 1
        else:
            wait_count += 1

        qty = float(res['inputs'].get('quantity', 1000.0))
        total_qty += qty
        total_value += exp_val
        total_spoilage_product += spoil_pct * qty

        evaluated_plots.append({
            'id': plot_id,
            'name': plot_name,
            'crop': res['inputs'].get('crop', 'Tomato'),
            'quantity': qty,
            'maturity': res['inputs'].get('maturity', 80.0),
            'recommended_day': opt_day,
            'recommendation': res['recommendation'],
            'recommendation_ta': res['recommendation_ta'],
            'recommendation_hi': res['recommendation_hi'],
            'recommended_market': best_market['name'],
            'recommended_market_ta': best_market['name_ta'],
            'recommended_market_hi': best_market['name_hi'],
            'expected_farmer_value': exp_val,
            'spoilage_pct': spoil_pct,
            'spoilage_risk': risk_lvl,
            'spoilage_risk_ta': res['optimal_horizon']['risk_level_ta'],
            'spoilage_risk_hi': res['optimal_horizon']['risk_level_hi'],
            'full_result': res
        })

    avg_spoilage = round(total_spoilage_product / max(1.0, total_qty), 1) if total_qty > 0 else 0.0

    return {
        'plots': evaluated_plots,
        'summary': {
            'total_plots': len(evaluated_plots),
            'total_quantity_kg': round(total_qty, 1),
            'total_expected_value': round(total_value, 2),
            'average_spoilage_pct': avg_spoilage,
            'immediate_harvest_count': immediate_count,
            'wait_count': wait_count
        }
    }
