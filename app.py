"""
app.py

Flask Web Application & REST API for Harvest Timing & Market Option Simulator.
Production-ready with structured logging, health checks, live market price service,
live weather service, multi-plot support, and offline-first capabilities.
"""

import os
import json
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from config import Config
from simulator.engine import run_simulation, simulate_farm_plots
from simulator.market_service import get_market_price
from simulator.weather_service import get_live_weather
from models.train_model import train_and_save_model
from evaluation.evaluate import run_evaluation

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.from_object(Config)

# Ensure directories exist
os.makedirs('templates', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)
os.makedirs('reports', exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health():
    """Production health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'Harvest Timing & Market Option Simulator',
        'version': '1.1.0',
        'environment': 'development' if app.config['DEBUG'] else 'production'
    }), 200

@app.route('/api/market-price', methods=['GET', 'POST'])
def market_price():
    """Fetch live or fallback market price for a crop."""
    try:
        if request.method == 'POST':
            data = request.json or {}
            crop = data.get('crop', 'Tomato')
            state = data.get('state', 'Tamil Nadu')
            market = data.get('market', 'All')
        else:
            crop = request.args.get('crop', 'Tomato')
            state = request.args.get('state', 'Tamil Nadu')
            market = request.args.get('market', 'All')

        result = get_market_price(crop=crop, state=state, market=market)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching market price: {str(e)}")
        return jsonify({'error': str(e), 'source': 'fallback'}), 500

@app.route('/api/weather', methods=['GET', 'POST'])
def weather():
    """Fetch live weather based on GPS coordinates or district preset."""
    try:
        lat = None
        lon = None
        district = None

        if request.method == 'POST':
            data = request.json or {}
            lat = data.get('latitude') or data.get('lat')
            lon = data.get('longitude') or data.get('lon')
            district = data.get('district')
        else:
            lat_param = request.args.get('lat') or request.args.get('latitude')
            lon_param = request.args.get('lon') or request.args.get('longitude')
            district = request.args.get('district')
            if lat_param:
                try:
                    lat = float(lat_param)
                except (ValueError, TypeError):
                    lat = None
            if lon_param:
                try:
                    lon = float(lon_param)
                except (ValueError, TypeError):
                    lon = None

        result = get_live_weather(lat=lat, lon=lon, district=district)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching live weather: {str(e)}")
        return jsonify({'error': str(e), 'source': 'fallback'}), 500

@app.route('/api/simulate', methods=['POST'])
def simulate():
    """Simulate single plot harvest horizon and market channels."""
    try:
        inputs = request.json
        if not inputs:
            return jsonify({'error': 'No input data provided'}), 400
        
        # Verify validation / negative values
        errors = []
        for key in ['maturity', 'quantity', 'current_price', 'future_price', 
                    'humidity', 'rain_probability', 'storage_duration', 'transport_duration']:
            if key in inputs and inputs[key] is not None and inputs[key] != '':
                try:
                    val = float(inputs[key])
                    if val < 0:
                        errors.append(f"{key.replace('_', ' ').capitalize()} cannot be negative.")
                except ValueError:
                    errors.append(f"{key.replace('_', ' ').capitalize()} must be a valid number.")

        if 'temperature' in inputs and inputs['temperature'] is not None and inputs['temperature'] != '':
            try:
                temp_val = float(inputs['temperature'])
                if temp_val < -20 or temp_val > 60:
                    errors.append("Temperature must be within plausible physical range (-20°C to 60°C).")
            except ValueError:
                errors.append("Temperature must be a valid number.")

        if errors:
            return jsonify({'error': 'Validation Error', 'messages': errors}), 400
            
        result = run_simulation(inputs)
        return jsonify(result), 200
    except ValueError as ve:
        logger.warning(f"Value error in simulate: {str(ve)}")
        return jsonify({'error': f'Invalid value format: {str(ve)}'}), 400
    except Exception as e:
        logger.error(f"Internal server error in simulate: {str(e)}")
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500

@app.route('/api/simulate-multi', methods=['POST'])
def simulate_multi():
    """Simulate multi-plot, multi-crop farm portfolio."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No farm data provided'}), 400
        
        plots = data.get('plots', [])
        if not plots or not isinstance(plots, list):
            return jsonify({'error': 'Plots must be a non-empty list'}), 400

        result = simulate_farm_plots(plots)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in multi-plot simulation: {str(e)}")
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500

@app.route('/api/simulate-multiple', methods=['POST'])
def simulate_multiple():
    """Stricter multi-plot endpoint with field validation and aliases."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No farm data provided'}), 400
        plots = data.get('plots')
        if plots is None:
            return jsonify({'error': 'Missing "plots" field'}), 400
        if not isinstance(plots, list) or len(plots) == 0:
            return jsonify({'error': 'Plots must be a non-empty list'}), 400
        errors = []
        for idx, plot in enumerate(plots):
            if not isinstance(plot, dict):
                errors.append(f'Plot at index {idx} must be an object')
                continue
            # Handle aliases
            if 'quantity_kg' in plot and 'quantity' not in plot:
                plot['quantity'] = plot['quantity_kg']
            if 'maturity_percent' in plot and 'maturity' not in plot:
                plot['maturity'] = plot['maturity_percent']
            # Required fields
            for key in ['id', 'crop', 'quantity', 'maturity']:
                if key not in plot:
                    errors.append(f"Plot {plot.get('id', idx)} missing required field '{key}'")
            # Numeric validation
            try:
                qty = float(plot.get('quantity', 0))
                if qty <= 0:
                    errors.append(f"Plot {plot.get('id', idx)}: quantity must be > 0")
            except (ValueError, TypeError):
                errors.append(f"Plot {plot.get('id', idx)}: quantity must be a number")
            try:
                mat = float(plot.get('maturity', -1))
                if not (0 <= mat <= 100):
                    errors.append(f"Plot {plot.get('id', idx)}: maturity must be between 0 and 100")
            except (ValueError, TypeError):
                errors.append(f"Plot {plot.get('id', idx)}: maturity must be a number")
            for opt in ['temperature', 'humidity', 'rain_probability', 'storage_duration', 'transport_duration']:
                if opt in plot:
                    try:
                        val = float(plot[opt])
                        if opt in ['humidity', 'rain_probability'] and not (0 <= val <= 100):
                            errors.append(f"Plot {plot.get('id', idx)}: {opt} must be 0–100")
                        if opt in ['storage_duration', 'transport_duration'] and val < 0:
                            errors.append(f"Plot {plot.get('id', idx)}: {opt} cannot be negative")
                    except (ValueError, TypeError):
                        errors.append(f"Plot {plot.get('id', idx)}: {opt} must be a number")
        if errors:
            return jsonify({'error': 'Validation Error', 'messages': errors}), 400
        result = simulate_farm_plots(plots)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in /api/simulate-multiple: {str(e)}")
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Returns compiled synthetic evaluation metrics."""
    metrics_path = 'reports/metrics.json'
    if not os.path.exists(metrics_path):
        run_evaluation()
    
    try:
        with open(metrics_path, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
        return jsonify(metrics), 200
    except Exception as e:
        logger.error(f"Error reading metrics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/train', methods=['POST'])
def retrain():
    """Retrains the machine learning model and re-runs evaluation."""
    try:
        train_and_save_model()
        run_evaluation()
        return jsonify({'status': 'success', 'message': 'Model retrained and evaluated successfully.'}), 200
    except Exception as e:
        logger.error(f"Error during retrain: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/reports/<path:filename>')
def serve_reports(filename):
    return send_from_directory('reports', filename)

if __name__ == '__main__':
    logger.info(f"Starting server on {Config.HOST}:{Config.PORT} (Debug={Config.DEBUG})")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
