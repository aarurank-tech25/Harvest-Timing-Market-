import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib

def generate_synthetic_dataset(num_records=1000, seed=42):
    np.random.seed(seed)
    
    crops = ['Tomato', 'Potato', 'Onion', 'Rice', 'Mango']
    
    # Generate random features
    maturity = np.random.uniform(50, 100, num_records)
    temperature = np.random.uniform(15, 45, num_records)
    humidity = np.random.uniform(30, 95, num_records)
    rain_probability = np.random.uniform(0, 100, num_records)
    storage_duration = np.random.uniform(0, 10, num_records)
    transport_duration = np.random.uniform(0, 24, num_records)
    # 0 = Cold Storage, 1 = Ambient
    ambient_storage = np.random.binomial(1, 0.7, num_records)
    
    selected_crops = np.random.choice(crops, num_records)
    
    # Calculate baseline spoilage based on physical rules + random noise
    base_spoilage = (
        0.05 * (maturity / 100) ** 2 +
        0.10 * ((temperature - 15) / 30) +
        0.05 * (humidity / 100) +
        0.08 * (rain_probability / 100) +
        0.12 * (storage_duration / 10) +
        0.08 * (transport_duration / 24)
    )
    
    # Adjust for storage condition: Cold storage reduces spoilage rate significantly
    spoilage_rate = base_spoilage * (1.0 * ambient_storage + 0.25 * (1 - ambient_storage))
    
    # Add random noise
    noise = np.random.normal(0, 0.02, num_records)
    spoilage_pct = np.clip((spoilage_rate + noise) * 100, 0, 100)
    
    # Current and expected future prices (simulated)
    current_price = np.random.uniform(15, 60, num_records)
    # future price is often higher, but sometimes drops
    price_change_pct = np.random.normal(0.1, 0.15, num_records)
    future_price = np.clip(current_price * (1 + price_change_pct), 5, 120)
    
    df = pd.DataFrame({
        'crop': selected_crops,
        'maturity': np.round(maturity, 1),
        'temperature': np.round(temperature, 1),
        'humidity': np.round(humidity, 1),
        'rain_probability': np.round(rain_probability, 1),
        'storage_duration': np.round(storage_duration, 1),
        'transport_duration': np.round(transport_duration, 1),
        'ambient_storage': ambient_storage,
        'current_price': np.round(current_price, 1),
        'future_price': np.round(future_price, 1),
        'spoilage_pct': np.round(spoilage_pct, 2)
    })
    
    return df

def train_and_save_model():
    print("Generating synthetic data for training...")
    df = generate_synthetic_dataset(1200)
    
    # Make sure output directories exist
    os.makedirs('data', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    
    # Save the synthetic training data
    df.to_csv('data/synthetic_data.csv', index=False)
    print("Synthetic dataset saved to data/synthetic_data.csv")
    
    # Features & target
    X = df[['maturity', 'temperature', 'humidity', 'rain_probability', 
            'storage_duration', 'transport_duration', 'ambient_storage']]
    y = df['spoilage_pct']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train Linear Regression model for interpretability
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # Evaluate
    preds = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)
    
    print(f"Model Training Complete.")
    print(f"RMSE: {rmse:.4f}")
    print(f"R² Score: {r2:.4f}")
    print("Coefficients:")
    for col, coef in zip(X.columns, model.coef_):
        print(f"  {col}: {coef:.4f}")
    print(f"  Intercept: {model.intercept_:.4f}")
    
    # Save model artifacts
    model_data = {
        'model': model,
        'features': list(X.columns),
        'coef': list(model.coef_),
        'intercept': float(model.intercept_)
    }
    
    joblib.dump(model_data, 'models/spoilage_model.joblib')
    print("Model saved to models/spoilage_model.joblib")

if __name__ == '__main__':
    train_and_save_model()
