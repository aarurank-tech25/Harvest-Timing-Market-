// =========================================================================
// Harvest Timing & Market Option Simulator - Frontend Logic
// Production & Offline-First Implementation (English / Tamil / Hindi)
// =========================================================================

// Global App State
let currentLang = 'en';
let isOffline = !navigator.onLine;
let charts = {};
let currentSimulationData = null;

// Offline ML & Agronomic Model (Synchronized with Python SpoilageSimulator)
const OFFLINE_MODEL = {
    intercept: -34.6903,
    coef: {
        maturity: 0.1594,
        temperature: 0.4834,
        humidity: 0.1073,
        rain_probability: 0.0525,
        storage_duration: 1.1749,
        transport_duration: 0.2718,
        ambient_storage: 20.0726
    }
};

// Default Multi-Plot Farm Portfolio
let farmPlots = [
    { id: 'plot-1', name: 'Plot 1 - North Orchard', crop: 'Tomato', quantity: 1000, maturity: 70, temperature: 25, humidity: 55, rain_probability: 10, storage_duration: 2, transport_duration: 2, storage_condition: 'Ambient', current_price: 30, future_price: 35 },
    { id: 'plot-2', name: 'Plot 2 - Ridge Valley', crop: 'Onion', quantity: 750, maturity: 45, temperature: 27, humidity: 50, rain_probability: 5, storage_duration: 4, transport_duration: 3, storage_condition: 'Ambient', current_price: 28, future_price: 32 },
    { id: 'plot-3', name: 'Plot 3 - Canal Field', crop: 'Tomato', quantity: 500, maturity: 85, temperature: 28, humidity: 65, rain_probability: 20, storage_duration: 1, transport_duration: 1, storage_condition: 'Cold Storage', current_price: 30, future_price: 38 }
];

// Initial Setup on Load
document.addEventListener('DOMContentLoaded', () => {
    // Value label listeners
    ['maturity', 'temperature', 'humidity', 'rain_probability', 'storage_duration', 'transport_duration'].forEach(id => {
        updateVal(id);
    });

    // Online / Offline Listeners
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus();

    // Select Scenario 1 by default
    selectScenario(1);

    // Load farm plots from LocalStorage if present
    loadFarmPlotsFromStorage();

    // Load saved calculations
    loadSavedCalculations();

    // Fetch initial weather & price if online
    if (!isOffline) {
        updateDistrictWeather();
        refreshMarketPrice();
    }

    // Initial multi-plot calculation
    runMultiPlotSimulation();
});

// -------------------------------------------------------------------------
// Sliders & UI Controls
// -------------------------------------------------------------------------
function updateVal(id) {
    const input = document.getElementById(id);
    const display = document.getElementById(`${id}-val`);
    if (!input || !display) return;
    
    let suffix = '';
    if (id === 'maturity' || id === 'humidity' || id === 'rain_probability') suffix = '%';
    else if (id === 'temperature') suffix = '°C';
    else if (id === 'storage_duration') {
        const d = parseInt(input.value);
        if (currentLang === 'ta') suffix = d === 1 ? ' நாள்' : ' நாட்கள்';
        else if (currentLang === 'hi') suffix = d === 1 ? ' दिन' : ' दिन';
        else suffix = d === 1 ? ' day' : ' days';
    } else if (id === 'transport_duration') {
        const h = parseInt(input.value);
        if (currentLang === 'ta') suffix = ' மணி';
        else if (currentLang === 'hi') suffix = ' घंटे';
        else suffix = h === 1 ? ' hour' : ' hours';
    }
    
    display.textContent = `${input.value}${suffix}`;
}

function onCropChange() {
    refreshMarketPrice();
}

// -------------------------------------------------------------------------
// Online / Offline Status
// -------------------------------------------------------------------------
function updateOnlineStatus() {
    isOffline = !navigator.onLine;
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');
    const banner = document.getElementById('offline-banner');
    
    if (!isOffline) {
        indicator.className = 'status-badge status-online';
        text.textContent = currentLang === 'ta' ? 'ஆன்லைன்' : (currentLang === 'hi' ? 'ऑनलाइन' : 'ONLINE');
        if (banner) banner.classList.remove('active');
    } else {
        indicator.className = 'status-badge status-offline';
        text.textContent = currentLang === 'ta' ? 'ஆஃப்லைன் — உள்ளமைக்கப்பட்ட தரவு' : (currentLang === 'hi' ? 'ऑफ़लाइन — फ़ॉलबैक डेटा' : 'OFFLINE — USING FALLBACK DATA');
        if (banner) banner.classList.add('active');
    }
}

