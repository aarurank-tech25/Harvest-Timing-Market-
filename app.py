import os
import json
from flask import Flask, request, jsonify, render_template, send_from_directory
from simulator.engine import run_simulation
from models.train_model import train_and_save_model
from evaluation.evaluate import run_evaluation

app = Flask(__name__, template_folder='templates', static_folder='static')

# Ensure directories exist
os.makedirs('templates', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/simulate', methods=['POST'])
def simulate():
    try:
        inputs = request.json or {}
        result = run_simulation(inputs)
        return jsonify(result)
    except Exception as e:
        # Emergency recovery fallback
        try:
            fallback_res = run_simulation({})
            fallback_res['warnings'].append(f"Server recovered from input format exception: {str(e)}")
            return jsonify(fallback_res)
        except Exception as inner_e:
            return jsonify({'error': f'Internal Server Error: {str(inner_e)}'}), 500

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    metrics_path = 'reports/metrics.json'
    if not os.path.exists(metrics_path):
        run_evaluation()
    
    try:
        with open(metrics_path, 'r') as f:
            metrics = json.load(f)
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/train', methods=['POST'])
def retrain():
    try:
        train_and_save_model()
        run_evaluation()
        return jsonify({'status': 'success', 'message': 'Model retrained and evaluated successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reports/<path:filename>')
def serve_reports(filename):
    return send_from_directory('reports', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
