import os
import joblib
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'spoilage_model.joblib')

CROP_FACTORS = {
    'Tomato': 1.15,
    'Potato': 0.65,
    'Onion': 0.55,
    'Rice': 0.35,
    'Mango': 1.10
}

CROP_GROWTH_RATES = {
    'Tomato': 2.8,  # % maturity increase per day on field
    'Potato': 1.5,
    'Onion': 1.2,
    'Rice': 1.0,
    'Mango': 2.5
}

class SpoilageSimulator:
    def __init__(self):
        self.coef = {
            'maturity': 0.0642,
            'temperature': 0.2561,
            'humidity': 0.0427,
            'rain_probability': 0.0602,
            'storage_duration': 0.9711,
            'transport_duration': 0.2670,
            'ambient_storage': 18.5839,
            'intercept': -19.8232
        }
        self.load_model()

    def load_model(self):
        if os.path.exists(MODEL_PATH):
            try:
                model_data = joblib.load(MODEL_PATH)
                if isinstance(model_data, dict) and 'coef' in model_data:
                    self.coef['maturity'] = float(model_data['coef'][0])
                    self.coef['temperature'] = float(model_data['coef'][1])
                    self.coef['humidity'] = float(model_data['coef'][2])
                    self.coef['rain_probability'] = float(model_data['coef'][3])
                    self.coef['storage_duration'] = float(model_data['coef'][4])
                    self.coef['transport_duration'] = float(model_data['coef'][5])
                    self.coef['ambient_storage'] = float(model_data['coef'][6])
                    self.coef['intercept'] = float(model_data['intercept'])
            except Exception as e:
                # Silently use calibrated fallback coefficients
                pass

    def predict_spoilage_pct(self, maturity, temp, humidity, rain_prob, storage_days, transport_hours, ambient_storage, crop='Tomato', spoilage_multiplier=1.0):
        maturity = max(0.0, float(maturity))
        temp = float(temp)
        humidity = max(0.0, min(100.0, float(humidity)))
        rain_prob = max(0.0, min(100.0, float(rain_prob)))
        storage_days = max(0.0, float(storage_days))
        transport_hours = max(0.0, float(transport_hours))
        ambient = 1.0 if ambient_storage else 0.0

        raw_spoilage = (
            self.coef['intercept'] +
            self.coef['maturity'] * maturity +
            self.coef['temperature'] * temp +
            self.coef['humidity'] * humidity +
            self.coef['rain_probability'] * rain_prob +
            self.coef['storage_duration'] * storage_days +
            self.coef['transport_duration'] * transport_hours +
            self.coef['ambient_storage'] * ambient
        )

        # Physical nonlinear over-ripening adjustments
        if maturity >= 100:
            raw_spoilage += 12.0 + (maturity - 100) * 1.5
        elif maturity > 90:
            raw_spoilage += (maturity - 90) * 0.8

        # Extreme heat & humidity accelerating microbial decay
        if temp > 38 and humidity > 70:
            raw_spoilage += 15.0
        elif temp > 35:
            raw_spoilage += 6.0

        # High precipitation / dampness risk
        if rain_prob > 75:
            raw_spoilage += 8.0

        # Long transport transit stress
        if transport_hours > 12:
            raw_spoilage += 10.0

        # Crop factor
        crop_factor = CROP_FACTORS.get(crop, 1.0)
        final_spoilage = raw_spoilage * crop_factor * float(spoilage_multiplier)

        # Ambient storage minimum floor vs cold storage preservation
        if not ambient_storage:
            final_spoilage = max(1.0, final_spoilage * 0.40)
        else:
            final_spoilage = max(2.5, final_spoilage)

        return float(np.clip(final_spoilage, 0.0, 99.0))

    @staticmethod
    def get_risk_level(spoilage_pct):
        if spoilage_pct < 10.0:
            return 'Low Risk'
        elif spoilage_pct <= 25.0:
            return 'Medium Risk'
        else:
            return 'High Risk'

