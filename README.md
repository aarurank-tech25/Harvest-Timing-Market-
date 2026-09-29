# Harvest Timing & Market Option Simulator

A complete, production-ready decision-support system built for small and medium farmers to optimize harvest timing and choose the best market/buyer options by balancing expected market prices against environmental spoilage risks and logistics overheads.

---

## Features

- **Dynamic Harvest Timing (Day 0–10)**: Algorithmically evaluates all 11 candidate harvest horizons and recommends the day that maximises net farmer value — no hard-coded advice.
- **4-Tier Market Channel Optimization**: Compares Local Mandi, Regional Wholesale APMC, Direct/Premium Buyer, and Farm-Gate Distress Sale. The recommended channel is selected from actual calculated farmer value.
- **Multi-Plot Farm Simulation**: Manage a portfolio of independent plots — each receives its own harvest timing, spoilage risk, and market recommendation.
- **Live Market Data**: Integrates with Agmarknet/e-NAM for live commodity prices. Falls back transparently: LIVE → CACHED → FALLBACK.
- **Live Weather + GPS**: Fetches real-time agro-weather data from Open-Meteo. GPS optional, with manual district selector. Falls back: LIVE → CACHED → DISTRICT PRESET.
- **Offline-First**: Core simulation, market logic, and sensitivity analysis are fully replicated in the browser (JavaScript). The app works with zero internet.
- **Multilingual: English, Tamil (தமிழ்), and Hindi (हिंदी)**: All UI elements, recommendations, warnings, risk levels, and explanations are fully translated.
- **Sensitivity Analysis**: Sweeps 7 parameters (future price, temperature, humidity, rain, storage, transport, maturity) to show what drives or changes the recommendation.
- **Explainable Recommendations**: Every recommendation cites the actual calculated price, spoilage %, usable quantity, costs, and expected farmer value.
- **Accessibility**: Semantic HTML5, ARIA roles/labels, keyboard navigation, screen-reader friendly status messages.
- **Edge-Case Handling**: Extreme heat, overmaturity, zero/negative quantity, missing fields, invalid coordinates — all handled gracefully with informative warnings.
- **Production Ready**: Dockerfile, Gunicorn, `/health` endpoint, environment-variable configuration, structured logging.

---

## Project Structure

```
harvest_risk_simulator/
├── app.py                      # Flask API + Web server
├── config.py                   # Environment-variable configuration
├── requirements.txt            # Backend dependencies
├── Dockerfile                  # Production Docker image (Gunicorn)
├── .dockerignore
├── README.md
├── data/
│   └── synthetic_data.csv      # 1,200-record agro-climatic dataset
├── models/
│   ├── train_model.py          # Scikit-learn spoilage model training
│   └── spoilage_model.joblib   # Trained model file
├── simulator/
│   ├── engine.py               # Core simulation engine (Day 0–10, market, sensitivity)
│   ├── market_service.py       # Live market price service (LIVE→CACHED→FALLBACK)
│   └── weather_service.py      # Live weather service + GPS (LIVE→CACHED→FALLBACK)
├── evaluation/
│   └── evaluate.py             # Evaluation pipeline (metrics.json, evaluation_report.md, CSV)
├── tests/
│   ├── test_api.py             # API endpoint tests
│   ├── test_multiplot.py       # Multi-plot simulation tests
│   ├── test_offline.py         # Offline/fallback resilience tests
│   ├── test_services.py        # Market + weather service tests
│   └── test_simulator.py       # Core engine tests
├── templates/
│   └── index.html              # Main dashboard (trilingual, accessible)
├── static/
│   ├── css/style.css
│   └── js/app.js               # Frontend logic + offline simulation replica
└── reports/
    ├── evaluation_report.md    # Full evaluation report
    ├── metrics.json            # Compiled evaluation metrics
    └── evaluation_results.csv # Per-case evaluation data
```

---

## Setup & Running Locally

### 1. Requirements

Python 3.10+ required.

### 2. Installation

```powershell
cd harvest_risk_simulator
pip install -r requirements.txt
```

### 3. (Optional) Train Model & Evaluate

```powershell
python models/train_model.py
python evaluation/evaluate.py
```

The model is automatically trained on first run if not found.

### 4. Run Development Server

```powershell
python app.py
```

Open: **`http://localhost:5000`**

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `GET /health` | GET | Health check — returns `{"status": "ok"}` |
| `POST /api/simulate` | POST | Single-plot simulation |
| `POST /api/simulate-multiple` | POST | Multi-plot simulation (strict validation) |
| `POST /api/simulate-multi` | POST | Multi-plot simulation (legacy) |
| `GET /api/market-price` | GET | Live/cached/fallback market price |
| `GET /api/weather` | GET | Live/cached/fallback weather |
| `GET /api/metrics` | GET | Evaluation metrics |
| `POST /api/train` | POST | Retrain spoilage model |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `harvest-risk-sim-secret-key-2026` | Flask secret key |
| `DEBUG` | `False` | Debug mode |
| `PORT` | `5000` | Server port |
| `HOST` | `0.0.0.0` | Bind address |
| `MARKET_API_URL` | Agmarknet endpoint | Live market price API URL |
| `MARKET_API_KEY` | *(empty)* | API key for market price service |
| `MARKET_TIMEOUT` | `3.0` | Market API timeout (seconds) |
| `WEATHER_API_URL` | Open-Meteo endpoint | Live weather API URL |
| `WEATHER_TIMEOUT` | `3.0` | Weather API timeout (seconds) |
| `CACHE_TTL_MARKET` | `3600` | Market cache lifetime (seconds) |
| `CACHE_TTL_WEATHER` | `1800` | Weather cache lifetime (seconds) |

---

## Production Deployment

### Docker

```bash
docker build -t harvest-sim .
docker run -p 5000:5000 \
  -e MARKET_API_KEY=your_key \
  -e SECRET_KEY=your_secret \
  harvest-sim
```

### Gunicorn (direct)

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 4 app:app
```

### Health Check

```bash
curl http://localhost:5000/health
# {"status": "ok", "service": "Harvest Timing & Market Option Simulator", "version": "1.1.0", ...}
```

---

## Running Tests

```powershell
python -m unittest discover -s tests -v
```

Expected: **42 tests, 0 failures**.

---

## Offline Mode

The simulator works completely offline:

- Browser-side JS replicates the entire Python spoilage model, 11-horizon optimizer, and 4-tier market engine.
- Chart.js is vendored locally (`static/js/chart.min.js`) — no CDN required.
- Market prices and weather fall back to agronomic baseline presets.
- An orange banner appears when offline mode is active.

---

## Running Evaluation

```powershell
python evaluation/evaluate.py
```

Generates:
- `reports/metrics.json` — aggregate performance metrics
- `reports/evaluation_report.md` — full evaluation report
- `reports/evaluation_results.csv` — per-case results (1,000 rows)

---

## Limitations

- Spoilage model trained on synthetic dataset; real-world calibration with farmer data is pending.
- Market price API (Agmarknet/e-NAM) requires a government API key for live data; fallback prices are agronomic baselines.
- Weather forecast uses Open-Meteo free tier (no key required) with a 3-second timeout.
- Multi-plot simulation does not persist to a database; plots are saved to browser `localStorage`.
- Real-world farmer/stakeholder validation is pending.

---

## Responsible AI

- All model coefficients and decision logic are fully transparent and auditable.
- The system never fabricates data — fallback data is always labelled `source: "fallback"`.
- Hindi, Tamil, and English support ensures the tool is usable by a broader rural population.
- An ethics/disclosure panel is accessible from the dashboard.
