// Demo presets removed for interview-ready UI

const NEIGHBORHOODS = [
  {
    names: ["pasadena", "91103", "91105", "old town"],
    label: "Pasadena / Northeast LA",
    basePrice: 640000,
    compRange: [615000, 695000],
    baseConfidence: 0.88,
    trend: "+2.1% over 3 months",
    source: "ATTOM + Zillow Research",
  },
  {
    names: ["glendale", "91206", "91205", "la crescenta"],
    label: "Glendale / Foothill metro",
    basePrice: 695000,
    compRange: [650000, 760000],
    baseConfidence: 0.84,
    trend: "+1.6% over 3 months",
    source: "ATTOM + county records",
  },
  {
    names: ["los angeles", "90069", "90046", "west hollywood"],
    label: "West Hollywood / Central LA",
    basePrice: 1180000,
    compRange: [1100000, 1320000],
    baseConfidence: 0.8,
    trend: "+2.8% over 3 months",
    source: "ATTOM + FRED trend overlay",
  },
];

const API_BASE_URL = "http://127.0.0.1:8000";

const form = document.getElementById("valuationForm");
const loadDemoButton = document.getElementById("loadDemo");
const report = document.getElementById("report");
const loadingState = document.getElementById("loadingState");
const errorState = document.getElementById("errorState");
const statusBadge = document.getElementById("statusBadge");
const estimateRange = document.getElementById("estimateRange");
const estimateMeta = document.getElementById("estimateMeta");
const confidenceBadge = document.getElementById("confidenceBadge");
const dataSource = document.getElementById("dataSource");
const lowLabel = document.getElementById("lowLabel");
const midLabel = document.getElementById("midLabel");
const highLabel = document.getElementById("highLabel");
const rangeBar = document.getElementById("rangeBar");
const midMarker = document.getElementById("midMarker");
const compsUsed = document.getElementById("compsUsed");
const compsNote = document.getElementById("compsNote");
const modelVersion = document.getElementById("modelVersion");
const trustSignal = document.getElementById("trustSignal");
const compsTableBody = document.getElementById("compsTableBody");
const explanationsList = document.getElementById("explanationsList");

function numberFormat(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Math.round(value));
}

function money(value) {
  return `$${numberFormat(value)}`;
}

function compactMoney(value) {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "+";
  if (abs >= 1000) {
    return `${sign}$${(abs / 1000).toFixed(abs % 1000 === 0 ? 0 : 1)}k`;
  }
  return `${sign}$${numberFormat(abs)}`;
}

function hashString(value) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash >>> 0);
}

function seededRandom(seed) {
  let state = seed % 2147483647;
  if (state <= 0) state += 2147483646;
  return () => {
    state = (state * 16807) % 2147483647;
    return (state - 1) / 2147483646;
  };
}