def validate_and_normalize_inputs(inputs: dict) -> tuple[dict, bool, list]:
    """
    Validates inputs and handles missing values via robust fallbacks.
    Returns: (cleaned_inputs, fallback_used, warnings)
    """
    cleaned = dict(inputs) if inputs else {}
    warnings = []
    fallback_used = False

    # Defaults for fallback
    defaults = {
        'crop': 'Tomato',
        'maturity': 80.0,
        'quantity': 1000.0,
        'current_price': 30.0,
        'future_price': 35.0,
        'temperature': 25.0,
        'humidity': 60.0,
        'rain_probability': 20.0,
        'weather_condition': 'Sunny',
        'storage_duration': 2.0,
        'storage_condition': 'Ambient',
        'transport_duration': 2.0,
        'spoilage_multiplier': 1.0
    }

    # Detect missing weather or price data
    missing_fields = []
    for key in ['temperature', 'humidity', 'rain_probability', 'current_price', 'future_price']:
        if key not in cleaned or cleaned[key] is None or cleaned[key] == '':
            cleaned[key] = defaults[key]
            missing_fields.append(key)
            fallback_used = True

    if missing_fields:
        warnings.append(f"Fallback data is being used for missing parameters: {', '.join(missing_fields)}.")

    # Convert numeric fields
    numeric_fields = [
        'maturity', 'quantity', 'current_price', 'future_price',
        'temperature', 'humidity', 'rain_probability',
        'storage_duration', 'transport_duration', 'spoilage_multiplier'
    ]
    for key in numeric_fields:
        try:
            cleaned[key] = float(cleaned.get(key, defaults[key]))
        except (ValueError, TypeError):
            cleaned[key] = defaults[key]
            fallback_used = True
            warnings.append(f"Invalid {key} formatted; fallback applied.")

    # Guard bounds
    if cleaned['quantity'] <= 0:
        cleaned['quantity'] = 1000.0
        warnings.append("Quantity was zero or negative; reset to 1000 kg standard.")

    if cleaned['current_price'] <= 0:
        cleaned['current_price'] = 10.0
        warnings.append("Current price was zero or negative; reset to ₹10/kg.")

    if cleaned['future_price'] <= 0:
        cleaned['future_price'] = cleaned['current_price']
        warnings.append("Future price was negative; clamped to current price.")

    cleaned['crop'] = str(cleaned.get('crop', 'Tomato'))
    if cleaned['crop'] not in CROP_FACTORS:
        cleaned['crop'] = 'Tomato'

    cleaned['storage_condition'] = str(cleaned.get('storage_condition', 'Ambient'))
    if cleaned['storage_condition'] not in ['Ambient', 'Cold Storage']:
        cleaned['storage_condition'] = 'Ambient'

    return cleaned, fallback_used, warnings

