// ===================================================================
// Harvest Timing & Market Option Simulator - Frontend Logic
// Full Day 0-10 Simulation, Baseline Comparison, 3 Markets,
// Sensitivity Flip Points, Edge Cases, Bilingual (EN/TA), and 100% Offline
// ===================================================================

let currentLang = 'en';
let isOffline = !navigator.onLine;
let activeCharts = {};
let latestSimulationResult = null;

// Offline coefficients matching trained Linear Regression model
const OFFLINE_COEF = {
    maturity: 0.0642,
    temperature: 0.2561,
    humidity: 0.0427,
    rain_probability: 0.0602,
    storage_duration: 0.9711,
    transport_duration: 0.2670,
    ambient_storage: 18.5839,
    intercept: -19.8232
};

const CROP_FACTORS = {
    'Tomato': 1.15,
    'Potato': 0.65,
    'Onion': 0.55,
    'Rice': 0.35,
    'Mango': 1.10
};

const CROP_GROWTH_RATES = {
    'Tomato': 2.8,
    'Potato': 1.5,
    'Onion': 1.2,
    'Rice': 1.0,
    'Mango': 2.5
};

// Initial setup on load
document.addEventListener('DOMContentLoaded', () => {
    ['maturity', 'temperature', 'humidity', 'rain_probability', 'storage_duration', 'transport_duration'].forEach(id => {
        updateVal(id);
    });

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus();

    loadSavedCalculations();
    loadEvaluationMetrics();

    // Default to Scenario 1
    selectScenario(1);
});

// Update slider value labels
function updateVal(id) {
    const input = document.getElementById(id);
    const display = document.getElementById(`${id}-val`);
    if (!input || !display) return;
    
    let suffix = '';
    if (id === 'maturity' || id === 'humidity' || id === 'rain_probability') suffix = '%';
    else if (id === 'temperature') suffix = '°C';
    else if (id === 'storage_duration') suffix = parseInt(input.value) === 1 ? ' day' : ' days';
    else if (id === 'transport_duration') suffix = parseInt(input.value) === 1 ? ' hr' : ' hrs';
    
    display.textContent = `${input.value}${suffix}`;
}

// Online / Offline status badge
function updateOnlineStatus() {
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');
    if (!indicator || !text) return;
    
    if (navigator.onLine) {
        isOffline = false;
        indicator.className = 'status-badge status-online';
        text.setAttribute('data-en', 'Online Mode');
        text.setAttribute('data-ta', 'ஆன்லைன் பயன்முறை');
    } else {
        isOffline = true;
        indicator.className = 'status-badge status-offline';
        text.setAttribute('data-en', 'Offline Mode (Local Engine)');
        text.setAttribute('data-ta', 'ஆஃப்லைன் (உள்ளூர் கால்குலேட்டர்)');
    }
    translateUI();
}

// Toggle language EN <-> TA
function toggleLanguage() {
    currentLang = currentLang === 'en' ? 'ta' : 'en';
    translateUI();
    if (latestSimulationResult) {
        renderSimulationResults(latestSimulationResult);
    }
}

function translateUI() {
    const elements = document.querySelectorAll('[data-en]');
    elements.forEach(el => {
        const text = el.getAttribute(`data-${currentLang}`);
        if (text) {
            if (el.tagName === 'OPTION') {
                el.text = text;
            } else if (el.children.length === 0 || el.classList.contains('rec-title')) {
                el.textContent = text;
            }
        }
    });
}

// Tab navigation
function switchTab(tabId, btn) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
    });

    const targetTab = document.getElementById(tabId);
    if (targetTab) {
        targetTab.classList.add('active');
        btn.classList.add('active');
        btn.setAttribute('aria-selected', 'true');
    }

    // Trigger chart resize if needed
    window.dispatchEvent(new Event('resize'));
}

// Read inputs from form
function getFormData() {
    return {
        crop: document.getElementById('crop').value,
        maturity: parseFloat(document.getElementById('maturity').value),
        quantity: parseFloat(document.getElementById('quantity').value) || 1000,
        current_price: parseFloat(document.getElementById('current_price').value),
        future_price: parseFloat(document.getElementById('future_price').value),
        temperature: parseFloat(document.getElementById('temperature').value),
        humidity: parseFloat(document.getElementById('humidity').value),
        rain_probability: parseFloat(document.getElementById('rain_probability').value),
        storage_duration: parseFloat(document.getElementById('storage_duration').value),
        storage_condition: document.getElementById('storage_condition').value,
        transport_duration: parseFloat(document.getElementById('transport_duration').value)
    };
}