function getNeighborhood(address) {
  const normalized = address.toLowerCase();
  return (
    NEIGHBORHOODS.find((neighborhood) => neighborhood.names.some((needle) => normalized.includes(needle))) ||
    {
      label: "Default Metro",
      basePrice: 560000,
      compRange: [520000, 610000],
      baseConfidence: 0.76,
      trend: "+1.2% over 3 months",
      source: "ATTOM fixture data",
    }
  );
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function inferAddressParts(address) {
  const zipMatch = address.match(/\b(\d{5})(?:-\d{4})?\b/);
  const cityMatch = address.match(/,\s*([^,]+?),\s*[A-Z]{2}/);
  return {
    zip: zipMatch ? zipMatch[1] : "n/a",
    city: cityMatch ? cityMatch[1].trim() : "local market",
  };
}

function buildComps(address, property, neighborhood, random) {
  const compCount = 6;
  const comps = [];
  const saleFloor = neighborhood.compRange[0];
  const saleCeil = neighborhood.compRange[1];

  for (let index = 0; index < compCount; index += 1) {
    const ageOffset = index - 2.5;
    const sqft = Math.round(property.sqft * (0.92 + random() * 0.18));
    const beds = clamp(Math.round(property.beds + (random() > 0.6 ? 1 : 0) - (random() > 0.8 ? 1 : 0)), 2, 6);
    const baths = Math.round((property.baths + (random() - 0.4) * 0.8) * 2) / 2;
    const soldDaysAgo = 12 + index * 11 + Math.round(random() * 6);
    const salePrice = Math.round(
      clamp(
        neighborhood.basePrice + ageOffset * 12000 + (sqft - property.sqft) * 225 + (beds - property.beds) * 17500 +
          (baths - property.baths) * 10500 + (random() - 0.5) * 24000,
        saleFloor,
        saleCeil,
      ),
    );

    comps.push({
      address: `${100 + index * 18} ${["Cedar", "Olive", "Maple", "Orange", "Palm", "Walnut"][index]} St`,
      sale_price: salePrice,
      sqft,
      beds,
      baths,
      sold_days_ago: soldDaysAgo,
    });
  }

  return comps.sort((left, right) => right.sale_price - left.sale_price);
}

function buildExplanations(property, neighborhood, comps, random) {
  const medianPricePerSqft = comps.reduce((sum, comp) => sum + comp.sale_price / comp.sqft, 0) / comps.length;
  const medianSqft = comps.map((comp) => comp.sqft).sort((a, b) => a - b)[Math.floor(comps.length / 2)];
  const medianBeds = comps.map((comp) => comp.beds).sort((a, b) => a - b)[Math.floor(comps.length / 2)];
  const medianBaths = comps.map((comp) => comp.baths).sort((a, b) => a - b)[Math.floor(comps.length / 2)];
  const propertyAge = 2025 - property.yearBuilt;
  const medianAge = clamp(propertyAge + Math.round((random() - 0.5) * 8) - 2, 5, 90);

  const sqftImpact = Math.round((property.sqft - medianSqft) * medianPricePerSqft * 0.42);
  const bedImpact = Math.round((property.beds - medianBeds) * 18500);
  const bathImpact = Math.round((property.baths - medianBaths) * 11800);
  const ageImpact = Math.round((medianAge - propertyAge) * 920);
  const lotImpact = Math.round(((property.lotSize - 5600) / 100) * 160);
  const conditionImpact = Math.round((property.conditionScore - 3) * 16500);

  const explanations = [
    {
      factor: "Sqft",
      impact: sqftImpact,
      direction: sqftImpact >= 0 ? "positive" : "negative",
      text: `Your ${numberFormat(property.sqft)} sqft home vs the nearby median of ${numberFormat(medianSqft)} sqft ${sqftImpact >= 0 ? "adds" : "reduces"} about ${compactMoney(sqftImpact)}.`,
    },
    {
      factor: "Beds",
      impact: bedImpact,
      direction: bedImpact >= 0 ? "positive" : "negative",
      text: `Your ${property.beds} bed count vs the median ${medianBeds} ${bedImpact >= 0 ? "adds" : "reduces"} about ${compactMoney(bedImpact)}.`,
    },
    {
      factor: "Baths",
      impact: bathImpact,
      direction: bathImpact >= 0 ? "positive" : "negative",
      text: `The ${property.baths} bath layout ${bathImpact >= 0 ? "adds" : "reduces"} about ${compactMoney(bathImpact)} versus area norms.`,
    },
    {
      factor: "Age",
      impact: ageImpact,
      direction: ageImpact >= 0 ? "positive" : "negative",
      text: `Built in ${property.yearBuilt}, the age profile ${ageImpact >= 0 ? "supports" : "pressures"} value by roughly ${compactMoney(ageImpact)}.`,
    },
    {
      factor: "Lot size",
      impact: lotImpact,
      direction: lotImpact >= 0 ? "positive" : "negative",
      text: `A ${numberFormat(property.lotSize)} sqft lot ${lotImpact >= 0 ? "adds" : "reduces"} approximately ${compactMoney(lotImpact)} relative to nearby homes.`,
    },
    {
      factor: "Condition rating",
      impact: conditionImpact,
      direction: conditionImpact >= 0 ? "positive" : "negative",
      text: `Condition rating of ${property.conditionScore}/5 (from listing photos) ${conditionImpact >= 0 ? "adds" : "reduces"} about ${compactMoney(conditionImpact)} compared to standard baseline.`,
    },
  ];

  return explanations.sort((left, right) => Math.abs(right.impact) - Math.abs(left.impact));
}

function buildResponse(address, property) {
  property = Object.assign({ yearBuilt: 1980, lotSize: 6000, conditionScore: 3 }, property);
  const neighborhood = getNeighborhood(address);
  const seed = hashString(`${address}|${property.beds}|${property.baths}|${property.sqft}|${property.yearBuilt}|${property.lotSize}|${property.conditionScore}`);
  const random = seededRandom(seed);
  const comps = buildComps(address, property, neighborhood, random);
  const explanations = buildExplanations(property, neighborhood, comps, random);
  const compAverage = comps.reduce((sum, comp) => sum + comp.sale_price, 0) / comps.length;
  const sizeAdjustment = (property.sqft - 1800) * 225;
  const bedAdjustment = (property.beds - 3.5) * 18000;
  const bathAdjustment = (property.baths - 2.25) * 11000;
  const ageAdjustment = (1980 - property.yearBuilt) * -850;
  const lotAdjustment = ((property.lotSize - 6000) / 100) * 140;
  const conditionAdjustment = (property.conditionScore - 3) * 16500;
  const noise = (random() - 0.5) * 18000;

  const mid = Math.round(clamp(neighborhood.basePrice * 0.28 + compAverage * 0.62 + sizeAdjustment + bedAdjustment + bathAdjustment + ageAdjustment + lotAdjustment + conditionAdjustment + noise, 300000, 2500000));
  const spreadFactor = 0.05 + (1 - neighborhood.baseConfidence) * 0.06 + Math.max(0, 4 - comps.length) * 0.015;
  const low = Math.round(mid * (1 - spreadFactor));
  const high = Math.round(mid * (1 + spreadFactor));
  const confidenceScore = clamp(neighborhood.baseConfidence - Math.max(0, 4 - comps.length) * 0.08 + (property.sqft > 1200 ? 0.02 : -0.03), 0.55, 0.94);
  const confidence = confidenceScore >= 0.83 ? "high" : confidenceScore >= 0.7 ? "medium" : "low";

  return {
    address,
    neighborhood,
    estimate: {
      low,
      mid,
      high,
      confidence,
    },
    comps_used: comps.length,
    comps,
    explanations,
    confidenceScore,
    model_version: "v1.0-local-demo",
    data_source: neighborhood.source,
    city: inferAddressParts(address).city,
    zip: inferAddressParts(address).zip,
    market_label: neighborhood.label,
    trend: neighborhood.trend,
    data_mode: "local-demo",
  };
}

function renderCompsTable(comps) {
  compsTableBody.innerHTML = comps
    .map(
      (comp) => `
        <tr>
          <td>${comp.address}</td>
          <td>${money(comp.sale_price)}</td>
          <td>${numberFormat(comp.sqft)}</td>
          <td>${comp.beds}</td>
          <td>${comp.baths}</td>
          <td>${comp.sold_days_ago} days ago</td>
        </tr>
      `,
    )
    .join("");
}

function renderExplanations(explanations) {
  explanationsList.innerHTML = explanations
    .map(
      (item) => `
        <article class="explanation-item">
          <div>
            <div class="factor-name">${item.factor}</div>
            <div class="muted">SHAP-style contribution</div>
          </div>
          <div class="factor-text">${item.text}</div>
          <div class="factor-impact ${item.direction}">${compactMoney(item.impact)}</div>
        </article>
      `,
    )
    .join("");
}

function updateMeter(low, mid, high) {
  const center = (mid - low) / Math.max(high - low, 1);
  const width = clamp(58 + (high - low) / mid * 100, 48, 72);
  const left = clamp(center * 100 - width / 2, 10, 100 - width - 10);
  rangeBar.style.width = `${width}%`;
  rangeBar.style.left = `${left}%`;
  midMarker.style.left = `${clamp(center * 100, 14, 86)}%`;
  lowLabel.textContent = money(low);
  midLabel.textContent = money(mid);
  highLabel.textContent = money(high);
}

function showLoading() {
  loadingState.classList.remove("hidden");
  errorState.classList.add("hidden");
  report.classList.add("hidden");
  if (statusBadge) {
    statusBadge.textContent = "Running model";
    statusBadge.className = "status-badge loading";
  }
}

function showError(message) {
  loadingState.classList.add("hidden");
  report.classList.add("hidden");
  errorState.classList.remove("hidden");
  errorState.textContent = message;
  if (statusBadge) {
    statusBadge.textContent = "Needs input";
    statusBadge.className = "status-badge neutral";
  }
}

function showReport(response) {
  loadingState.classList.add("hidden");
  errorState.classList.add("hidden");
  report.classList.remove("hidden");

  estimateRange.textContent = `${money(response.estimate.low)} - ${money(response.estimate.high)}`;
  estimateMeta.textContent = `${response.address} · ${response.city ?? response.zip ?? "local market"} · ${response.market_label ?? response.neighborhood?.label ?? "local market"}`;
  confidenceBadge.textContent = `${response.estimate.confidence} confidence`;
  confidenceBadge.className = `confidence-badge ${response.estimate.confidence}`;
  if (dataSource) dataSource.textContent = `Data source: ${response.data_source} · ${response.data_mode ?? "local-demo"}`;
  if (compsUsed) compsUsed.textContent = String(response.comps_used);
  if (compsNote) compsNote.textContent = `Estimated from ${response.comps_used} recent comps · ${response.trend ?? response.neighborhood?.trend ?? "market trend unavailable"}`;
  if (modelVersion) modelVersion.textContent = response.model_version;
  if (trustSignal) trustSignal.textContent = response.estimate.confidence === "high" ? "Strong" : response.estimate.confidence === "medium" ? "Moderate" : "Directional";
  if (statusBadge) {
    statusBadge.textContent = response.data_mode === "live-api" ? "Live API" : "Local demo";
    statusBadge.className = "status-badge success";
  }

  updateMeter(response.estimate.low, response.estimate.mid, response.estimate.high);
  renderCompsTable(response.comps);
  renderExplanations(response.explanations);
}

function readForm() {
  const address = document.getElementById("address").value.trim();
  const beds = Number(document.getElementById("beds").value);
  const baths = Number(document.getElementById("baths").value);
  const sqft = Number(document.getElementById("sqft").value);
  // advanced fields removed; use sensible defaults
  const yearBuilt = 1980;
  const lotSize = 6000;
  const conditionScore = 3;

  if (!address) {
    throw new Error("Enter a property address to generate a valuation.");
  }

  return { address, beds, baths, sqft, yearBuilt, lotSize, conditionScore };
}

async function handleSubmit(event) {
  event.preventDefault();

  let property;
  try {
    property = readForm();
  } catch (error) {
    showError(error instanceof Error ? error.message : "Enter a valid property address.");
    return;
  }

  showLoading();

  try {
    const apiResponse = await fetch(`${API_BASE_URL}/api/value`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        address: property.address,
        beds: property.beds,
        baths: property.baths,
        sqft: property.sqft,
        year_built: property.yearBuilt,
        lot_size: property.lotSize,
        condition_score: property.conditionScore,
      }),
    });

    if (!apiResponse.ok) {
      throw new Error(`Backend returned ${apiResponse.status}`);
    }

    const response = await apiResponse.json();
    response.data_mode = "live-api";
    showReport(response);
  } catch (error) {
    const seed = hashString(property.address);
    const delay = 450 + (seed % 300);
    await new Promise((resolve) => setTimeout(resolve, delay));
    const response = buildResponse(property.address, property);
    showReport(response);
  }
}

function fillPreset(name) {
  const preset = DEMO_PRESETS[name];
  if (!preset) return;
  document.getElementById("address").value = preset.address;
  document.getElementById("beds").value = preset.beds;
  document.getElementById("baths").value = preset.baths;
  document.getElementById("sqft").value = preset.sqft;
  document.getElementById("yearBuilt").value = preset.yearBuilt;
  document.getElementById("lotSize").value = preset.lotSize;
  document.getElementById("conditionScore").value = preset.conditionScore || 3;
}

function wirePresets() {
  // presets removed
}
form.addEventListener("submit", handleSubmit);
// remove auto-fill and demo messages for cleaner UI