def calculate_single_day_metrics(sim: SpoilageSimulator, day: int, inputs: dict, price: float, maturity: float) -> dict:
    """
    Evaluates one harvest timing day (Day 0 through Day 10).
    """
    quantity = inputs['quantity']
    temp = inputs['temperature']
    humidity = inputs['humidity']
    rain_prob = inputs['rain_probability']
    storage_duration = inputs['storage_duration']
    transport_duration = inputs['transport_duration']
    ambient_storage = (inputs['storage_condition'] == 'Ambient')
    crop = inputs['crop']
    multiplier = inputs.get('spoilage_multiplier', 1.0)

    # In-field aging penalty if left unharvested
    field_decay = 0.0
    if day > 0:
        field_decay = max(0.0, (maturity - 90) * 0.4) + (0.35 * day if rain_prob > 60 else 0.12 * day)

    spoilage_pct = sim.predict_spoilage_pct(
        maturity=maturity,
        temp=temp,
        humidity=humidity,
        rain_prob=rain_prob,
        storage_days=storage_duration,
        transport_hours=transport_duration,
        ambient_storage=ambient_storage,
        crop=crop,
        spoilage_multiplier=multiplier
    )
    spoilage_pct = float(np.clip(spoilage_pct + field_decay, 0.0, 99.0))
    risk_level = sim.get_risk_level(spoilage_pct)

    # Core mathematical formulas:
    # 1. usable_quantity = quantity * (1 - spoilage_percentage / 100)
    usable_quantity = quantity * (1.0 - spoilage_pct / 100.0)

    # 2. revenue = usable_quantity * market_price
    revenue = usable_quantity * price

    # 3. storage_cost = quantity * storage_days * storage_rate
    storage_rate = 0.50 if ambient_storage else 1.50
    storage_cost = quantity * storage_duration * storage_rate

    # 4. transport_cost = quantity * transport_hours * transport_rate
    transport_rate = 0.75
    transport_cost = quantity * transport_duration * transport_rate

    # 5. handling/risk cost (field holding overhead + handling buffer)
    field_overhead = day * 0.15 * quantity
    handling_cost = (quantity * 0.20) + field_overhead

    # 6. expected_farmer_value = revenue - storage_cost - transport_cost - handling/risk cost
    expected_farmer_value = revenue - storage_cost - transport_cost - handling_cost

    spoilage_loss = (quantity - usable_quantity) * price

    return {
        'day': day,
        'price': round(price, 2),
        'maturity': round(maturity, 1),
        'spoilage_pct': round(spoilage_pct, 2),
        'usable_quantity': round(usable_quantity, 1),
        'gross_revenue': round(revenue, 2),
        'storage_cost': round(storage_cost, 2),
        'transport_cost': round(transport_cost, 2),
        'handling_cost': round(handling_cost, 2),
        'spoilage_loss': round(spoilage_loss, 2),
        'expected_farmer_value': round(expected_farmer_value, 2),
        'risk_level': risk_level
    }

def simulate_harvest_timeline(sim: SpoilageSimulator, inputs: dict) -> list[dict]:
    """
    Simulates harvest timing across Day 0 to Day 10.
    """
    timeline = []
    base_maturity = inputs['maturity']
    p0 = inputs['current_price']
    ptarget = inputs['future_price']
    crop = inputs['crop']
    growth_rate = CROP_GROWTH_RATES.get(crop, 2.0)

    # Daily linear price gradient anchored around Day 5 target
    price_slope = (ptarget - p0) / 5.0

    for day in range(11):
        # Projected day price
        day_price = max(1.0, p0 + price_slope * day)
        # Projected day maturity
        day_maturity = min(115.0, base_maturity + day * growth_rate)

        day_metric = calculate_single_day_metrics(sim, day, inputs, day_price, day_maturity)
        timeline.append(day_metric)

    return timeline