// Priority 4: Select 3 Predefined Scenarios
function selectScenario(scId) {
    const scenarios = {
        1: { crop: 'Tomato', maturity: 80, current_price: 30, future_price: 32, temperature: 24, humidity: 55, rain_probability: 10, storage_duration: 2, transport_duration: 2, storage_condition: 'Ambient' },
        2: { crop: 'Tomato', maturity: 95, current_price: 30, future_price: 38, temperature: 39, humidity: 85, rain_probability: 85, storage_duration: 5, transport_duration: 6, storage_condition: 'Ambient' },
        3: { crop: 'Tomato', maturity: 65, current_price: 25, future_price: 42, temperature: 21, humidity: 45, rain_probability: 5, storage_duration: 2, transport_duration: 1.5, storage_condition: 'Cold Storage' }
    };

    const sc = scenarios[scId];
    if (!sc) return;

    ['btn-sc-1', 'btn-sc-2', 'btn-sc-3'].forEach((id, idx) => {
        const btn = document.getElementById(id);
        if (btn) {
            if (idx === scId - 1) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    });

    populateInputs(sc);
    runSimulationDynamic();
}

// Priority 9: Select 4 Edge Cases
function selectEdgeCase(ecId) {
    const edgeCases = {
        1: { crop: 'Tomato', maturity: 98, current_price: 30, future_price: 60, temperature: 45, humidity: 90, rain_probability: 90, storage_duration: 4, transport_duration: 6, storage_condition: 'Ambient' },
        2: { crop: 'Tomato', maturity: 80, current_price: 30, future_price: 35, temperature: 25, humidity: 60, rain_probability: 20, storage_duration: 14, transport_duration: 24, storage_condition: 'Ambient' },
        3: { crop: 'Tomato', maturity: 75, current_price: '', future_price: '', temperature: '', humidity: '', rain_probability: '', storage_duration: 2, transport_duration: 2, storage_condition: 'Ambient' },
        4: { crop: 'Tomato', maturity: 115, current_price: -10, future_price: -20, quantity: 0, temperature: 25, humidity: 50, rain_probability: 10, storage_duration: 2, transport_duration: 2, storage_condition: 'Ambient' }
    };

    const ec = edgeCases[ecId];
    if (!ec) return;

    populateInputs(ec);
    runSimulationDynamic();
}

function populateInputs(data) {
    if (data.crop !== undefined) document.getElementById('crop').value = data.crop;
    if (data.maturity !== undefined) document.getElementById('maturity').value = data.maturity;
    if (data.quantity !== undefined) document.getElementById('quantity').value = data.quantity;
    if (data.current_price !== undefined) document.getElementById('current_price').value = data.current_price;
    if (data.future_price !== undefined) document.getElementById('future_price').value = data.future_price;
    if (data.temperature !== undefined) document.getElementById('temperature').value = data.temperature;
    if (data.humidity !== undefined) document.getElementById('humidity').value = data.humidity;
    if (data.rain_probability !== undefined) document.getElementById('rain_probability').value = data.rain_probability;
    if (data.storage_duration !== undefined) document.getElementById('storage_duration').value = data.storage_duration;
    if (data.storage_condition !== undefined) document.getElementById('storage_condition').value = data.storage_condition;
    if (data.transport_duration !== undefined) document.getElementById('transport_duration').value = data.transport_duration;

    ['maturity', 'temperature', 'humidity', 'rain_probability', 'storage_duration', 'transport_duration'].forEach(id => {
        updateVal(id);
    });
}

// Dynamic execution: calls Flask API when online, falls back smoothly to offline JS engine
async function runSimulationDynamic() {
    const inputs = getFormData();
    
    // Check missing fields for edge case 3
    const isMissing = isNaN(inputs.current_price) || isNaN(inputs.future_price) || isNaN(inputs.temperature) || isNaN(inputs.humidity) || isNaN(inputs.rain_probability);

    if (navigator.onLine) {
        try {
            const response = await fetch('/api/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(inputs)
            });

            if (response.ok) {
                const data = await response.json();
                latestSimulationResult = data;
                renderSimulationResults(data);
                return;
            }
        } catch (err) {
            console.warn("Online API call failed; switching seamlessly to offline engine.", err);
        }
    }

    // Run client-side offline calculation
    const offlineResult = runOfflineSimulation(inputs);
    latestSimulationResult = offlineResult;
    renderSimulationResults(offlineResult);
}

// -------------------------------------------------------------------
// CLIENT-SIDE OFFLINE SIMULATION ENGINE (100% mirrors Python engine)
// -------------------------------------------------------------------
function predictOfflineSpoilage(maturity, temp, humidity, rainProb, storageDays, transHours, isAmbient, crop, multiplier = 1.0) {
    let raw = (
        OFFLINE_COEF.intercept +
        OFFLINE_COEF.maturity * maturity +
        OFFLINE_COEF.temperature * temp +
        OFFLINE_COEF.humidity * humidity +
        OFFLINE_COEF.rain_probability * rainProb +
        OFFLINE_COEF.storage_duration * storageDays +
        OFFLINE_COEF.transport_duration * transHours +
        OFFLINE_COEF.ambient_storage * (isAmbient ? 1.0 : 0.0)
    );

    if (maturity >= 100) raw += 12.0 + (maturity - 100) * 1.5;
    else if (maturity > 90) raw += (maturity - 90) * 0.8;

    if (temp > 38 && humidity > 70) raw += 15.0;
    else if (temp > 35) raw += 6.0;

    if (rainProb > 75) raw += 8.0;
    if (transHours > 12) raw += 10.0;

    const cropFactor = CROP_FACTORS[crop] || 1.0;
    let finalSpoil = raw * cropFactor * multiplier;

    if (!isAmbient) {
        finalSpoil = Math.max(1.0, finalSpoil * 0.40);
    } else {
        finalSpoil = Math.max(2.5, finalSpoil);
    }

    return Math.min(99.0, Math.max(0.0, finalSpoil));
}

