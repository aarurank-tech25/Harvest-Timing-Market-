"""
models/train_model.py

Generates reproducible synthetic training data and trains an interpretable Linear Regression
model for post-harvest crop spoilage risk.
"""

import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

def generate_synthetic_dataset(num_records=1200, seed=42):
    """
    Generate synthetic agricultural dataset modeling harvest maturity,
    ambient/cold storage, weather, transport, and spoilage percentage.
    """
    np.random.seed(seed)
    
    crops = ['Tomato', 'Potato', 'Onion', 'Rice', 'Mango']
    
    # Feature distributions
    maturity = np.random.uniform(50, 100, num_records)
    temperature = np.random.uniform(15, 45, num_records)
    humidity = np.random.uniform(30, 95, num_records)
    rain_probability = np.random.uniform(0, 100, num_records)
    storage_duration = np.random.uniform(0, 10, num_records)
    transport_duration = np.random.uniform(0, 24, num_records)
    # 0 = Cold Storage, 1 = Ambient
    ambient_storage = np.random.binomial(1, 0.70, num_records)
    
    selected_crops = np.random.choice(crops, num_records)
    
    # Physical spoilage rate formulation (0 to 1 scale)
    base_spoilage = (
        0.06 * (maturity / 100.0) +
        0.12 * np.clip((temperature - 15.0) / 30.0, 0.0, 1.2) +
        0.05 * (humidity / 100.0) +
        0.07 * (rain_probability / 100.0) +
        0.14 * (storage_duration / 10.0) +
        0.08 * (transport_duration / 24.0)
    )
    
    # Ambient vs Cold Storage multiplier
    storage_factor = 1.0 * ambient_storage + 0.30 * (1 - ambient_storage)
    spoilage_rate = base_spoilage * storage_factor
    
    # Extreme weather/handling nonlinear acceleration
    heat_penalty = np.where((temperature > 38.0) & (humidity > 75.0), 0.15, 0.0)
    overripe_penalty = np.where(maturity >= 95.0, 0.10, 0.0)
    
    # Gaussian noise (sigma = 2%)
    noise = np.random.normal(0, 0.02, num_records)
    
    # Final bounded spoilage percentage
    spoilage_pct = np.clip((spoilage_rate + heat_penalty + overripe_penalty + noise) * 100.0, 0.0, 100.0)
    
    # Prices (INR / kg)
    current_price = np.random.uniform(18.0, 55.0, num_records)
    # Expected future price variation (-15% to +35%)
    price_change_pct = np.random.normal(0.08, 0.12, num_records)
    future_price = np.clip(current_price * (1.0 + price_change_pct), 8.0, 110.0)
    
    df = pd.DataFrame({
        'crop': selected_crops,
        'maturity': np.round(maturity, 1),
        'temperature': np.round(temperature, 1),
        'humidity': np.round(humidity, 1),
        'rain_probability': np.round(rain_probability, 1),
        'storage_duration': np.round(storage_duration, 1),
        'transport_duration': np.round(transport_duration, 1),
        'ambient_storage': ambient_storage,
        'current_price': np.round(current_price, 2),
        'future_price': np.round(future_price, 2),
        'spoilage_pct': np.round(spoilage_pct, 2)
    })
    
    return df

def train_and_save_model(data_path='data/synthetic_data.csv', model_path='models/spoilage_model.joblib'):
    print("=" * 60)
    print("Generating synthetic dataset (1200 records, seed=42)...")
    df = generate_synthetic_dataset(1200, seed=42)
    
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    
    df.to_csv(data_path, index=False)
    print(f"Saved dataset to {data_path}")
    
    features = ['maturity', 'temperature', 'humidity', 'rain_probability', 
                'storage_duration', 'transport_duration', 'ambient_storage']
    X = df[features]
    y = df['spoilage_pct']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    preds_test = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds_test))
    mae = mean_absolute_error(y_test, preds_test)
    r2 = r2_score(y_test, preds_test)
    
    print("-" * 60)
    print("SPOILAGE MODEL TRAINING METRICS:")
    print(f"  Test RMSE : {rmse:.4f}%")
    print(f"  Test MAE  : {mae:.4f}%")
    print(f"  Test R²   : {r2:.4f}")
    print("-" * 60)
    print(f"  Intercept : {model.intercept_:.4f}")
    for col, coef in zip(features, model.coef_):
        print(f"  {col:<20}: {coef:+.4f}")
    print("-" * 60)
    
    model_data = {
        'model': model,
        'features': features,
        'coef': list(model.coef_),
        'intercept': float(model.intercept_),
        'metrics': {
            'rmse': round(float(rmse), 4),
            'mae': round(float(mae), 4),
            'r2': round(float(r2), 4)
        }
    }
    
    joblib.dump(model_data, model_path)
    print(f"Model successfully saved to {model_path}")
    print("=" * 60)
    return model_data

if __name__ == '__main__':
    train_and_save_model()