def calculate_market_options(sim: SpoilageSimulator, inputs: dict, chosen_day_metric: dict) -> list[dict]:
    """
    Priority 6: Transparently calculate Local Market, Wholesale Market, and Direct/Premium Market.
    """
    quantity = inputs['quantity']
    base_price = chosen_day_metric['price']
    maturity = chosen_day_metric['maturity']
    temp = inputs['temperature']
    humidity = inputs['humidity']
    rain_prob = inputs['rain_probability']
    storage_duration = inputs['storage_duration']
    base_transport = inputs['transport_duration']
    ambient_storage = (inputs['storage_condition'] == 'Ambient')
    crop = inputs['crop']

    storage_rate = 0.50 if ambient_storage else 1.50
    storage_cost = round(quantity * storage_duration * storage_rate, 2)

    # Define 3 standard agricultural channels
    market_configs = [
        {
            'key': 'local',
            'name': 'Local Market',
            'name_ta': 'உள்ளூர் சந்தை (Local Mandi)',
            'price_multiplier': 0.90,
            'transport_hours': max(0.5, round(base_transport * 0.4, 1)),
            'transport_rate': 0.40,
            'transit_stress_pct': -2.0,
            'desc': 'Quick local village / taluk mandi with minimal travel and lowest spoilage risk.'
        },
        {
            'key': 'wholesale',
            'name': 'Wholesale Market',
            'name_ta': 'மொத்த விற்பனை சந்தை (District Mandi)',
            'price_multiplier': 1.00,
            'transport_hours': max(1.5, round(base_transport * 1.0, 1)),
            'transport_rate': 0.75,
            'transit_stress_pct': 0.0,
            'desc': 'Standard APMC district wholesale auction market with standard volume throughput.'
        },
        {
            'key': 'direct_premium',
            'name': 'Direct / Premium Market',
            'name_ta': 'நேரடி / பிரீமியம் சந்தை (Retail / Exporter)',
            'price_multiplier': 1.30,
            'transport_hours': max(5.0, round(base_transport * 2.5, 1)),
            'transport_rate': 1.25,
            'transit_stress_pct': 4.5,
            'desc': 'Direct supermarket procurement or urban export center offering premium rates but requiring long transit.'
        }
    ]

    markets = []
    for cfg in market_configs:
        m_price = round(base_price * cfg['price_multiplier'], 2)
        m_trans_hours = cfg['transport_hours']
        
        # Calculate market specific spoilage
        m_spoilage = sim.predict_spoilage_pct(
            maturity=maturity,
            temp=temp,
            humidity=humidity,
            rain_prob=rain_prob,
            storage_days=storage_duration,
            transport_hours=m_trans_hours,
            ambient_storage=ambient_storage,
            crop=crop
        )
        m_spoilage = float(np.clip(m_spoilage + cfg['transit_stress_pct'], 0.0, 99.0))
        m_risk = sim.get_risk_level(m_spoilage)

        usable_qty = round(quantity * (1.0 - m_spoilage / 100.0), 1)
        gross_rev = round(usable_qty * m_price, 2)
        trans_cost = round(quantity * m_trans_hours * cfg['transport_rate'], 2)
        handling = round(quantity * 0.20, 2)
        net_val = round(gross_rev - storage_cost - trans_cost - handling, 2)

        markets.append({
            'key': cfg['key'],
            'name': cfg['name'],
            'name_ta': cfg['name_ta'],
            'price': m_price,
            'transport_hours': m_trans_hours,
            'transport_cost': trans_cost,
            'storage_cost': storage_cost,
            'handling_cost': handling,
            'spoilage_pct': round(m_spoilage, 2),
            'spoilage_loss': round((quantity - usable_qty) * m_price, 2),
            'usable_quantity': usable_qty,
            'gross_revenue': gross_rev,
            'net_farmer_value': net_val,
            'risk_level': m_risk,
            'description': cfg['desc']
        })

    # Sort descending by net farmer value
    markets.sort(key=lambda x: x['net_farmer_value'], reverse=True)
    return markets