function getRiskLevel(spoilage) {
    if (spoilage < 10.0) return 'Low Risk';
    if (spoilage <= 25.0) return 'Medium Risk';
    return 'High Risk';
}

function runOfflineSimulation(rawInputs) {
    let fallbackUsed = false;
    let warnings = [];

    // Fallback checks
    let crop = rawInputs.crop || 'Tomato';
    let maturity = isNaN(rawInputs.maturity) ? 80 : rawInputs.maturity;
    let quantity = isNaN(rawInputs.quantity) || rawInputs.quantity <= 0 ? 1000 : rawInputs.quantity;
    let currentPrice = isNaN(rawInputs.current_price) ? 30 : rawInputs.current_price;
    let futurePrice = isNaN(rawInputs.future_price) ? 35 : rawInputs.future_price;
    let temp = isNaN(rawInputs.temperature) ? 25 : rawInputs.temperature;
    let humidity = isNaN(rawInputs.humidity) ? 60 : rawInputs.humidity;
    let rainProb = isNaN(rawInputs.rain_probability) ? 20 : rawInputs.rain_probability;
    let storageDays = isNaN(rawInputs.storage_duration) ? 2 : rawInputs.storage_duration;
    let transHours = isNaN(rawInputs.transport_duration) ? 2 : rawInputs.transport_duration;
    let isAmbient = (rawInputs.storage_condition !== 'Cold Storage');

    if (isNaN(rawInputs.temperature) || isNaN(rawInputs.current_price) || isNaN(rawInputs.future_price)) {
        fallbackUsed = true;
        warnings.push("Fallback data is being used for missing parameters.");
    }

    if (currentPrice <= 0) {
        currentPrice = 10.0;
        warnings.push("Current price was zero or negative; reset to ₹10/kg.");
    }
    if (futurePrice <= 0) {
        futurePrice = currentPrice;
        warnings.push("Future price was negative; clamped to current price.");
    }

    const growthRate = CROP_GROWTH_RATES[crop] || 2.0;
    const priceSlope = (futurePrice - currentPrice) / 5.0;

    // Simulate Days 0 to 10
    const timeline = [];
    for (let day = 0; day <= 10; day++) {
        const dayPrice = Math.max(1.0, currentPrice + priceSlope * day);
        const dayMaturity = Math.min(115.0, maturity + day * growthRate);

        let fieldDecay = 0.0;
        if (day > 0) {
            fieldDecay = Math.max(0.0, (dayMaturity - 90) * 0.4) + (rainProb > 60 ? 0.35 * day : 0.12 * day);
        }

        let spoil = predictOfflineSpoilage(dayMaturity, temp, humidity, rainProb, storageDays, transHours, isAmbient, crop);
        spoil = Math.min(99.0, Math.max(0.0, spoil + fieldDecay));

        const usableQty = quantity * (1.0 - spoil / 100.0);
        const grossRev = usableQty * dayPrice;

        const storageRate = isAmbient ? 0.50 : 1.50;
        const storageCost = quantity * storageDays * storageRate;
        const transportCost = quantity * transHours * 0.75;
        const fieldOverhead = day * 0.15 * quantity;
        const handlingCost = (quantity * 0.20) + fieldOverhead;
        const netValue = grossRev - storageCost - transportCost - handlingCost;

        timeline.push({
            day: day,
            price: Math.round(dayPrice * 100) / 100,
            maturity: Math.round(dayMaturity * 10) / 10,
            spoilage_pct: Math.round(spoil * 100) / 100,
            usable_quantity: Math.round(usableQty * 10) / 10,
            gross_revenue: Math.round(grossRev * 100) / 100,
            storage_cost: Math.round(storageCost * 100) / 100,
            transport_cost: Math.round(transportCost * 100) / 100,
            handling_cost: Math.round(handlingCost * 100) / 100,
            expected_farmer_value: Math.round(netValue * 100) / 100,
            risk_level: getRiskLevel(spoil)
        });
    }

    // Optimal day
    let bestDayMetric = timeline[0];
    for (let i = 1; i < timeline.length; i++) {
        if (timeline[i].expected_farmer_value > bestDayMetric.expected_farmer_value) {
            bestDayMetric = timeline[i];
        }
    }
    const recDay = bestDayMetric.day;
    const baselineMetric = timeline[0];

    const valueDiff = Math.round((bestDayMetric.expected_farmer_value - baselineMetric.expected_farmer_value) * 100) / 100;
    const pctImprovement = Math.round((valueDiff / Math.max(1.0, Math.abs(baselineMetric.expected_farmer_value))) * 10000) / 100;
    const spoilDiff = Math.round((bestDayMetric.spoilage_pct - baselineMetric.spoilage_pct) * 100) / 100;

    // 3 Market Options
    const storageRate = isAmbient ? 0.50 : 1.50;
    const storageCost = Math.round(quantity * storageDays * storageRate * 100) / 100;
    const marketConfigs = [
        { key: 'local', name: 'Local Market', name_ta: 'உள்ளூர் சந்தை (Local Mandi)', mult: 0.90, trans: Math.max(0.5, Math.round(transHours * 0.4 * 10) / 10), rate: 0.40, stress: -2.0, desc: 'Quick local village mandi with minimal travel and lowest spoilage risk.' },
        { key: 'wholesale', name: 'Wholesale Market', name_ta: 'மொத்த விற்பனை சந்தை (District Mandi)', mult: 1.00, trans: Math.max(1.5, Math.round(transHours * 1.0 * 10) / 10), rate: 0.75, stress: 0.0, desc: 'Standard APMC district wholesale auction market with standard volume throughput.' },
        { key: 'direct_premium', name: 'Direct / Premium Market', name_ta: 'நேரடி / பிரீமியம் சந்தை (Retail / Exporter)', mult: 1.30, trans: Math.max(5.0, Math.round(transHours * 2.5 * 10) / 10), rate: 1.25, stress: 4.5, desc: 'Direct supermarket procurement or urban export center offering premium rates but requiring long transit.' }
    ];

    const markets = marketConfigs.map(cfg => {
        const mPrice = Math.round(bestDayMetric.price * cfg.mult * 100) / 100;
        let mSpoil = predictOfflineSpoilage(bestDayMetric.maturity, temp, humidity, rainProb, storageDays, cfg.trans, isAmbient, crop);
        mSpoil = Math.min(99.0, Math.max(0.0, mSpoil + cfg.stress));
        const usable = Math.round(quantity * (1.0 - mSpoil / 100.0) * 10) / 10;
        const gross = Math.round(usable * mPrice * 100) / 100;
        const transCost = Math.round(quantity * cfg.trans * cfg.rate * 100) / 100;
        const handling = Math.round(quantity * 0.20 * 100) / 100;
        const net = Math.round((gross - storageCost - transCost - handling) * 100) / 100;

        return {
            key: cfg.key,
            name: cfg.name,
            name_ta: cfg.name_ta,
            price: mPrice,
            transport_hours: cfg.trans,
            transport_cost: transCost,
            storage_cost: storageCost,
            handling_cost: handling,
            spoilage_pct: Math.round(mSpoil * 100) / 100,
            usable_quantity: usable,
            gross_revenue: gross,
            net_farmer_value: net,
            risk_level: getRiskLevel(mSpoil),
            description: cfg.desc
        };
    });

    markets.sort((a, b) => b.net_farmer_value - a.net_farmer_value);
    const bestMarket = markets[0];

    // Sensitivity & Flip points
    const flipPoints = [];
    const flipPointsTa = [];
    const priceSweeps = [-0.2, -0.1, 0, 0.1, 0.2, 0.3];
    const priceCurve = priceSweeps.map(factor => {
        const modFP = Math.round(futurePrice * (1 + factor) * 100) / 100;
        const slope = (modFP - currentPrice) / 5.0;
        let bDay = 0, maxVal = -1e9;
        for (let d = 0; d <= 10; d++) {
            const p = Math.max(1.0, currentPrice + slope * d);
            const m = Math.min(115.0, maturity + d * growthRate);
            const s = predictOfflineSpoilage(m, temp, humidity, rainProb, storageDays, transHours, isAmbient, crop);
            const val = (quantity * (1 - s / 100) * p) - (storageCost + quantity * transHours * 0.75 + quantity * 0.20);
            if (val > maxVal) { maxVal = val; bDay = d; }
        }
        const label = factor === 0 ? '0% (Base)' : `${factor > 0 ? '+' : ''}${Math.round(factor * 100)}%`;
        if (bDay !== recDay) {
            flipPoints.push(`Future price ${label} (₹${modFP}/kg) changes recommendation from Day ${recDay} to Day ${bDay}.`);
            flipPointsTa.push(`எதிர்கால விலை ${label} (₹${modFP}/கிலோ) முடிவை நாள் ${recDay}-லிருந்து நாள் ${bDay}-ஆக மாற்றுகிறது.`);
        }
        return { variation: label, future_price: modFP, recommended_day: bDay, expected_farmer_value: Math.round(maxVal * 100) / 100 };
    });

    // Explanations
    const deltaPrice = Math.round((bestDayMetric.price - baselineMetric.price) * 100) / 100;
    const deltaSpoil = Math.round((bestDayMetric.spoilage_pct - baselineMetric.spoilage_pct) * 100) / 100;
    const deltaVal = Math.round((bestDayMetric.expected_farmer_value - baselineMetric.expected_farmer_value) * 100) / 100;

    const explanations = [];
    const taExplanations = [];

    if (recDay === 0) {
        explanations.push(`Harvest immediately on Day 0 to avoid rapid spoilage and moisture decay on the field.`);
        taExplanations.push(`வயலில் பயிர் விரைவாக அழுகுதல் மற்றும் ஈரப்பத சேதத்தைத் தவிர்க்க உடனடியாக நாள் 0-ல் அறுவடை செய்யவும்.`);
        if (deltaPrice > 0) {
            explanations.push(`Even though future price rises by ₹${deltaPrice}/kg, projected post-harvest decay would erase ₹${Math.abs(deltaVal).toFixed(2)} in net profit.`);
            taExplanations.push(`எதிர்கால விலை ₹${deltaPrice}/கிலோ உயர்ந்தாலும், அழுகல் இழப்பு நிகர லாபத்தில் ₹${Math.abs(deltaVal).toFixed(2)} சேதத்தை ஏற்படுத்தும்.`);
        }
    } else {
        explanations.push(`Recommended harvest on Day ${recDay}: Projected market price reaches ₹${bestDayMetric.price}/kg (+₹${deltaPrice}/kg compared to today).`);
        taExplanations.push(`பரிந்துரைக்கப்பட்ட அறுவடை நாள் ${recDay}: சந்தை விலை ₹${bestDayMetric.price}/கிலோ வரை உயரும் (இன்றை விட +₹${deltaPrice}/கிலோ அதிகம்).`);
        explanations.push(`Expected spoilage increases modestly to ${bestDayMetric.spoilage_pct}% (a change of ${deltaSpoil >= 0 ? '+' : ''}${deltaSpoil.toFixed(1)}% over Day 0).`);
        taExplanations.push(`எதிர்பார்க்கப்படும் பயிர் அழுகல் ${bestDayMetric.spoilage_pct}% ஆக மிதமாகவே உயர்கிறது (நாள் 0-ஐ விட ${deltaSpoil >= 0 ? '+' : ''}${deltaSpoil.toFixed(1)}% மாற்றம்).`);
        explanations.push(`Harvesting on Day ${recDay} yields ₹${deltaVal.toLocaleString()} more Expected Farmer Value than immediate Day 0 harvest.`);
        taExplanations.push(`நாள் ${recDay}-ல் அறுவடை செய்வது உடனடியாக அறுவடை செய்வதை விட ₹${deltaVal.toLocaleString()} கூடுதல் நிகர மதிப்பை ஈட்டித் தரும்.`);
    }

    if (bestMarket) {
        explanations.push(`Optimal channel: ${bestMarket.name} yields highest net return of ₹${bestMarket.net_farmer_value.toLocaleString()} after transit & storage fees.`);
        taExplanations.push(`சிறந்த சந்தை வாய்ப்பு: ${bestMarket.name_ta} போக்குவரத்து & சேமிப்பு செலவுக்குப் பின் அதிகபட்ச நிகர மதிப்பான ₹${bestMarket.net_farmer_value.toLocaleString()}-ஐ வழங்குகிறது.`);
    }

    const recEn = recDay === 0 ? "HARVEST NOW (Day 0)" : `HARVEST ON DAY ${recDay}`;
    const recTa = recDay === 0 ? "இப்போதே அறுவடை செய்க (நாள் 0)" : `நாள் ${recDay}-ல் அறுவடை செய்க`;

    return {
        inputs: rawInputs,
        fallback_used: fallbackUsed,
        warnings: warnings,
        timeline: timeline,
        recommendation: {
            day: recDay,
            decision_en: recEn,
            decision_ta: recTa,
            expected_farmer_value: bestDayMetric.expected_farmer_value,
            expected_spoilage: bestDayMetric.spoilage_pct,
            risk_level: bestDayMetric.risk_level,
            usable_quantity: bestDayMetric.usable_quantity,
            gross_revenue: bestDayMetric.gross_revenue,
            storage_cost: bestDayMetric.storage_cost,
            transport_cost: bestDayMetric.transport_cost,
            handling_cost: bestDayMetric.handling_cost,
            price: bestDayMetric.price
        },
        baseline_comparison: {
            baseline_name: 'Immediate Harvest (Day 0)',
            baseline_name_ta: 'உடனடி அறுவடை (நாள் 0)',
            baseline_farmer_value: baselineMetric.expected_farmer_value,
            baseline_spoilage: baselineMetric.spoilage_pct,
            baseline_usable_qty: baselineMetric.usable_quantity,
            proposed_farmer_value: bestDayMetric.expected_farmer_value,
            proposed_spoilage: bestDayMetric.spoilage_pct,
            proposed_usable_qty: bestDayMetric.usable_quantity,
            value_difference: valueDiff,
            pct_improvement: pctImprovement,
            spoilage_difference: spoilDiff
        },
        markets: markets,
        best_market: bestMarket,
        sensitivity: {
            future_price: priceCurve,
            flip_points: flipPoints,
            flip_points_ta: flipPointsTa
        },
        explanations: explanations,
        ta_explanations: taExplanations
    };
}

