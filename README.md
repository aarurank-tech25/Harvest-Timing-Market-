# Harvest Timing & Market Option Simulator

**Checkpoint Status:** 70% AI-Review-Ready Checkpoint  
**Validation Status:** Synthetic Simulation Evaluation (Pending Real-World Field Validation)  

A field-friendly decision-support system built for smallholder and medium-scale farmers to optimize harvest timing and choose the best route/buyer options by balancing expected market prices against environmental spoilage risks and storage/transportation overheads.

---

## Key Features

1. **Full Day 0 → Day 10 Harvest Simulation**:
   - Evaluates daily crop maturity, price gradient, spoilage risk, storage costs, and transport costs for every day from Day 0 (Immediate Harvest) to Day 10.
   - Automatically identifies the optimal harvest day $t^*$ that maximizes Expected Farmer Value (EFV).

2. **Strict Baseline Comparison**:
   - Benchmarked against **Immediate Harvest (Day 0)**.
   - Measures net farmer value improvement (₹ and %), spoilage difference, and usable quantity comparison.

3. **Three Practical Market Options**:
   - **Local Market**: Low travel time (0.5–1 hr), standard local price (0.90x), minimal transit spoilage.
   - **Wholesale Market (District Mandi)**: Benchmark price (1.00x), standard APMC transit (2–3 hrs).
   - **Direct / Premium Market (Retail/Exporter)**: Premium price (+30%), longer travel (5–8 hrs), transit stress penalty.

4. **Transparent Mathematical Formulas**:
   - Every metric is computed dynamically from documented decay and logistics equations—no hard-coded numbers.

5. **Sensitivity Analysis & Decision Flip Identification**:
   - Sweeps future price, temperature, spoilage rates, and storage/transport durations.
   - Dynamically highlights **which assumptions flip the final recommendation** (e.g., *Future price -10% flips decision from Day 3 to Day 0*).

6. **Edge Cases & Failure Recovery**:
   - Extreme heat (45°C) + price surge -> protects farmers by recommending immediate Day 0 harvest.
   - Long storage (14d) / transit (24h) -> identifies loss thresholds.
   - Missing weather or price data -> activates regional historical fallbacks and warns the user without crashing (*"Fallback data is being used for missing parameters."*).
   - Bounds safety: zero quantity, negative price, and overripe maturity (>100%) handled cleanly.

7. **100% Offline & Low-Bandwidth Capability**:
   - Zero remote CDN dependencies (`chart.min.js` bundled locally).
   - Full simulation engine implemented in vanilla JavaScript in `static/js/app.js` mirroring the Python backend.
   - Browser `LocalStorage` saves calculations locally.

8. **Bilingual (English / தமிழ்)**:
   - Complete 1-click toggle between English and Tamil across all inputs, tables, chart labels, and quantitative explanations.

---

## Mathematical Formulation

$$\begin{aligned}
\text{Usable Quantity}_t &= \text{Quantity} \times \left(1 - \frac{S_t}{100}\right) \\
\text{Gross Revenue}_t &= \text{Usable Quantity}_t \times P_t \\
\text{Storage Cost}_t &= \text{Quantity} \times S_d \times \text{Rate}_{store} \\
\text{Transport Cost}_t &= \text{Quantity} \times T_d \times \text{Rate}_{trans} \\
\text{Handling Cost}_t &= (\text{Quantity} \times ₹0.20) + (t \times ₹0.15 \times \text{Quantity}) \\
\mathbf{\text{Expected Farmer Value}_t} &= \mathbf{\text{Gross Revenue}_t - \text{Storage Cost}_t - \text{Transport Cost}_t - \text{Handling Cost}_t}
\end{aligned}$$