def run_sensitivity_analysis(sim: SpoilageSimulator, base_inputs: dict, base_recommended_day: int) -> dict:
    """
    Priority 7: Evaluates variations in future price, spoilage rate, temperature,
    storage duration, and transport duration, identifying assumptions that CHANGE recommendation.
    """
    sens_results = {}
    flip_points = []
    flip_points_ta = []

    # 1. Future Price variations
    p0 = base_inputs['current_price']
    fp = base_inputs['future_price']
    price_sweeps = [
        {'label': '-20%', 'mult': 0.8},
        {'label': '-10%', 'mult': 0.9},
        {'label': '0% (Base)', 'mult': 1.0},
        {'label': '+10%', 'mult': 1.1},
        {'label': '+20%', 'mult': 1.2},
        {'label': '+30%', 'mult': 1.3}
    ]
    price_curve = []
    for item in price_sweeps:
        mod_inputs = dict(base_inputs)
        mod_inputs['future_price'] = round(fp * item['mult'], 2)
        timeline = simulate_harvest_timeline(sim, mod_inputs)
        best_day = max(timeline, key=lambda x: x['expected_farmer_value'])
        price_curve.append({
            'variation': item['label'],
            'future_price': mod_inputs['future_price'],
            'recommended_day': best_day['day'],
            'expected_farmer_value': best_day['expected_farmer_value'],
            'spoilage_pct': best_day['spoilage_pct']
        })
        if best_day['day'] != base_recommended_day:
            flip_points.append(f"Future price {item['label']} (₹{mod_inputs['future_price']}/kg) changes recommendation from Day {base_recommended_day} to Day {best_day['day']}.")
            flip_points_ta.append(f"எதிர்கால விலை {item['label']} (₹{mod_inputs['future_price']}/கிலோ) முடிவை நாள் {base_recommended_day}-லிருந்து நாள் {best_day['day']}-ஆக மாற்றுகிறது.")

    sens_results['future_price'] = price_curve

    # 2. Spoilage Rate Multiplier variations
    spoil_sweeps = [
        {'label': '0.7x (Low decay)', 'val': 0.7},
        {'label': '0.9x', 'val': 0.9},
        {'label': '1.0x (Standard)', 'val': 1.0},
        {'label': '1.2x', 'val': 1.2},
        {'label': '1.5x (Accelerated)', 'val': 1.5}
    ]
    spoil_curve = []
    for item in spoil_sweeps:
        mod_inputs = dict(base_inputs)
        mod_inputs['spoilage_multiplier'] = item['val']
        timeline = simulate_harvest_timeline(sim, mod_inputs)
        best_day = max(timeline, key=lambda x: x['expected_farmer_value'])
        spoil_curve.append({
            'variation': item['label'],
            'multiplier': item['val'],
            'recommended_day': best_day['day'],
            'expected_farmer_value': best_day['expected_farmer_value'],
            'spoilage_pct': best_day['spoilage_pct']
        })
        if best_day['day'] != base_recommended_day:
            flip_points.append(f"Spoilage rate {item['label']} changes recommendation from Day {base_recommended_day} to Day {best_day['day']}.")
            flip_points_ta.append(f"அழுகல் விகிதம் {item['label']} முடிவை நாள் {base_recommended_day}-லிருந்து நாள் {best_day['day']}-ஆக மாற்றுகிறது.")

    sens_results['spoilage_rate'] = spoil_curve

    # 3. Temperature variations
    base_temp = base_inputs['temperature']
    temp_sweeps = [-5, 0, 5, 10, 15]
    temp_curve = []
    for dt in temp_sweeps:
        mod_inputs = dict(base_inputs)
        mod_inputs['temperature'] = base_temp + dt
        timeline = simulate_harvest_timeline(sim, mod_inputs)
        best_day = max(timeline, key=lambda x: x['expected_farmer_value'])
        temp_curve.append({
            'variation': f"{dt:+d}°C",
            'temperature': mod_inputs['temperature'],
            'recommended_day': best_day['day'],
            'expected_farmer_value': best_day['expected_farmer_value'],
            'spoilage_pct': best_day['spoilage_pct']
        })
        if best_day['day'] != base_recommended_day and dt != 0:
            flip_points.append(f"Temperature change {dt:+d}°C ({mod_inputs['temperature']}°C) changes recommendation from Day {base_recommended_day} to Day {best_day['day']}.")
            flip_points_ta.append(f"வெப்பநிலை மாற்றம் {dt:+d}°C ({mod_inputs['temperature']}°C) முடிவை நாள் {base_recommended_day}-லிருந்து நாள் {best_day['day']}-ஆக மாற்றுகிறது.")

    sens_results['temperature'] = temp_curve

    # 4. Storage duration variations
    storage_sweeps = [0, 2, 4, 7, 10]
    storage_curve = []
    for sd in storage_sweeps:
        mod_inputs = dict(base_inputs)
        mod_inputs['storage_duration'] = float(sd)
        timeline = simulate_harvest_timeline(sim, mod_inputs)
        best_day = max(timeline, key=lambda x: x['expected_farmer_value'])
        storage_curve.append({
            'variation': f"{sd} days",
            'storage_duration': sd,
            'recommended_day': best_day['day'],
            'expected_farmer_value': best_day['expected_farmer_value'],
            'spoilage_pct': best_day['spoilage_pct']
        })
        if best_day['day'] != base_recommended_day:
            flip_points.append(f"Storage duration of {sd} days changes recommendation from Day {base_recommended_day} to Day {best_day['day']}.")
            flip_points_ta.append(f"சேமிப்பு காலம் {sd} நாட்கள் முடிவை நாள் {base_recommended_day}-லிருந்து நாள் {best_day['day']}-ஆக மாற்றுகிறது.")

    sens_results['storage_duration'] = storage_curve

    # 5. Transport duration variations
    trans_sweeps = [1, 2, 4, 8, 14]
    trans_curve = []
    for td in trans_sweeps:
        mod_inputs = dict(base_inputs)
        mod_inputs['transport_duration'] = float(td)
        timeline = simulate_harvest_timeline(sim, mod_inputs)
        best_day = max(timeline, key=lambda x: x['expected_farmer_value'])
        trans_curve.append({
            'variation': f"{td} hours",
            'transport_duration': td,
            'recommended_day': best_day['day'],
            'expected_farmer_value': best_day['expected_farmer_value'],
            'spoilage_pct': best_day['spoilage_pct']
        })
        if best_day['day'] != base_recommended_day:
            flip_points.append(f"Transport duration of {td} hours changes recommendation from Day {base_recommended_day} to Day {best_day['day']}.")
            flip_points_ta.append(f"போக்குவரத்து நேரம் {td} மணி முடிவை நாள் {base_recommended_day}-லிருந்து நாள் {best_day['day']}-ஆக மாற்றுகிறது.")

    sens_results['transport_duration'] = trans_curve
    sens_results['flip_points'] = flip_points
    sens_results['flip_points_ta'] = flip_points_ta

    return sens_results