// -------------------------------------------------------------------
// RENDER SIMULATION RESULTS ON DASHBOARD
// -------------------------------------------------------------------
function renderSimulationResults(data) {
    if (!data) return;

    const rec = data.recommendation;
    const base = data.baseline_comparison;
    const bestMarket = data.best_market;

    // 1. Fallback Notice Banner
    const fallbackBanner = document.getElementById('fallback-banner');
    const fallbackText = document.getElementById('fallback-banner-text');
    if (fallbackBanner && fallbackText) {
        if (data.fallback_used || (data.warnings && data.warnings.length > 0)) {
            fallbackBanner.style.display = 'flex';
            const msg = data.warnings && data.warnings.length > 0 ? data.warnings.join(' ') : "Fallback data is being used for missing parameters.";
            fallbackText.textContent = msg;
            fallbackText.setAttribute('data-en', msg);
            fallbackText.setAttribute('data-ta', 'விடுபட்ட வானிலை/விலைத் தரவுகளுக்கு இயல்புநிலைத் தரவு பயன்படுத்தப்படுகிறது.');
        } else {
            fallbackBanner.style.display = 'none';
        }
    }

    // 2. Primary Recommendation Box
    const recBox = document.getElementById('recommendation-box');
    const recTitle = document.getElementById('rec-decision');
    if (recBox && recTitle) {
        recTitle.textContent = currentLang === 'ta' ? rec.decision_ta : rec.decision_en;
        recTitle.setAttribute('data-en', rec.decision_en);
        recTitle.setAttribute('data-ta', rec.decision_ta);

        if (rec.day === 0) {
            recBox.className = 'rec-box harvest';
        } else {
            recBox.className = 'rec-box wait';
        }
    }

    // 3. Highlight Metrics
    const dayElem = document.getElementById('metric-rec-day');
    if (dayElem) dayElem.textContent = rec.day === 0 ? 'Day 0 (Now)' : `Day ${rec.day}`;

    const netValElem = document.getElementById('metric-net-value');
    if (netValElem) netValElem.textContent = `₹${rec.expected_farmer_value.toLocaleString()}`;

    const spoilElem = document.getElementById('metric-spoilage-pct');
    if (spoilElem) spoilElem.textContent = `${rec.expected_spoilage}%`;

    const riskElem = document.getElementById('metric-risk-level');
    if (riskElem) {
        riskElem.textContent = rec.risk_level;
        riskElem.className = 'h-metric-val ' + (rec.risk_level === 'Low Risk' ? 'risk-low' : (rec.risk_level === 'Medium Risk' ? 'risk-medium' : 'risk-high'));
    }

    // 4. Explanations (Priority 8)
    const expList = document.getElementById('explanation-list');
    if (expList) {
        expList.innerHTML = '';
        const list = currentLang === 'ta' && data.ta_explanations ? data.ta_explanations : data.explanations;
        if (list && list.length > 0) {
            list.forEach(txt => {
                const li = document.createElement('li');
                li.textContent = txt;
                expList.appendChild(li);
            });
        }
    }

    // 5. Baseline Comparison (Priority 5)
    const baseValDisp = document.getElementById('base-value-display');
    const baseSpoilDisp = document.getElementById('base-spoilage-display');
    const propTitleDisp = document.getElementById('proposed-title-display');
    const propValDisp = document.getElementById('proposed-value-display');
    const propSpoilDisp = document.getElementById('proposed-spoilage-display');
    const impDisp = document.getElementById('improvement-display');

    if (baseValDisp) baseValDisp.textContent = `₹${base.baseline_farmer_value.toLocaleString()}`;
    if (baseSpoilDisp) baseSpoilDisp.textContent = `Spoilage: ${base.baseline_spoilage}% | Usable: ${base.baseline_usable_qty} kg`;
    if (propTitleDisp) {
        const titleText = rec.day === 0 ? "Immediate Harvest (Day 0)" : `Optimal Harvest (Day ${rec.day})`;
        propTitleDisp.textContent = titleText;
    }
    if (propValDisp) propValDisp.textContent = `₹${base.proposed_farmer_value.toLocaleString()}`;
    if (propSpoilDisp) propSpoilDisp.textContent = `Spoilage: ${base.proposed_spoilage}% | Usable: ${base.proposed_usable_qty} kg`;

    if (impDisp) {
        const sign = base.value_difference >= 0 ? '+' : '';
        impDisp.textContent = `${sign}₹${base.value_difference.toLocaleString()} (${sign}${base.pct_improvement}%)`;
        impDisp.className = base.value_difference >= 0 ? 'compare-diff-positive' : 'compare-diff-negative';
    }

    // 6. Market Options Cards (Priority 6)
    const marketCards = document.getElementById('market-cards-container');
    if (marketCards && data.markets) {
        marketCards.innerHTML = '';
        data.markets.forEach((m, idx) => {
            const isBest = (bestMarket && bestMarket.key === m.key);
            const card = document.createElement('div');
            card.className = `market-card ${isBest ? 'best-market' : ''}`;
            const mName = currentLang === 'ta' && m.name_ta ? m.name_ta : m.name;
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <h4 style="font-size: 1.05rem; font-weight: 600;">${mName}</h4>
                    ${isBest ? '<span class="badge-recommended">BEST CHOICE</span>' : ''}
                </div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 10px;">${m.description}</div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.82rem; margin-bottom: 10px;">
                    <div>Price: <strong>₹${m.price}/kg</strong></div>
                    <div>Transit: <strong>${m.transport_hours} hrs</strong></div>
                    <div>Spoilage: <strong style="color: ${m.spoilage_pct > 25 ? 'var(--danger)' : 'inherit'};">${m.spoilage_pct}%</strong></div>
                    <div>Usable Qty: <strong>${m.usable_quantity} kg</strong></div>
                    <div>Transport Cost: <strong>₹${m.transport_cost.toLocaleString()}</strong></div>
                    <div>Storage Cost: <strong>₹${m.storage_cost.toLocaleString()}</strong></div>
                </div>
                <div style="border-top: 1px solid var(--border-glass); padding-top: 8px; display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.85rem; color: var(--text-muted);">Net Farmer Value:</span>
                    <strong style="font-size: 1.15rem; color: ${isBest ? 'var(--success)' : 'var(--text-primary)'};">₹${m.net_farmer_value.toLocaleString()}</strong>
                </div>
            `;
            marketCards.appendChild(card);
        });
    }

    // 7. Day 0 - Day 10 Timeline Table & Chart (Priority 3)
    renderTimelineTableAndChart(data.timeline, rec.day);

    // 8. Sensitivity Flip Points & Charts (Priority 7)
    renderSensitivitySection(data.sensitivity, rec.day);
}

// Render Day 0 - Day 10 Timeline Table & Chart
function renderTimelineTableAndChart(timeline, recDay) {
    if (!timeline) return;

    const tbody = document.getElementById('timeline-table-body');
    if (tbody) {
        tbody.innerHTML = '';
        timeline.forEach(row => {
            const isRec = (row.day === recDay);
            const tr = document.createElement('tr');
            if (isRec) tr.className = 'recommended-row';

            const statusBadge = isRec 
                ? '<span class="badge-recommended">RECOMMENDED</span>' 
                : (row.day === 0 ? '<span class="badge-baseline">DAY 0 BASE</span>' : `<span style="color: var(--text-muted);">Day ${row.day}</span>`);

            tr.innerHTML = `
                <td><strong>Day ${row.day}</strong></td>
                <td>₹${row.price.toFixed(2)}</td>
                <td>${row.maturity}%</td>
                <td style="color: ${row.spoilage_pct > 25 ? 'var(--danger)' : 'inherit'};">${row.spoilage_pct}%</td>
                <td>${row.usable_quantity} kg</td>
                <td>₹${row.gross_revenue.toLocaleString()}</td>
                <td>₹${(row.storage_cost + row.transport_cost + row.handling_cost).toLocaleString()}</td>
                <td style="font-weight: 700; color: ${isRec ? 'var(--success)' : 'var(--accent-color)'};">₹${row.expected_farmer_value.toLocaleString()}</td>
                <td>${statusBadge}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    // Render Timeline Chart
    if (typeof Chart !== 'undefined') {
        const ctx = document.getElementById('chart-timeline');
        if (ctx) {
            if (activeCharts['timeline']) activeCharts['timeline'].destroy();

            const labels = timeline.map(r => `Day ${r.day}`);
            const netValues = timeline.map(r => r.expected_farmer_value);
            const spoilageRates = timeline.map(r => r.spoilage_pct);

            activeCharts['timeline'] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Expected Farmer Value (₹)',
                            data: netValues,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.15)',
                            fill: true,
                            tension: 0.3,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Spoilage Risk (%)',
                            data: spoilageRates,
                            borderColor: '#f87171',
                            backgroundColor: 'transparent',
                            borderDash: [5, 5],
                            tension: 0.3,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            type: 'linear',
                            position: 'left',
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#9ca3af' }
                        },
                        y1: {
                            type: 'linear',
                            position: 'right',
                            grid: { drawOnChartArea: false },
                            ticks: { color: '#f87171' }
                        },
                        x: {
                            ticks: { color: '#9ca3af' }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#f3f4f6' } }
                    }
                }
            });
        }
    }
}