Where:
- Spoilage $S_t$ is estimated using trained regression coefficients with non-linear penalties for extreme heat ($>38^\circ\text{C}$), high humidity ($>70\%$), precipitation ($>75\%$), overripe maturity ($M_t \ge 100\%$), and transit stress ($T_d > 12\text{h}$).
- Optimal Harvest Day: $t^* = \arg\max_{t \in [0, 10]} \text{Expected Farmer Value}_t$.

---

## Project Structure

```
Harvest Timing Market Option Simulator/
├── app.py                     # Flask web app and simulation REST API
├── simulator/
│   └── engine.py              # Core simulation engine (Day 0-10, Baseline, Markets, Sensitivity)
├── models/
│   ├── train_model.py         # Model training script for Linear Regression spoilage weights
│   └── spoilage_model.joblib  # Calibrated model weights
├── evaluation/
│   └── evaluate.py            # Evaluation script running 800 synthetic cases
├── reports/
│   ├── evaluation_report.md   # Comprehensive 18-section technical evaluation report
│   └── metrics.json           # Validation metrics
├── static/
│   ├── css/
│   │   └── style.css          # High-contrast, responsive, accessible CSS
│   └── js/
│       ├── app.js             # Interactive UI logic & client-side offline calculation engine
│       └── chart.min.js       # Bundled local Chart.js (offline ready)
├── templates/
│   └── index.html             # Accessible, bilingual (EN/TA) dashboard template
├── test_scenarios.py          # Automated verification script for the 3 operating scenarios
├── test_edge_cases.py         # Automated verification script for the 4 edge cases
└── test_flask_api.py          # Automated verification script for Flask endpoints
```

---

## Setup & Running Locally

### 1. Requirements
- Python 3.10+ (tested on Python 3.13)
- Required packages: `flask`, `numpy`, `pandas`, `scikit-learn`, `joblib`

### 2. Run the Verification Tests
Verify all scenarios, edge cases, and endpoints:
```powershell
python test_scenarios.py
python test_edge_cases.py
python test_flask_api.py
```

### 3. Run Synthetic Evaluation
Run the 800-record synthetic evaluation:
```powershell
python evaluation/evaluate.py
```

### 4. Start the Application
```powershell
python app.py
```
Open your browser and navigate to:
**`http://localhost:5000`**

---

## Verification Results Summary (70% Checkpoint)

| Requirement | Implementation Status | Verified Output |
| :--- | :---: | :--- |
| **Day 0-10 Simulation** | Complete | Computes daily price, maturity, spoilage, costs & EFV for Days 0–10. |
| **Baseline Comparison** | Complete | Baseline = Day 0 Immediate Harvest. Evaluated across 800 cases (+21.23% avg gain). |
| **3 Operating Scenarios** | Complete | Scenario 1 (Day 3, EFV ₹22,194.91); Scenario 2 (Day 0, EFV ₹3,119.29); Scenario 3 (Day 10, EFV ₹51,169.00). |
| **3 Market Channels** | Complete | Local Market, Wholesale Mandi, Direct/Premium Market with cost breakdowns. |
| **Sensitivity Analysis** | Complete | Future price, spoilage multiplier, temp, storage sweeps with dynamic flip point alerts. |
| **Edge Cases & Fallbacks** | Complete | 4 edge cases tested: Extreme heat, long transit, missing data fallback, negative bounds. |
| **Offline Mode** | Complete | 100% offline client-side JS calculation with bundled local Chart.js. |
| **Bilingual Support** | Complete | Full English / Tamil toggle for all inputs, results, and explanations. |
| **Evaluation Report** | Complete | `reports/evaluation_report.md` covering all 18 mandatory sections. |

---

## Remaining Scope for Final 30%

The following advanced or non-critical features are intentionally reserved for the final 30% phase:
1. Real-time Agmarknet API integration for live mandi commodity spot prices.
2. OpenWeatherMap / IMD live meteorological forecast ingestion.
3. Multi-crop mixed basket portfolio optimization.
4. Production containerization (Docker, Nginx/Gunicorn production harness).
5. Physical field trial validation with farmer cooperative societies.