def build_explanations(rec_day: int, timeline: list[dict], inputs: dict, best_market: dict) -> tuple[list[str], list[str]]:
    """
    Priority 8: Generates plain-language, quantitative justification for the farmer.
    """
    day0 = timeline[0]
    day_opt = timeline[rec_day]

    delta_price = round(day_opt['price'] - day0['price'], 2)
    delta_spoil = round(day_opt['spoilage_pct'] - day0['spoilage_pct'], 2)
    delta_store = round(day_opt['storage_cost'] - day0['storage_cost'], 2)
    delta_trans = round(day_opt['transport_cost'] - day0['transport_cost'], 2)
    delta_val = round(day_opt['expected_farmer_value'] - day0['expected_farmer_value'], 2)

    exps = []
    exps_ta = []

    if rec_day == 0:
        exps.append(f"Harvest immediately on Day 0 to avoid rapid spoilage and moisture risks on the field.")
        exps_ta.append(f"வயலில் பயிர் விரைவாக அழுகுதல் மற்றும் ஈரப்பத சேதத்தைத் தவிர்க்க உடனடியாக நாள் 0-ல் அறுவடை செய்யவும்.")
        if delta_price > 0:
            exps.append(f"Even though future price rises by ₹{delta_price}/kg, projected post-harvest decay would erase ₹{abs(delta_val):.2f} in net profit.")
            exps_ta.append(f"எதிர்கால விலை ₹{delta_price}/கிலோ உயர்ந்தாலும், அழுகல் இழப்பு நிகர லாபத்தில் ₹{abs(delta_val):.2f} சேதத்தை ஏற்படுத்தும்.")
        else:
            exps.append(f"Future market price shows no gain (₹{day_opt['price']}/kg vs ₹{day0['price']}/kg today).")
            exps_ta.append(f"எதிர்கால சந்தை விலையில் எந்த உயர்வும் இல்லை (இன்று ₹{day0['price']}/கிலோ vs எதிர்காலம் ₹{day_opt['price']}/கிலோ).")
    else:
        exps.append(f"Recommended harvest on Day {rec_day}: Projected market price reaches ₹{day_opt['price']}/kg (+₹{delta_price}/kg compared to today).")
        exps_ta.append(f"பரிந்துரைக்கப்பட்ட அறுவடை நாள் {rec_day}: சந்தை விலை ₹{day_opt['price']}/கிலோ வரை உயரும் (இன்றை விட +₹{delta_price}/கிலோ அதிகம்).")
        exps.append(f"Expected spoilage increases modestly to {day_opt['spoilage_pct']}% (a change of {delta_spoil:+0.1f}% over Day 0).")
        exps_ta.append(f"எதிர்பார்க்கப்படும் பயிர் அழுகல் {day_opt['spoilage_pct']}% ஆக மிதமாகவே உயர்கிறது (நாள் 0-ஐ விட {delta_spoil:+0.1f}% மாற்றம்).")
        exps.append(f"Harvesting on Day {rec_day} yields ₹{delta_val:,.2f} more Expected Farmer Value than immediate Day 0 harvest.")
        exps_ta.append(f"நாள் {rec_day}-ல் அறுவடை செய்வது உடனடியாக அறுவடை செய்வதை விட ₹{delta_val:,.2f} கூடுதல் நிகர மதிப்பை ஈட்டித் தரும்.")

    # Storage & channel specific driver
    if best_market:
        exps.append(f"Optimal channel: {best_market['name']} yields highest net return of ₹{best_market['net_farmer_value']:,.2f} after transit & storage fees.")
        exps_ta.append(f"சிறந்த சந்தை வாய்ப்பு: {best_market['name_ta']} போக்குவரத்து & சேமிப்பு செலவுக்குப் பின் அதிகபட்ச நிகர மதிப்பான ₹{best_market['net_farmer_value']:,.2f}-ஐ வழங்குகிறது.")

    # Extreme risk warnings
    if inputs['temperature'] > 38:
        exps.append(f"Warning: Ambient temperature ({inputs['temperature']}°C) is severe; minimize post-harvest delay.")
        exps_ta.append(f"எச்சரிக்கை: தீவிர சுற்றுப்புற வெப்பநிலை ({inputs['temperature']}°C); அறுவடைக்குப் பிந்தைய தாமதத்தை தவிர்க்கவும்.")

    if inputs['rain_probability'] > 75:
        exps.append(f"Warning: Rain risk is {inputs['rain_probability']}%; waterlogged soil will escalate transit decay.")
        exps_ta.append(f"எச்சரிக்கை: மழை வாய்ப்பு {inputs['rain_probability']}%; ஈரப்பதம் பயிர் அழுகலை விரைவுபடுத்தும்.")

    return exps, exps_ta