// -------------------------------------------------------------------------
// Trilingual Support (English, Tamil, Hindi)
// -------------------------------------------------------------------------
function setLanguage(lang) {
    currentLang = lang;
    
    // Update active button state
    ['en', 'ta', 'hi'].forEach(l => {
        const btn = document.getElementById(`btn-lang-${l}`);
        if (btn) {
            if (l === lang) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    });

    translateUI();
}

function translateUI() {
    const elements = document.querySelectorAll(`[data-${currentLang}]`);
    elements.forEach(el => {
        const text = el.getAttribute(`data-${currentLang}`);
        if (text) {
            if (el.tagName === 'OPTION') {
                el.text = text;
            } else {
                el.textContent = text;
            }
        }
    });

    // Update slider label suffixes
    ['maturity', 'temperature', 'humidity', 'rain_probability', 'storage_duration', 'transport_duration'].forEach(id => {
        updateVal(id);
    });

    updateOnlineStatus();

    // Re-render current simulation output in active language
    if (currentSimulationData) {
        renderSimulationResults(currentSimulationData);
    } else {
        runSimulationDynamic(false);
    }

    renderMultiPlotTable(farmPlots);
}

// -------------------------------------------------------------------------
// Live Market Price Integration
// -------------------------------------------------------------------------
async function refreshMarketPrice() {
    const crop = document.getElementById('crop').value;
    const badge = document.getElementById('market-badge');
    const display = document.getElementById('market-price-display');
    const sourceInfo = document.getElementById('market-source-info');

    if (badge) {
        badge.className = 'live-badge badge-cached';
        badge.textContent = 'CHECKING...';
    }

    try {
        const res = await fetch(`/api/market-price?crop=${encodeURIComponent(crop)}`);
        if (!res.ok) throw new Error('API error');
        const data = await res.json();

        if (display) display.textContent = `₹${data.price.toFixed(2)}/kg`;
        if (sourceInfo) sourceInfo.textContent = `(${data.mandi})`;

        if (badge) {
            if (data.source === 'live') {
                badge.className = 'live-badge badge-live';
                badge.textContent = '● LIVE AGMARKNET';
            } else if (data.source === 'cached') {
                badge.className = 'live-badge badge-cached';
                badge.textContent = '● CACHED PRICE';
            } else {
                badge.className = 'live-badge badge-fallback';
                badge.textContent = '● FALLBACK PRICE';
            }
        }

        // Auto-update spot price input field
        const priceInput = document.getElementById('current_price');
        if (priceInput && data.price > 0) {
            priceInput.value = data.price;
        }
    } catch (err) {
        if (badge) {
            badge.className = 'live-badge badge-fallback';
            badge.textContent = '● FALLBACK PRICE';
        }
        if (sourceInfo) sourceInfo.textContent = '(Offline Benchmark)';
    }
}

// -------------------------------------------------------------------------
// Live Weather & Location Integration
// -------------------------------------------------------------------------
async function updateDistrictWeather() {
    const district = document.getElementById('district-selector').value;
    fetchWeatherInternal({ district });
}

function fetchGPSWeather() {
    if (!navigator.geolocation) {
        alert(currentLang === 'ta' ? 'உங்கள் உலாவியில் GPS ஆதரிக்கப்படவில்லை.' : 'GPS is not supported in this browser.');
        return;
    }

    const badge = document.getElementById('weather-badge');
    if (badge) {
        badge.className = 'live-badge badge-cached';
        badge.textContent = 'LOCATING...';
    }

    navigator.geolocation.getCurrentPosition(
        (pos) => {
            fetchWeatherInternal({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
        },
        (err) => {
            console.warn("GPS access denied/unavailable:", err.message);
            updateDistrictWeather(); // Graceful fallback to district
        },
        { timeout: 5000 }
    );
}

async function fetchWeatherInternal(params) {
    const badge = document.getElementById('weather-badge');
    const display = document.getElementById('weather-display');
    const locInfo = document.getElementById('weather-location-info');

    try {
        let url = '/api/weather?';
        if (params.district) url += `district=${encodeURIComponent(params.district)}`;
        else if (params.latitude && params.longitude) url += `lat=${params.latitude}&lon=${params.longitude}`;

        const res = await fetch(url);
        if (!res.ok) throw new Error('Weather API error');
        const data = await res.json();

        if (display) display.textContent = `${data.temperature}°C | ${data.humidity}% RH`;
        if (locInfo && data.location_name) locInfo.textContent = `(${data.location_name})`;

        if (badge) {
            if (data.source === 'live') {
                badge.className = 'live-badge badge-live';
                badge.textContent = '● LIVE WEATHER';
            } else if (data.source === 'cached') {
                badge.className = 'live-badge badge-cached';
                badge.textContent = '● CACHED WEATHER';
            } else {
                badge.className = 'live-badge badge-fallback';
                badge.textContent = '● FALLBACK WEATHER';
            }
        }

        // Auto-populate weather form inputs
        document.getElementById('temperature').value = data.temperature;
        document.getElementById('humidity').value = data.humidity;
        document.getElementById('rain_probability').value = data.rain_probability;
        updateVal('temperature');
        updateVal('humidity');
        updateVal('rain_probability');

    } catch (err) {
        if (badge) {
            badge.className = 'live-badge badge-fallback';
            badge.textContent = '● FALLBACK WEATHER';
        }
        if (locInfo) locInfo.textContent = '(Offline Fallback)';
    }
}

// -------------------------------------------------------------------------
// Tab Switching
// -------------------------------------------------------------------------
function switchTab(tabId, btn) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    const targetTab = document.getElementById(tabId);
    if (targetTab) targetTab.classList.add('active');
    if (btn) btn.classList.add('active');

    // Trigger chart resize if sensitivity tab opened
    if (tabId === 'tab-sensitivity' && currentSimulationData) {
        setTimeout(renderCharts, 100);
    }
}

// -------------------------------------------------------------------------
// Scenario Selector
// -------------------------------------------------------------------------
function selectScenario(scenarioId) {
    const scenarios = {
        1: { maturity: 80, temperature: 24, humidity: 55, rain_probability: 10, current_price: 30, future_price: 35, storage_duration: 2, transport_duration: 2, storage_condition: 'Ambient', weather_condition: 'Sunny' },
        2: { maturity: 95, temperature: 38, humidity: 85, rain_probability: 80, current_price: 30, future_price: 38, storage_duration: 5, transport_duration: 8, storage_condition: 'Ambient', weather_condition: 'Rainy' },
        3: { maturity: 70, temperature: 22, humidity: 40, rain_probability: 5, current_price: 25, future_price: 45, storage_duration: 1, transport_duration: 1, storage_condition: 'Cold Storage', weather_condition: 'Sunny' }
    };
    
    const sc = scenarios[scenarioId];
    if (!sc) return;
    
    const buttons = document.querySelectorAll('.btn-scenario');
    buttons.forEach((btn, idx) => {
        if (idx === scenarioId - 1) btn.classList.add('active');
        else btn.classList.remove('active');
    });

    document.getElementById('maturity').value = sc.maturity;
    document.getElementById('temperature').value = sc.temperature;
    document.getElementById('humidity').value = sc.humidity;
    document.getElementById('rain_probability').value = sc.rain_probability;
    document.getElementById('current_price').value = sc.current_price;
    document.getElementById('future_price').value = sc.future_price;
    document.getElementById('storage_duration').value = sc.storage_duration;
    document.getElementById('transport_duration').value = sc.transport_duration;
    document.getElementById('storage_condition').value = sc.storage_condition;
    document.getElementById('weather_condition').value = sc.weather_condition;

    ['maturity', 'temperature', 'humidity', 'rain_probability', 'storage_duration', 'transport_duration'].forEach(id => {
        updateVal(id);
    });

    runSimulationDynamic();
}

// -------------------------------------------------------------------------
// Simulation Execution (Online API with Full Offline Fallback)
// -------------------------------------------------------------------------
function getFormInputs() {
    return {
        crop: document.getElementById('crop').value,
        maturity: parseFloat(document.getElementById('maturity').value),
        quantity: parseFloat(document.getElementById('quantity').value),
        current_price: parseFloat(document.getElementById('current_price').value),
        future_price: parseFloat(document.getElementById('future_price').value),
        temperature: parseFloat(document.getElementById('temperature').value),
        humidity: parseFloat(document.getElementById('humidity').value),
        rain_probability: parseFloat(document.getElementById('rain_probability').value),
        storage_duration: parseFloat(document.getElementById('storage_duration').value),
        transport_duration: parseFloat(document.getElementById('transport_duration').value),
        storage_condition: document.getElementById('storage_condition').value,
        weather_condition: document.getElementById('weather_condition').value
    };
}

async function runSimulationDynamic(updatePlots = true) {
    const inputs = getFormInputs();

    // Input sanity validations
    if (isNaN(inputs.quantity) || inputs.quantity <= 0) {
        showWarning("Please specify a valid crop quantity (> 0 kg).");
        return;
    }

    try {
        // 1. Attempt Server-side simulation
        const response = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(inputs)
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();
        currentSimulationData = data;
        renderSimulationResults(data);

    } catch (err) {
        console.warn("Backend API unavailable. Executing client-side offline fallback simulation engine:", err.message);
        const offlineData = runOfflineSimulation(inputs);
        currentSimulationData = offlineData;
        renderSimulationResults(offlineData);
    }
}

// -------------------------------------------------------------------------
// Offline Simulation Engine (Client-Side JS Replica)
// -------------------------------------------------------------------------
function runOfflineSimulation(inputs) {
    const mat = Math.max(0, parseFloat(inputs.maturity) || 80);
    const temp = parseFloat(inputs.temperature) || 25;
    const hum = Math.min(100, Math.max(0, parseFloat(inputs.humidity) || 60));
    const rain = Math.min(100, Math.max(0, parseFloat(inputs.rain_probability) || 20));
    const stor = Math.max(0, parseFloat(inputs.storage_duration) || 2);
    const tran = Math.max(0, parseFloat(inputs.transport_duration) || 2);
    const isAmb = inputs.storage_condition === 'Ambient';
    const qty = Math.max(1, parseFloat(inputs.quantity) || 1000);
    const currPrice = Math.max(0, parseFloat(inputs.current_price) || 30);
    const futPrice = Math.max(0, parseFloat(inputs.future_price) || 35);

    function calcSpoilage(m, t, h, r, sd, td, amb) {
        let score = OFFLINE_MODEL.intercept +
            OFFLINE_MODEL.coef.maturity * m +
            OFFLINE_MODEL.coef.temperature * t +
            OFFLINE_MODEL.coef.humidity * h +
            OFFLINE_MODEL.coef.rain_probability * r +
            OFFLINE_MODEL.coef.storage_duration * sd +
            OFFLINE_MODEL.coef.transport_duration * td +
            OFFLINE_MODEL.coef.ambient_storage * (amb ? 1.0 : 0.0);

        let overrides = 0;
        if (m >= 100) overrides += 15.0;
        else if (m >= 95) overrides += 7.5;
        if (t > 40 && h > 75) overrides += 20.0;
        else if (t > 38) overrides += 8.0;
        if (r > 85) overrides += 10.0;
        if (td > 16) overrides += 12.0;
        if (amb && sd > 7) overrides += 15.0;

        return Math.min(100.0, Math.max(0.0, score + overrides));
    }

    function getRisk(s) {
        if (s < 10.0) return 'Low Risk';
        if (s <= 22.0) return 'Medium Risk';
        return 'High Risk';
    }

    const storRate = isAmb ? 0.50 : 1.50;
    const transRate = 0.80;

    // Simulate 11 horizons
    const horizons = [];
    let bestNet = -1e9;
    let bestHorizon = null;

    for (let d = 0; d <= 10; d++) {
        const mat_d = Math.min(110.0, mat + d * 2.5);
        const waitD = stor > 0 ? stor : 5.0;
        const price_d = currPrice + (futPrice - currPrice) * Math.min(1.0, d / waitD);
        const spoil_d = calcSpoilage(mat_d, temp, hum, rain, stor, tran, isAmb);
        const usable_d = qty * (1.0 - spoil_d / 100.0);
        const gross_d = qty * price_d;
        const loss_d = qty * (spoil_d / 100.0) * price_d;
        const netRev_d = usable_d * price_d;
        const storCost_d = qty * stor * storRate;
        const tranCost_d = qty * tran * transRate;
        let fieldRisk_d = 0;
        if (d > 0) {
            fieldRisk_d = qty * (d * 0.15) * (1.0 + rain / 100.0 + Math.max(0, temp - 30) / 20.0);
            if (temp > 40 && hum > 75 && mat >= 90) fieldRisk_d += qty * price_d * (0.30 * d);
        }
        const netVal_d = netRev_d - storCost_d - tranCost_d - fieldRisk_d;

        const hObj = {
            day: d,
            maturity: parseFloat(mat_d.toFixed(1)),
            expected_price: parseFloat(price_d.toFixed(2)),
            spoilage_pct: parseFloat(spoil_d.toFixed(2)),
            usable_qty: parseFloat(usable_d.toFixed(1)),
            gross_revenue: parseFloat(gross_d.toFixed(2)),
            spoilage_loss: parseFloat(loss_d.toFixed(2)),
            net_revenue: parseFloat(netRev_d.toFixed(2)),
            storage_cost: parseFloat(storCost_d.toFixed(2)),
            transport_cost: parseFloat(tranCost_d.toFixed(2)),
            net_farmer_value: parseFloat(netVal_d.toFixed(2)),
            risk_level: getRisk(spoil_d)
        };
        horizons.push(hObj);
        if (netVal_d > bestNet) {
            bestNet = netVal_d;
            bestHorizon = hObj;
        }
    }

    const day0 = horizons[0];
    const optDay = bestHorizon.day;
    const rec = optDay === 0 ? "Harvest Now" : `Wait / Harvest on Day ${optDay}`;
    const recTa = optDay === 0 ? "இப்போது அறுவடை செய்க" : `காத்திருந்து நாள் ${optDay}-ல் அறுவடை செய்க`;
    const recHi = optDay === 0 ? "अभी फसल काटें (दिन 0)" : `प्रतीक्षा करें / दिन ${optDay} पर फसल काटें`;

    // 4 Market Channels
    const mConfigs = [
        { id: 'local', name: 'Local Mandi (Village Market)', name_ta: 'உள்ளூர் சந்தை (கிராம மண்டி)', name_hi: 'स्थानीय मंडी (ग्रामीण बाजार)', mult: 0.85, trans: 1.0, storAdj: 0.8, handle: 0.15, comm: 0.01, dist: 12 },
        { id: 'wholesale', name: 'Regional Wholesale APMC Hub', name_ta: 'பிராந்திய மொத்த விற்பனை APMC மையம்', name_hi: 'क्षेत्रीय थोक APMC मंडी', mult: 1.00, trans: 3.5, storAdj: 1.0, handle: 0.25, comm: 0.02, dist: 55 },
        { id: 'premium', name: 'Direct Retail / Premium Buyer', name_ta: 'நேரடி சில்லறை / பிரீமியம் வாங்குபவர்', name_hi: 'प्रत्यक्ष खुदरा / प्रीमियम खरीदार', mult: 1.25, trans: 7.0, storAdj: 1.5, handle: 0.45, comm: 0.00, dist: 140 },
        { id: 'farm_gate', name: 'Farm-Gate / Distress Sale', name_ta: 'பண்ணை வாசல் / அவசர விற்பனை', name_hi: 'खेत पर बिक्री / संकटकालीन सौदा', mult: 0.70, trans: 0.0, storAdj: 0.0, handle: 0.05, comm: 0.00, dist: 0 }
    ];

    const chosenP = bestHorizon.expected_price;
    const markets = mConfigs.map(m => {
        const mp = parseFloat((chosenP * m.mult).toFixed(2));
        const sp = calcSpoilage(bestHorizon.maturity, temp, hum, rain, stor, m.trans, isAmb);
        const uq = qty * (1.0 - sp / 100.0);
        const gross = qty * mp;
        const loss = qty * (sp / 100.0) * mp;
        const tc = qty * m.trans * transRate;
        const sc = qty * stor * (storRate * m.storAdj);
        const hc = qty * m.handle;
        const comm = gross * m.comm;
        const net = gross - loss - tc - sc - hc - comm;
        return {
            id: m.id,
            name: m.name,
            name_ta: m.name_ta,
            name_hi: m.name_hi,
            price: mp,
            distance_km: m.dist,
            transport_hours: m.trans,
            spoilage_pct: parseFloat(sp.toFixed(2)),
            usable_qty: parseFloat(uq.toFixed(1)),
            gross_revenue: parseFloat(gross.toFixed(2)),
            spoilage_loss: parseFloat(loss.toFixed(2)),
            transport_cost: parseFloat(tc.toFixed(2)),
            storage_cost: parseFloat(sc.toFixed(2)),
            handling_cost: parseFloat(hc.toFixed(2)),
            commission: parseFloat(comm.toFixed(2)),
            expected_market_value: parseFloat(net.toFixed(2)),
            risk_level: getRisk(sp),
            reason: `Price: ₹${mp}/kg | Spoilage: ${sp.toFixed(1)}% | Net: ₹${net.toFixed(2)}`
        };
    });
    markets.sort((a, b) => b.expected_market_value - a.expected_market_value);

    // Baseline calculation
    const baseWaitD = Math.max(1, Math.min(10, Math.round(stor > 0 ? stor : 5.0)));
    const baseDec = futPrice > currPrice ? `Wait (Target Day ${baseWaitD})` : "Harvest Now (Day 0)";
    const baseOutcome = futPrice > currPrice ? horizons[baseWaitD] : day0;
    const valDiff = bestHorizon.net_farmer_value - baseOutcome.net_farmer_value;

    return {
        inputs,
        warnings: [],
        recommendation: rec,
        recommendation_ta: recTa,
        recommendation_hi: recHi,
        recommended_day: optDay,
        confidence_level: Math.abs(valDiff) > 1500 ? "High" : "Medium",
        confidence_desc: "Simulated offline using validated empirical post-harvest equations.",
        confidence_desc_ta: "ஆஃப்லைன் கணிப்பு சமன்பாடுகள் மூலம் கணக்கிடப்பட்டது.",
        confidence_desc_hi: "मान्य कृषि समीकरणों का उपयोग करके ऑफ़लाइन गणना की गई।",
        optimal_horizon: bestHorizon,
        day_0: day0,
        horizons,
        baseline: {
            decision: baseDec,
            net_farmer_value: baseOutcome.net_farmer_value,
            spoilage_pct: baseOutcome.spoilage_pct,
            day: baseOutcome.day
        },
        proposed: {
            decision: rec,
            net_farmer_value: bestHorizon.net_farmer_value,
            spoilage_pct: bestHorizon.spoilage_pct,
            day: optDay
        },
        comparison: {
            value_difference: parseFloat(valDiff.toFixed(2)),
            value_difference_pct: parseFloat(((valDiff / Math.max(1, Math.abs(baseOutcome.net_farmer_value))) * 100).toFixed(2))
        },
        best_market: markets[0],
        market_explanation: `Recommended Market Channel: ${markets[0].name} (Expected Net: ₹${markets[0].expected_market_value.toLocaleString()})`,
        markets,
        explanations: [
            optDay === 0 ? "Immediate harvest avoids on-field weather exposure and high ambient rot." : `Waiting until Day ${optDay} yields higher net return (+₹${valDiff.toFixed(2)}) despite spoilage.`
        ],
        ta_explanations: [
            optDay === 0 ? "இப்போதே அறுவடை செய்வது கள சேதத்தைத் தவிர்க்கிறது." : `நாள் ${optDay} வரை காத்திருப்பது கூடுதல் லாபத்தைத் தருகிறது.`
        ],
        hi_explanations: [
            optDay === 0 ? "तत्काल कटाई मौसम के जोखिम और सड़न से बचाती है।" : `दिन ${optDay} तक प्रतीक्षा करने से अतिरिक्त लाभ होता है।`
        ]
    };
}

// -------------------------------------------------------------------------
// Render Simulation Results to UI
// -------------------------------------------------------------------------
function renderSimulationResults(data) {
    const opt = data.optimal_horizon;
    const day0 = data.day_0;
    const recBox = document.getElementById('recommendation-box');
    const recDecision = document.getElementById('rec-decision');

    // 1. Recommendation Header Banner
    let recText = data.recommendation;
    if (currentLang === 'ta' && data.recommendation_ta) recText = data.recommendation_ta;
    else if (currentLang === 'hi' && data.recommendation_hi) recText = data.recommendation_hi;

    if (recDecision) recDecision.textContent = recText.toUpperCase();
    if (recBox) {
        if (data.recommended_day === 0) {
            recBox.className = 'rec-box harvest';
        } else {
            recBox.className = 'rec-box wait';
        }
    }

    // 2. Metrics Grid
    document.getElementById('metric-net-value').textContent = `₹${opt.net_farmer_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    
    const riskElem = document.getElementById('metric-risk-level');
    let riskText = opt.risk_level;
    if (currentLang === 'ta') riskText = opt.risk_level_ta || (opt.risk_level === 'Low Risk' ? 'குறைந்த அபாயம்' : (opt.risk_level === 'Medium Risk' ? 'நடுத்தர அபாயம்' : 'அதிக அபாயம்'));
    else if (currentLang === 'hi') riskText = opt.risk_level_hi || (opt.risk_level === 'Low Risk' ? 'कम जोखिम' : (opt.risk_level === 'Medium Risk' ? 'मध्यम जोखिम' : 'उच्च जोखिम'));
    
    riskElem.textContent = riskText;
    riskElem.className = `h-metric-val ${opt.risk_level === 'Low Risk' ? 'risk-low' : (opt.risk_level === 'Medium Risk' ? 'risk-med' : 'risk-high')}`;

    document.getElementById('metric-spoilage-pct').textContent = `${opt.spoilage_pct.toFixed(1)}%`;
    document.getElementById('metric-confidence').textContent = data.confidence_level || 'High';

    // 3. Explanation Drivers List
    const expList = document.getElementById('explanation-list');
    expList.innerHTML = '';
    let expItems = data.explanations || [];
    if (currentLang === 'ta' && data.ta_explanations && data.ta_explanations.length) expItems = data.ta_explanations;
    else if (currentLang === 'hi' && data.hi_explanations && data.hi_explanations.length) expItems = data.hi_explanations;

    expItems.forEach(text => {
        const li = document.createElement('li');
        li.textContent = text;
        expList.appendChild(li);
    });

    // 4. Comparison Table (Day 0 vs Recommended Day)
    const thRec = document.getElementById('th-recommended-day');
    if (thRec) {
        const dNum = data.recommended_day;
        if (currentLang === 'ta') thRec.textContent = `பரிந்துரைக்கப்பட்ட நாள் (${dNum})`;
        else if (currentLang === 'hi') thRec.textContent = `अनुशंसित दिन (${dNum})`;
        else thRec.textContent = `Recommended Day (${dNum})`;
    }

    document.getElementById('tbl-price-now').textContent = `₹${day0.expected_price.toFixed(2)}`;
    document.getElementById('tbl-price-wait').textContent = `₹${opt.expected_price.toFixed(2)}`;

    document.getElementById('tbl-spoilage-now').textContent = `${day0.spoilage_pct.toFixed(1)}%`;
    document.getElementById('tbl-spoilage-wait').textContent = `${opt.spoilage_pct.toFixed(1)}%`;

    document.getElementById('tbl-qty-now').textContent = `${day0.usable_qty.toLocaleString()} kg`;
    document.getElementById('tbl-qty-wait').textContent = `${opt.usable_qty.toLocaleString()} kg`;

    document.getElementById('tbl-rev-now').textContent = `₹${day0.gross_revenue.toLocaleString()}`;
    document.getElementById('tbl-rev-wait').textContent = `₹${opt.gross_revenue.toLocaleString()}`;

    document.getElementById('tbl-loss-now').textContent = `-₹${day0.spoilage_loss.toLocaleString()}`;
    document.getElementById('tbl-loss-wait').textContent = `-₹${opt.spoilage_loss.toLocaleString()}`;

    document.getElementById('tbl-store-now').textContent = `₹${day0.storage_cost.toLocaleString()}`;
    document.getElementById('tbl-store-wait').textContent = `₹${opt.storage_cost.toLocaleString()}`;

    document.getElementById('tbl-trans-now').textContent = `₹${day0.transport_cost.toLocaleString()}`;
    document.getElementById('tbl-trans-wait').textContent = `₹${opt.transport_cost.toLocaleString()}`;

    document.getElementById('tbl-net-now').textContent = `₹${day0.net_farmer_value.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    document.getElementById('tbl-net-wait').textContent = `₹${opt.net_farmer_value.toLocaleString(undefined, {minimumFractionDigits: 2})}`;

    // 5. Baseline Comparison Cards
    const baseDecDisplay = document.getElementById('base-decision-display');
    const baseValDisplay = document.getElementById('base-value-display');
    const propDecDisplay = document.getElementById('proposed-decision-display');
    const propValDisplay = document.getElementById('proposed-value-display');
    const impDisplay = document.getElementById('improvement-display');

    if (baseDecDisplay) baseDecDisplay.textContent = data.baseline.decision;
    if (baseValDisplay) baseValDisplay.textContent = `₹${data.baseline.net_farmer_value.toLocaleString()}`;
    if (propDecDisplay) propDecDisplay.textContent = recText;
    if (propValDisplay) propValDisplay.textContent = `₹${data.proposed.net_farmer_value.toLocaleString()}`;

    const diff = data.comparison.value_difference;
    const diffPct = data.comparison.value_difference_pct;
    if (impDisplay) {
        if (diff >= 0) {
            impDisplay.textContent = `+₹${diff.toLocaleString()} (+${diffPct.toFixed(1)}%)`;
            impDisplay.className = 'compare-diff-positive';
        } else {
            impDisplay.textContent = `-₹${Math.abs(diff).toLocaleString()} (${diffPct.toFixed(1)}%)`;
            impDisplay.className = 'compare-diff-negative';
        }
    }

    // 6. 4-Tier Market Channels Rendering
    renderMarketCards(data.markets, data.best_market, data.market_explanation);

    // 7. Render Charts
    renderCharts();

    // 8. Display Warnings if any
    displayWarnings(data.warnings || []);
}

// -------------------------------------------------------------------------
// Render 4 Market Options Cards
// -------------------------------------------------------------------------
function renderMarketCards(markets, bestMarket, marketExplanation) {
    const container = document.getElementById('market-cards-container');
    if (!container) return;
    container.innerHTML = '';

    markets.forEach(m => {
        const isBest = (m.id === bestMarket.id);
        const card = document.createElement('div');
        card.className = `market-card ${isBest ? 'recommended' : ''}`;

        let marketName = m.name;
        if (currentLang === 'ta' && m.name_ta) marketName = m.name_ta;
        else if (currentLang === 'hi' && m.name_hi) marketName = m.name_hi;

        card.innerHTML = `
            <div>
                <div class="market-card-title">${marketName}</div>
                <div class="market-card-price">₹${m.price.toFixed(2)}/kg</div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 8px;">
                    📍 ${m.distance_km} km | ⏱️ ${m.transport_hours}h transit
                </div>
            </div>

            <div class="market-breakdown">
                <div class="market-breakdown-row">
                    <span>${currentLang === 'ta' ? 'அழுகல் இழப்பு' : (currentLang === 'hi' ? 'सड़न हानि' : 'Spoilage Loss')}:</span>
                    <span style="color: var(--danger);">${m.spoilage_pct.toFixed(1)}%</span>
                </div>
                <div class="market-breakdown-row">
                    <span>${currentLang === 'ta' ? 'போக்குவரத்து' : (currentLang === 'hi' ? 'परिवहन लागत' : 'Transport')}:</span>
                    <span>₹${m.transport_cost.toLocaleString()}</span>
                </div>
                <div class="market-breakdown-row">
                    <span>${currentLang === 'ta' ? 'சேமிப்பு' : (currentLang === 'hi' ? 'भंडारण लागत' : 'Storage')}:</span>
                    <span>₹${m.storage_cost.toLocaleString()}</span>
                </div>
                <div class="market-breakdown-row">
                    <span>${currentLang === 'ta' ? 'கையாளுதல் & கட்டணம்' : (currentLang === 'hi' ? 'हैंडलिंग व शुल्क' : 'Handling & Comm.')}:</span>
                    <span>₹${(m.handling_cost + m.commission).toLocaleString()}</span>
                </div>
                <div class="market-breakdown-row net">
                    <span>${currentLang === 'ta' ? 'நிகர மதிப்பு' : (currentLang === 'hi' ? 'शुद्ध किसान मूल्य' : 'Net Farmer Value')}:</span>
                    <span>₹${m.expected_market_value.toLocaleString()}</span>
                </div>
            </div>

            <div style="font-size: 0.78rem; color: var(--text-muted); font-style: italic;">
                ${m.reason || ''}
            </div>
        `;
        container.appendChild(card);
    });

    const expElem = document.getElementById('market-recommendation-note');
    if (expElem) {
        expElem.textContent = marketExplanation || `Best Market Channel: ${bestMarket.name}`;
    }
}

// -------------------------------------------------------------------------
// Sensitivity Charts (Local Chart.js with Graceful Guard)
// -------------------------------------------------------------------------
function renderCharts() {
    if (typeof Chart === 'undefined') {
        console.warn("Chart.js is not loaded. Degrading gracefully without throwing errors.");
        return;
    }

    if (!currentSimulationData || !currentSimulationData.horizons) return;
    const horizons = currentSimulationData.horizons;
    const labels = horizons.map(h => `Day ${h.day}`);

    // Chart 1: Profit vs Spoilage
    renderSingleChart('chart-profit-spoilage', {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: currentLang === 'ta' ? 'நிகர மதிப்பு (₹)' : (currentLang === 'hi' ? 'शुद्ध मूल्य (₹)' : 'Net Value (₹)'),
                    data: horizons.map(h => h.net_farmer_value),
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    yAxisID: 'y'
                },
                {
                    label: currentLang === 'ta' ? 'பயிர் அழுகல் (%)' : (currentLang === 'hi' ? 'खराबी (%)' : 'Spoilage (%)'),
                    data: horizons.map(h => h.spoilage_pct),
                    borderColor: '#f87171',
                    backgroundColor: 'rgba(248, 113, 113, 0.1)',
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { type: 'linear', position: 'left' },
                y1: { type: 'linear', position: 'right', grid: { drawOnChartArea: false } }
            }
        }
    });

    // Chart 2: Net Profit vs Future Price
    const baseP = parseFloat(document.getElementById('current_price').value);
    const priceRange = [-20, -10, 0, 10, 20];
    const priceLabels = priceRange.map(pct => `${pct > 0 ? '+' : ''}${pct}%`);
    const priceValues = priceRange.map(pct => {
        const testP = baseP * (1 + pct / 100);
        return testP * (1000 * (1 - horizons[0].spoilage_pct / 100)) - 1000 * 2 * 0.5 - 1000 * 2 * 0.8;
    });

    renderSingleChart('chart-profit-futureprice', {
        type: 'bar',
        data: {
            labels: priceLabels,
            datasets: [{
                label: currentLang === 'ta' ? 'நிகர லாபம் (₹)' : (currentLang === 'hi' ? 'शुद्ध लाभ (₹)' : 'Net Profit (₹)'),
                data: priceValues,
                backgroundColor: 'rgba(245, 158, 11, 0.7)'
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });

    // Chart 3: Decision vs Maturity — dynamically generated from sensitivity sweep
    const matSweep = (currentSimulationData.sensitivity && currentSimulationData.sensitivity.table)
        ? currentSimulationData.sensitivity.table.filter(r => r.variable === 'Maturity')
        : [];
    const matLabels = matSweep.length > 0
        ? matSweep.map(r => r.change + '%')
        : ['40%', '65%', '80%', '98%'];
    const matDecisions = matSweep.length > 0
        ? matSweep.map(r => r.recommended_day)
        : [0, 0, 0, 0]; // safe fallback: no fake decisions
    renderSingleChart('chart-decision-maturity', {
        type: 'line',
        data: {
            labels: matLabels,
            datasets: [{
                label: currentLang === 'ta' ? 'அறுவடை நாள்' : (currentLang === 'hi' ? 'अनुशंसित कटाई दिन' : 'Recommended Day'),
                data: matDecisions,
                borderColor: '#60a5fa',
                backgroundColor: 'rgba(96, 165, 250, 0.2)',
                stepped: true
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });

    // Chart 4: Profit vs Storage
    const storageDays = [1, 2, 4, 7, 10];
    const storageLabels = storageDays.map(d => `${d}d`);
    const storageValues = storageDays.map(d => {
        const loss = (d * 1.5) * 30 * 10;
        return currentSimulationData.optimal_horizon.net_farmer_value - loss;
    });

    renderSingleChart('chart-profit-storage', {
        type: 'line',
        data: {
            labels: storageLabels,
            datasets: [{
                label: currentLang === 'ta' ? 'சேமிப்பு தாக்க மதிப்பு' : (currentLang === 'hi' ? 'भंडारण मूल्य प्रभाव' : 'Storage Value Impact'),
                data: storageValues,
                borderColor: '#a78bfa',
                backgroundColor: 'rgba(167, 139, 250, 0.1)'
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

function renderSingleChart(canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (charts[canvasId]) {
        charts[canvasId].destroy();
    }

    try {
        charts[canvasId] = new Chart(canvas, config);
    } catch (e) {
        console.warn(`Failed to initialize chart on ${canvasId}:`, e.message);
    }
}

// -------------------------------------------------------------------------
// Multi-Plot Farm Management (Step 4)
// -------------------------------------------------------------------------
function loadFarmPlotsFromStorage() {
    try {
        const stored = localStorage.getItem('harvest_sim_plots');
        if (stored) {
            farmPlots = JSON.parse(stored);
        }
    } catch (e) {
        console.warn("Could not parse farmPlots from LocalStorage.");
    }
    renderMultiPlotTable(farmPlots);
}

function saveFarmPlotsToStorage() {
    try {
        localStorage.setItem('harvest_sim_plots', JSON.stringify(farmPlots));
    } catch (e) {}
}

async function runMultiPlotSimulation() {
    try {
        const res = await fetch('/api/simulate-multi', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plots: farmPlots })
        });

        if (!res.ok) throw new Error("Multi-plot API unavailable");
        const data = await res.json();
        renderMultiPlotResults(data);

    } catch (err) {
        // Client-side offline multi-plot evaluation
        const evaluated = farmPlots.map(p => {
            const sim = runOfflineSimulation(p);
            return {
                id: p.id,
                name: p.name,
                crop: p.crop,
                quantity: p.quantity,
                maturity: p.maturity,
                recommended_day: sim.recommended_day,
                recommendation: sim.recommendation,
                recommendation_ta: sim.recommendation_ta,
                recommendation_hi: sim.recommendation_hi,
                recommended_market: sim.best_market.name,
                recommended_market_ta: sim.best_market.name_ta,
                recommended_market_hi: sim.best_market.name_hi,
                expected_farmer_value: sim.proposed.net_farmer_value,
                spoilage_pct: sim.proposed.spoilage_pct,
                spoilage_risk: sim.optimal_horizon.risk_level
            };
        });

        const totalQty = evaluated.reduce((s, p) => s + p.quantity, 0);
        const totalVal = evaluated.reduce((s, p) => s + p.expected_farmer_value, 0);
        const avgSpoil = evaluated.reduce((s, p) => s + p.spoilage_pct * p.quantity, 0) / Math.max(1, totalQty);

        renderMultiPlotResults({
            plots: evaluated,
            summary: {
                total_plots: evaluated.length,
                total_quantity_kg: totalQty,
                total_expected_value: totalVal,
                average_spoilage_pct: parseFloat(avgSpoil.toFixed(1))
            }
        });
    }
}

function renderMultiPlotResults(data) {
    const s = data.summary;
    if (s) {
        document.getElementById('plot-stat-count').textContent = s.total_plots;
        document.getElementById('plot-stat-quantity').textContent = `${s.total_quantity_kg.toLocaleString()} kg`;
        document.getElementById('plot-stat-value').textContent = `₹${s.total_expected_value.toLocaleString(undefined, {maximumFractionDigits: 0})}`;
        document.getElementById('plot-stat-spoilage').textContent = `${s.average_spoilage_pct.toFixed(1)}%`;
    }
    renderMultiPlotTable(data.plots);
}

function renderMultiPlotTable(plots) {
    const tbody = document.getElementById('multiplot-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    plots.forEach(p => {
        const tr = document.createElement('tr');
        
        let recText = p.recommendation || `Day ${p.recommended_day}`;
        if (currentLang === 'ta' && p.recommendation_ta) recText = p.recommendation_ta;
        else if (currentLang === 'hi' && p.recommendation_hi) recText = p.recommendation_hi;

        let marketText = p.recommended_market || 'APMC Hub';
        if (currentLang === 'ta' && p.recommended_market_ta) marketText = p.recommended_market_ta;
        else if (currentLang === 'hi' && p.recommended_market_hi) marketText = p.recommended_market_hi;

        tr.innerHTML = `
            <td style="font-weight: 600;">${p.name}</td>
            <td>${p.crop}</td>
            <td>${p.quantity} kg</td>
            <td>${p.maturity}%</td>
            <td style="font-weight: 700; color: ${p.recommended_day === 0 ? 'var(--danger)' : 'var(--primary-color)'};">
                ${recText}
            </td>
            <td>${marketText}</td>
            <td style="font-weight: 700; color: var(--success);">₹${(p.expected_farmer_value || 0).toLocaleString()}</td>
            <td>
                <span class="live-badge ${p.spoilage_risk === 'Low Risk' ? 'badge-live' : (p.spoilage_risk === 'Medium Risk' ? 'badge-cached' : 'badge-fallback')}">
                    ${p.spoilage_risk || 'Normal'}
                </span>
            </td>
            <td>
                <button class="plot-action-btn" onclick="inspectPlot('${p.id}')">Inspect</button>
                <button class="plot-action-btn plot-delete-btn" onclick="deletePlot('${p.id}')">✕</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function inspectPlot(plotId) {
    const plot = farmPlots.find(p => p.id === plotId);
    if (!plot) return;

    // Populate main form
    document.getElementById('crop').value = plot.crop || 'Tomato';
    document.getElementById('maturity').value = plot.maturity || 80;
    document.getElementById('quantity').value = plot.quantity || 1000;
    document.getElementById('current_price').value = plot.current_price || 30;
    document.getElementById('future_price').value = plot.future_price || 35;
    document.getElementById('temperature').value = plot.temperature || 25;
    document.getElementById('humidity').value = plot.humidity || 60;
    document.getElementById('rain_probability').value = plot.rain_probability || 20;
    document.getElementById('storage_duration').value = plot.storage_duration || 2;
    document.getElementById('transport_duration').value = plot.transport_duration || 2;
    document.getElementById('storage_condition').value = plot.storage_condition || 'Ambient';

    ['maturity', 'temperature', 'humidity', 'rain_probability', 'storage_duration', 'transport_duration'].forEach(id => {
        updateVal(id);
    });

    // Switch to Decision Dashboard tab
    const dashBtn = document.querySelector('.tab-btn[aria-controls="tab-dashboard"]');
    switchTab('tab-dashboard', dashBtn);

    runSimulationDynamic();
}

function deletePlot(plotId) {
    if (farmPlots.length <= 1) {
        alert(currentLang === 'ta' ? 'குறைந்தது ஒரு நிலமாவது இருக்க வேண்டும்.' : 'At least one plot must remain in the farm.');
        return;
    }
    farmPlots = farmPlots.filter(p => p.id !== plotId);
    saveFarmPlotsToStorage();
    runMultiPlotSimulation();
}

function addNewPlotPrompt() {
    const plotNum = farmPlots.length + 1;
    const name = prompt(currentLang === 'ta' ? 'நிலத்தின் பெயர்:' : 'Enter Plot Name:', `Plot ${plotNum}`);
    if (!name) return;

    const crop = prompt(currentLang === 'ta' ? 'பயிர் (Tomato/Potato/Onion/Rice/Mango):' : 'Enter Crop (Tomato/Potato/Onion/Rice/Mango):', 'Tomato') || 'Tomato';
    const qty = parseFloat(prompt(currentLang === 'ta' ? 'அளவு (கிலோ):' : 'Enter Quantity (kg):', '1000')) || 1000;
    const mat = parseFloat(prompt(currentLang === 'ta' ? 'முதிர்ச்சி (%):' : 'Enter Maturity (%):', '75')) || 75;

    farmPlots.push({
        id: `plot-${Date.now()}`,
        name: name,
        crop: crop,
        quantity: qty,
        maturity: mat,
        temperature: 26,
        humidity: 60,
        rain_probability: 15,
        storage_duration: 2,
        transport_duration: 2,
        storage_condition: 'Ambient',
        current_price: 30,
        future_price: 35
    });

    saveFarmPlotsToStorage();
    runMultiPlotSimulation();
}

function loadDefaultPlotDemo() {
    farmPlots = [
        { id: 'plot-1', name: 'Plot 1 - North Orchard', crop: 'Tomato', quantity: 1000, maturity: 70, temperature: 25, humidity: 55, rain_probability: 10, storage_duration: 2, transport_duration: 2, storage_condition: 'Ambient', current_price: 30, future_price: 35 },
        { id: 'plot-2', name: 'Plot 2 - Ridge Valley', crop: 'Onion', quantity: 750, maturity: 45, temperature: 27, humidity: 50, rain_probability: 5, storage_duration: 4, transport_duration: 3, storage_condition: 'Ambient', current_price: 28, future_price: 32 },
        { id: 'plot-3', name: 'Plot 3 - Canal Field', crop: 'Tomato', quantity: 500, maturity: 85, temperature: 28, humidity: 65, rain_probability: 20, storage_duration: 1, transport_duration: 1, storage_condition: 'Cold Storage', current_price: 30, future_price: 38 }
    ];
    saveFarmPlotsToStorage();
    runMultiPlotSimulation();
}

// -------------------------------------------------------------------------
// Offline Storage of Individual Calculations
// -------------------------------------------------------------------------
function saveCalculationLocally() {
    if (!currentSimulationData) return;
    const history = JSON.parse(localStorage.getItem('harvest_sim_saved') || '[]');
    const inputs = getFormInputs();
    const entry = {
        timestamp: new Date().toLocaleTimeString(),
        crop: inputs.crop,
        quantity: inputs.quantity,
        recommendation: currentSimulationData.recommendation,
        net_value: currentSimulationData.optimal_horizon.net_farmer_value
    };
    history.unshift(entry);
    if (history.length > 5) history.pop();
    localStorage.setItem('harvest_sim_saved', JSON.stringify(history));
    loadSavedCalculations();
}

function loadSavedCalculations() {
    const list = document.getElementById('saved-calculations-list');
    if (!list) return;
    const history = JSON.parse(localStorage.getItem('harvest_sim_saved') || '[]');
    if (history.length === 0) {
        list.innerHTML = `<li style="color: var(--text-muted);">${currentLang === 'ta' ? 'உள்ளூர் சேமிப்புகள் எதுவும் இல்லை.' : (currentLang === 'hi' ? 'कोई गणना सहेजी नहीं गई है।' : 'No calculations saved locally yet.')}</li>`;
        return;
    }
    list.innerHTML = '';
    history.forEach(h => {
        const li = document.createElement('li');
        li.style.padding = '6px 0';
        li.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
        li.innerHTML = `<strong>${h.timestamp}</strong> - ${h.crop} (${h.quantity}kg): <span style="color: var(--primary-color);">${h.recommendation}</span> (₹${h.net_value.toLocaleString()})`;
        list.appendChild(li);
    });
}

// -------------------------------------------------------------------------
// Warnings & Alerts
// -------------------------------------------------------------------------
function displayWarnings(warnings) {
    const container = document.getElementById('warning-container');
    if (!container) return;
    if (!warnings || warnings.length === 0) {
        container.style.display = 'none';
        container.innerHTML = '';
        return;
    }

    container.style.display = 'block';
    container.innerHTML = '';
    warnings.forEach(w => {
        const div = document.createElement('div');
        div.className = 'alert alert-warning';
        div.textContent = w;
        container.appendChild(div);
    });
}

function showWarning(msg) {
    displayWarnings([msg]);
}

// -------------------------------------------------------------------------
// Server Evaluation Metrics Loader
// -------------------------------------------------------------------------
async function loadEvaluationMetrics() {
    try {
        const res = await fetch('/api/metrics');
        if (!res.ok) return;
        const m = await res.json();
        const baseAcc = document.getElementById('eval-base-acc');
        const propAcc = document.getElementById('eval-proposed-acc');
        const baseVal = document.getElementById('eval-base-val');
        const propVal = document.getElementById('eval-proposed-val');
        const baseSpoil = document.getElementById('eval-base-spoil');
        const propSpoil = document.getElementById('eval-proposed-spoil');

        if (baseAcc) baseAcc.textContent = `${m.baseline_accuracy.toFixed(1)}%`;
        if (propAcc) propAcc.textContent = `${m.proposed_accuracy.toFixed(1)}%`;
        if (baseVal) baseVal.textContent = `₹${m.baseline_value.toLocaleString()}`;
        if (propVal) propVal.textContent = `₹${m.proposed_value.toLocaleString()}`;
        if (baseSpoil) baseSpoil.textContent = `${m.baseline_spoilage.toFixed(1)}%`;
        if (propSpoil) propSpoil.textContent = `${m.proposed_spoilage.toFixed(1)}%`;
    } catch (e) {}
}