// Render Sensitivity Flip Points and Charts
function renderSensitivitySection(sens, recDay) {
    if (!sens) return;

    // Flip points list
    const flipList = document.getElementById('flip-points-list');
    if (flipList) {
        flipList.innerHTML = '';
        const list = currentLang === 'ta' && sens.flip_points_ta ? sens.flip_points_ta : sens.flip_points;
        if (list && list.length > 0) {
            list.forEach(item => {
                const li = document.createElement('li');
                li.innerHTML = `<strong>Shift detected:</strong> ${item}`;
                flipList.appendChild(li);
            });
        } else {
            const li = document.createElement('li');
            li.textContent = "The current recommendation is highly stable across tested price & weather margins.";
            flipList.appendChild(li);
        }
    }

    if (typeof Chart === 'undefined') return;

    // 1. Chart: Net Farmer Value vs Future Price
    if (sens.future_price) {
        const ctxFP = document.getElementById('chart-profit-futureprice');
        if (ctxFP) {
            if (activeCharts['future_price']) activeCharts['future_price'].destroy();
            activeCharts['future_price'] = new Chart(ctxFP, {
                type: 'line',
                data: {
                    labels: sens.future_price.map(p => p.variation),
                    datasets: [{
                        label: 'Net Farmer Value (₹)',
                        data: sens.future_price.map(p => p.expected_farmer_value),
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
                        x: { ticks: { color: '#9ca3af' } }
                    },
                    plugins: { legend: { labels: { color: '#f3f4f6' } } }
                }
            });
        }
    }

    // 2. Chart: Spoilage Multiplier Sweep
    const ctxSpoil = document.getElementById('chart-profit-spoilage');
    if (ctxSpoil && sens.spoilage_rate) {
        if (activeCharts['spoilage_rate']) activeCharts['spoilage_rate'].destroy();
        activeCharts['spoilage_rate'] = new Chart(ctxSpoil, {
            type: 'bar',
            data: {
                labels: sens.spoilage_rate.map(s => s.variation),
                datasets: [{
                    label: 'Expected Farmer Value (₹)',
                    data: sens.spoilage_rate.map(s => s.expected_farmer_value),
                    backgroundColor: 'rgba(52, 211, 153, 0.6)',
                    borderColor: '#34d399',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
                    x: { ticks: { color: '#9ca3af' } }
                },
                plugins: { legend: { labels: { color: '#f3f4f6' } } }
            }
        });
    }

    // 3. Chart: Temperature vs Recommended Harvest Day
    const ctxTemp = document.getElementById('chart-decision-maturity');
    if (ctxTemp && sens.temperature) {
        if (activeCharts['temp_day']) activeCharts['temp_day'].destroy();
        activeCharts['temp_day'] = new Chart(ctxTemp, {
            type: 'line',
            data: {
                labels: sens.temperature.map(t => t.variation),
                datasets: [{
                    label: 'Recommended Harvest Day',
                    data: sens.temperature.map(t => t.recommended_day),
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    stepped: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { min: 0, max: 10, ticks: { stepSize: 1, color: '#9ca3af' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
                    x: { ticks: { color: '#9ca3af' } }
                },
                plugins: { legend: { labels: { color: '#f3f4f6' } } }
            }
        });
    }

    // 4. Chart: Storage Duration vs Value
    const ctxStore = document.getElementById('chart-profit-storage');
    if (ctxStore && sens.storage_duration) {
        if (activeCharts['storage_val']) activeCharts['storage_val'].destroy();
        activeCharts['storage_val'] = new Chart(ctxStore, {
            type: 'line',
            data: {
                labels: sens.storage_duration.map(s => s.variation),
                datasets: [{
                    label: 'Net Farmer Value (₹)',
                    data: sens.storage_duration.map(s => s.expected_farmer_value),
                    borderColor: '#60a5fa',
                    backgroundColor: 'rgba(96, 165, 250, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { ticks: { color: '#9ca3af' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
                    x: { ticks: { color: '#9ca3af' } }
                },
                plugins: { legend: { labels: { color: '#f3f4f6' } } }
            }
        });
    }
}

// -------------------------------------------------------------------
// EVALUATION METRICS LOADER
// -------------------------------------------------------------------
async function loadEvaluationMetrics() {
    try {
        const response = await fetch('/api/metrics');
        if (response.ok) {
            const m = await response.json();
            const bVal = document.getElementById('eval-base-val');
            const pVal = document.getElementById('eval-proposed-val');
            const impVal = document.getElementById('eval-imp-val');
            const bSpoil = document.getElementById('eval-base-spoil');
            const pSpoil = document.getElementById('eval-proposed-spoil');
            const winCnt = document.getElementById('eval-win-count');

            if (bVal) bVal.textContent = `₹${m.average_baseline_value.toLocaleString()}`;
            if (pVal) pVal.textContent = `₹${m.average_proposed_value.toLocaleString()}`;
            if (impVal) impVal.textContent = `+₹${m.average_value_improvement.toLocaleString()} (+${m.percentage_value_improvement}%)`;
            if (bSpoil) bSpoil.textContent = `${m.average_baseline_spoilage}%`;
            if (pSpoil) pSpoil.textContent = `${m.average_proposed_spoilage}%`;
            if (winCnt) winCnt.textContent = `${m.win_count} / ${m.records_evaluated} (${m.win_rate_pct}%)`;
        }
    } catch (e) {
        console.warn("Could not load /api/metrics from server; pre-rendered default metrics will display.", e);
    }
}

// -------------------------------------------------------------------
// OFFLINE LOCALSTORAGE CALCULATIONS
// -------------------------------------------------------------------
function saveCalculationLocally() {
    const inputs = getFormData();
    const timestamp = new Date().toLocaleTimeString();
    const record = { timestamp, inputs };

    let history = JSON.parse(localStorage.getItem('harvest_calcs') || '[]');
    history.unshift(record);
    if (history.length > 5) history = history.slice(0, 5);
    localStorage.setItem('harvest_calcs', JSON.stringify(history));

    loadSavedCalculations();
}

function loadSavedCalculations() {
    const list = document.getElementById('saved-calculations-list');
    if (!list) return;

    const history = JSON.parse(localStorage.getItem('harvest_calcs') || '[]');
    if (history.length === 0) {
        list.innerHTML = `<li style="color: var(--text-muted);">${currentLang === 'ta' ? 'உள்ளூர் சேமிப்புகள் எதுவும் இல்லை.' : 'No calculations saved locally yet.'}</li>`;
        return;
    }

    list.innerHTML = '';
    history.forEach((rec, idx) => {
        const li = document.createElement('li');
        li.style.cssText = 'padding: 6px 0; border-bottom: 1px solid var(--border-glass); cursor: pointer;';
        li.innerHTML = `<strong>#${idx + 1} (${rec.timestamp})</strong>: ${rec.inputs.crop} | ${rec.inputs.quantity}kg | ₹${rec.inputs.current_price}/kg`;
        li.onclick = () => {
            populateInputs(rec.inputs);
            runSimulationDynamic();
        };
        list.appendChild(li);
    });
}