def calculate_price_scenarios(sim: SpoilageSimulator, inputs: dict) -> dict:
    """
    Evaluates Low, Base/Expected, and High future price scenarios.
    """
    fp = inputs['future_price']
    
    scenarios = {}
    for key, name, name_ta, mult in [
        ('low', 'Low Price Scenario (-15%)', 'குறைந்த விலை காட்சி (-15%)', 0.85),
        ('base', 'Expected / Base Scenario', 'எதிர்பார்க்கப்படும் அடிப்படை காட்சி', 1.00),
        ('high', 'High Price Scenario (+20%)', 'அதிக விலை காட்சி (+20%)', 1.20)
    ]:
        mod_inputs = dict(inputs)
        mod_inputs['future_price'] = round(fp * mult, 2)
        timeline = simulate_harvest_timeline(sim, mod_inputs)
        best_day = max(timeline, key=lambda x: x['expected_farmer_value'])
        markets = calculate_market_options(sim, mod_inputs, best_day)
        scenarios[key] = {
            'key': key,
            'scenario_name': name,
            'scenario_name_ta': name_ta,
            'future_price': mod_inputs['future_price'],
            'recommended_day': best_day['day'],
            'expected_farmer_value': best_day['expected_farmer_value'],
            'spoilage_pct': best_day['spoilage_pct'],
            'usable_quantity': best_day['usable_quantity'],
            'risk_level': best_day['risk_level'],
            'best_market': markets[0]['name'] if markets else 'Wholesale Market'
        }
    return scenarios

def run_simulation(inputs: dict) -> dict:
    """
    Main entry point for the simulator.
    Executes full Day 0-10 harvest simulation, Baseline (Day 0) comparison,
    Market channel selection, Sensitivity analysis, Price scenarios, and Explanation generation.
    """
    cleaned_inputs, fallback_used, warnings = validate_and_normalize_inputs(inputs)
    sim = SpoilageSimulator()

    # 1. Harvest Simulation: Day 0 -> Day 10
    timeline = simulate_harvest_timeline(sim, cleaned_inputs)

    # 2. Find day with highest expected farmer value
    best_day_metric = max(timeline, key=lambda x: x['expected_farmer_value'])
    recommended_day = best_day_metric['day']

    # 3. Priority 5: Baseline = Immediate Harvest / Day 0
    baseline_metric = timeline[0]
    proposed_metric = best_day_metric

    baseline_val = baseline_metric['expected_farmer_value']
    proposed_val = proposed_metric['expected_farmer_value']
    value_difference = round(proposed_val - baseline_val, 2)
    pct_improvement = round((value_difference / max(1.0, abs(baseline_val))) * 100.0, 2)
    spoilage_difference = round(proposed_metric['spoilage_pct'] - baseline_metric['spoilage_pct'], 2)

    # 4. Priority 6: Market channel comparison for recommended harvest day
    markets = calculate_market_options(sim, cleaned_inputs, proposed_metric)
    best_market = markets[0] if markets else None

    # 5. Price Scenarios: Low, Expected/Base, High
    price_scenarios = calculate_price_scenarios(sim, cleaned_inputs)

    # 6. Priority 7: Sensitivity analysis & flip detection
    sensitivity = run_sensitivity_analysis(sim, cleaned_inputs, recommended_day)

    # 7. Priority 8: Quantitative explanations
    explanations, ta_explanations = build_explanations(recommended_day, timeline, cleaned_inputs, best_market)

    # Decision label
    if recommended_day == 0:
        rec_decision_en = "HARVEST NOW (Day 0)"
        rec_decision_ta = "இப்போதே அறுவடை செய்க (நாள் 0)"
    else:
        rec_decision_en = f"HARVEST ON DAY {recommended_day}"
        rec_decision_ta = f"நாள் {recommended_day}-ல் அறுவடை செய்க"

    return {
        'inputs': cleaned_inputs,
        'fallback_used': fallback_used,
        'warnings': warnings,
        'timeline': timeline,
        'recommendation': {
            'day': recommended_day,
            'decision_en': rec_decision_en,
            'decision_ta': rec_decision_ta,
            'expected_farmer_value': proposed_metric['expected_farmer_value'],
            'expected_spoilage': proposed_metric['spoilage_pct'],
            'risk_level': proposed_metric['risk_level'],
            'usable_quantity': proposed_metric['usable_quantity'],
            'gross_revenue': proposed_metric['gross_revenue'],
            'storage_cost': proposed_metric['storage_cost'],
            'transport_cost': proposed_metric['transport_cost'],
            'handling_cost': proposed_metric['handling_cost'],
            'price': proposed_metric['price']
        },
        'baseline_comparison': {
            'baseline_name': 'Immediate Harvest (Day 0)',
            'baseline_name_ta': 'உடனடி அறுவடை (நாள் 0)',
            'baseline_farmer_value': baseline_metric['expected_farmer_value'],
            'baseline_spoilage': baseline_metric['spoilage_pct'],
            'baseline_usable_qty': baseline_metric['usable_quantity'],
            'proposed_farmer_value': proposed_metric['expected_farmer_value'],
            'proposed_spoilage': proposed_metric['spoilage_pct'],
            'proposed_usable_qty': proposed_metric['usable_quantity'],
            'value_difference': value_difference,
            'pct_improvement': pct_improvement,
            'spoilage_difference': spoilage_difference
        },
        'markets': markets,
        'best_market': best_market,
        'price_scenarios': price_scenarios,
        'sensitivity': sensitivity,
        'explanations': explanations,
        'ta_explanations': ta_explanations,
        # Backward compatibility aliases for existing JS callers if needed
        'harvest_now': baseline_metric,
        'harvest_later': proposed_metric,
        'baseline': {
            'decision': 'Immediate Harvest (Day 0)',
            'net_value': baseline_val,
            'spoilage_pct': baseline_metric['spoilage_pct']
        },
        'proposed': {
            'decision': rec_decision_en,
            'net_value': proposed_val,
            'spoilage_pct': proposed_metric['spoilage_pct']
        },
        'improvement': {
            'value': value_difference,
            'pct': pct_improvement
        }
    }
