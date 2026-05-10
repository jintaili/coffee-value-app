const form = document.querySelector("#analyzeForm");
const urlInput = document.querySelector("#urlInput");
const statusText = document.querySelector("#statusText");
const summaryGrid = document.querySelector("#summaryGrid");
const badges = document.querySelector("#badges");
const warningsList = document.querySelector("#warningsList");
const detailsContent = document.querySelector("#detailsContent");
const detailsBody = document.querySelector("#detailsBody");
const toggleDetails = document.querySelector("#toggleDetails");
const tabs = document.querySelectorAll(".tab");
const heroVerdict = document.querySelector("#heroVerdict");

let currentData = null;
let currentTab = "json";

const formatMoney = (value) => value == null ? "—" : `$${Number(value).toFixed(2)}`;
const formatNumber = (value, digits = 1) => value == null ? "—" : Number(value).toFixed(digits);
const titleize = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const joinList = (value) => Array.isArray(value) && value.length ? value.map(titleize).join(", ") : "—";
const verdictLabels = {
  good_value: "Good Value",
  priced_about_right: "Fair",
  expensive_for_predicted_quality: "Expensive",
  insufficient_information: "Insufficient Info",
  model_not_available: "Unavailable",
  model_not_available_price_missing: "Unavailable",
};
const currencySymbols = {
  USD: "$",
  EUR: "€",
  DKK: "kr ",
  GBP: "£",
  CAD: "CA$",
  AUD: "A$",
  JPY: "¥",
};

function setProgress(state) {
  const order = ["fetch", "extract", "predict"];
  document.querySelectorAll(".step").forEach((step) => {
    step.classList.remove("active", "done");
    const index = order.indexOf(step.dataset.step);
    const current = order.indexOf(state);
    if (state === "done" || index < current) step.classList.add("done");
    if (index === current) step.classList.add("active");
  });
}

function setLoading(isLoading) {
  form.querySelector("button").disabled = isLoading;
  urlInput.disabled = isLoading;
}

function setResultState(state) {
  heroVerdict.classList.remove("is-pending", "is-loading", "is-good-value", "is-fair", "is-expensive", "is-insufficient");
  heroVerdict.classList.add(state);
}

function addSummaryRow(label, value) {
  const template = document.querySelector("#summaryRowTemplate");
  const node = template.content.cloneNode(true);
  node.querySelector(".row-label").textContent = label;
  node.querySelector(".row-value").textContent = value || "—";
  summaryGrid.appendChild(node);
}

function formatCurrency(value, currency) {
  if (value == null) return "—";
  const code = currency || "USD";
  const symbol = currencySymbols[code] || `${code} `;
  return `${symbol}${Number(value).toFixed(2)}`;
}

function formatListedPrice(price) {
  const listed = formatCurrency(price.listed_price, price.listed_currency);
  if (
    price.original_listed_price != null &&
    price.original_listed_currency &&
    price.original_listed_currency !== price.listed_currency
  ) {
    return `${listed} from ${formatCurrency(price.original_listed_price, price.original_listed_currency)}`;
  }
  return listed;
}

function analysisPriceDetails(price) {
  const details = {
    listed_price: price.listed_price,
    listed_currency: price.listed_currency,
    original_listed_price: price.original_listed_price,
    original_listed_currency: price.original_listed_currency,
    price_100g_usd: price.price_100g_usd,
    bag_size_value: price.bag_size_value,
    bag_size_unit: price.bag_size_unit,
    package_grams: price.package_grams,
    assumptions: price.assumptions,
  };
  if (price.listed_currency === "USD") {
    details.normalized_listed_price_usd = price.listed_price;
  }
  return details;
}

function renderSummary(data) {
  const coffee = data.coffee;
  const price = data.price;
  summaryGrid.innerHTML = "";
  addSummaryRow("Coffee name", coffee.coffee_name);
  addSummaryRow("Producer", coffee.producer_or_farm);
  addSummaryRow("Roaster", coffee.roaster);
  addSummaryRow("Altitude", coffee.altitude);
  addSummaryRow("Origin", [coffee.origin_country, coffee.origin_region].filter(Boolean).filter((v) => v !== "unknown").join(" · "));
  addSummaryRow("Tasting notes", coffee.sensory_text);
  addSummaryRow("Process", joinList(coffee.process_method));
  addSummaryRow("Listed price", formatListedPrice(price));
  addSummaryRow("Variety", joinList(coffee.variety));
  addSummaryRow("Bag size", price.bag_size_value && price.bag_size_unit ? `${price.bag_size_value} ${price.bag_size_unit}` : "—");
  addSummaryRow("Normalized listed price", price.price_100g_usd == null ? "—" : `${formatMoney(price.price_100g_usd)} / 100g`);
  addSummaryRow("Roaster country", coffee.roaster_country);

  const badgeValues = [];
  if (!coffee.is_blend) badgeValues.push("Single Origin");
  if (coffee.is_blend) badgeValues.push("Blend");
  if (coffee.is_espresso) badgeValues.push("Espresso Friendly");
  if (coffee.is_decaf) badgeValues.push("Decaf");
  if (coffee.altitude) badgeValues.push("Altitude Listed");
  if (coffee.process_method?.some((v) => v !== "unknown")) badgeValues.push(`${titleize(coffee.process_method[0])} Process`);
  badges.innerHTML = badgeValues.map((value) => `<span class="pill">${value}</span>`).join("");
}

function renderPrediction(data) {
  const rating = data.prediction.rating;
  const price = data.prediction.price;
  const listedPrice = data.price;
  document.querySelector("#predictedRating").textContent = formatNumber(rating.predicted, 1);
  document.querySelector("#detailPredictedRating").textContent = formatNumber(rating.predicted, 1);
  document.querySelector("#ratingInterval").textContent = rating.interval_low == null ? "—" : `${formatNumber(rating.interval_low, 1)}–${formatNumber(rating.interval_high, 1)}`;
  document.querySelector("#predictedBagPrice").textContent = formatMoney(price.predicted_bag_price_usd);
  document.querySelector("#detailPredictedBagPrice").textContent = formatMoney(price.predicted_bag_price_usd);
  document.querySelector("#predicted100g").textContent = price.predicted_price_100g_usd == null ? "—" : `${formatMoney(price.predicted_price_100g_usd)} / 100g`;
  document.querySelector("#detailPredicted100g").textContent = price.predicted_price_100g_usd == null ? "—" : formatMoney(price.predicted_price_100g_usd);
  document.querySelector("#listedBagPrice").textContent = formatListedPrice(listedPrice);
  document.querySelector("#listed100g").textContent = listedPrice.price_100g_usd == null ? "—" : `${formatMoney(listedPrice.price_100g_usd)} / 100g`;
  document.querySelector("#priceInterval").textContent = price.interval_low == null ? "—" : `${formatMoney(price.interval_low)}–${formatMoney(price.interval_high)}`;
  document.querySelector("#modelLine").textContent = `Rating model: ${rating.model_version} · Price model: ${price.model_version}`;
  document.querySelector("#ratingLabel").textContent = rating.predicted == null ? "—" : rating.predicted >= 90 ? "Excellent quality" : rating.predicted >= 86 ? "High quality" : "Solid quality";
}

function renderVerdict(data) {
  const value = data.prediction.value;
  const verdict = verdictLabels[value.verdict] || titleize(value.verdict);
  document.querySelector("#verdictText").textContent = verdict;
  const delta = value.listed_vs_predicted_delta_pct;
  const state = delta == null ? "is-insufficient" : delta < -20 ? "is-good-value" : delta > 20 ? "is-expensive" : "is-fair";
  setResultState(state);
  const copy = delta == null
    ? "The app needs both listed price and predicted fair price to judge value."
    : `Listed price is ${Math.abs(delta).toFixed(1)}% ${delta >= 0 ? "above" : "below"} predicted fair price.`;
  document.querySelector("#verdictCopy").textContent = copy;
  document.querySelector("#pricePremium").textContent = delta == null ? "—" : `${delta > 0 ? "+" : ""}${delta.toFixed(1)}%`;
  document.querySelector("#pricePremium").classList.toggle("is-expensive", delta != null && delta > 20);
  document.querySelector("#pricePremium").classList.toggle("is-value", delta != null && delta < -20);
  const needleDeg = delta == null ? 0 : Math.max(-62, Math.min(62, delta * 1.25));
  document.querySelector("#needle").setAttribute("transform", `rotate(${needleDeg} 130 115)`);
}

function renderQuality(data) {
  const quality = data.quality;
  const missing = quality.missing_fields || [];
  const warnings = quality.warnings || [];
  const assumptions = data.price.assumptions || [];
  const completeness = Math.max(0, Math.round((1 - missing.length / 12) * 100));

  document.querySelector("#qualityValue").textContent = titleize(quality.extraction_quality);
  document.querySelector("#completenessValue").textContent = `${completeness}%`;
  document.querySelector("#missingValue").textContent = missing.length ? String(missing.length) : "None";
  document.querySelector("#warningValue").textContent = String(warnings.length);

  const items = [];
  if (!warnings.length && !missing.length) items.push({ text: "No major extraction issues detected", warn: false });
  warnings.forEach((text) => items.push({ text, warn: true }));
  missing.forEach((text) => items.push({ text: `Missing ${text}`, warn: true }));
  assumptions.forEach((text) => items.push({ text, warn: false }));
  warningsList.innerHTML = items.map((item) => `<span class="inline-item ${item.warn ? "warn" : ""}">${escapeHtml(item.text)}</span>`).join("");
}

function renderDetails() {
  if (!currentData) {
    detailsContent.textContent = "{}";
    return;
  }
  if (currentTab === "json") {
    detailsContent.textContent = JSON.stringify({
      coffee: currentData.coffee,
      price: analysisPriceDetails(currentData.price),
      model_input: currentData.model_input,
      prediction: currentData.prediction,
      quality: currentData.quality,
    }, null, 2);
  } else if (currentTab === "snippets") {
    detailsContent.textContent = JSON.stringify(currentData.coffee.source_snippets || [], null, 2);
  } else if (currentTab === "missing") {
    detailsContent.textContent = JSON.stringify(currentData.quality.missing_fields || [], null, 2);
  } else if (currentTab === "versions") {
    detailsContent.textContent = JSON.stringify({
      api_version: currentData.api_version,
      rating_model: currentData.prediction.rating.model_version,
      price_model: currentData.prediction.price.model_version,
    }, null, 2);
  }
}

function render(data) {
  currentData = data;
  renderSummary(data);
  renderPrediction(data);
  renderVerdict(data);
  renderQuality(data);
  renderDetails();
}

function renderPendingHero() {
  setResultState("is-pending");
  document.querySelector("#verdictText").textContent = "Awaiting analysis";
  document.querySelector("#verdictCopy").textContent = "Results are not finalized until you analyze a product URL.";
  document.querySelector("#predictedRating").textContent = "—";
  document.querySelector("#ratingLabel").textContent = "Pending";
  document.querySelector("#predictedBagPrice").textContent = "—";
  document.querySelector("#predicted100g").textContent = "—";
  document.querySelector("#listedBagPrice").textContent = "—";
  document.querySelector("#listed100g").textContent = "—";
  document.querySelector("#pricePremium").textContent = "—";
  document.querySelector("#pricePremium").classList.remove("is-expensive", "is-value");
  document.querySelector("#needle").setAttribute("transform", "rotate(0 130 115)");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  if (!url) return;
  setLoading(true);
  setResultState("is-loading");
  document.querySelector("#verdictText").textContent = "Analysis in progress";
  document.querySelector("#verdictCopy").textContent = "Displayed results are not finalized for this URL yet.";
  setProgress("fetch");
  statusText.textContent = "Fetching page and preparing extraction context.";
  try {
    setProgress("extract");
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    setProgress("predict");
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed with status ${response.status}`);
    }
    const data = await response.json();
    render(data);
    setProgress("done");
    statusText.textContent = "Analysis complete.";
  } catch (error) {
    statusText.textContent = error.message;
    setResultState("is-pending");
    document.querySelector("#verdictText").textContent = "Analysis failed";
    document.querySelector("#verdictCopy").textContent = "The displayed results were not updated.";
    setProgress(null);
  } finally {
    setLoading(false);
  }
});

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    currentTab = tab.dataset.tab;
    renderDetails();
  });
});

toggleDetails.addEventListener("click", () => {
  detailsBody.classList.toggle("hidden");
  toggleDetails.textContent = detailsBody.classList.contains("hidden") ? "⌄" : "⌃";
});

document.querySelector("#aboutButton").addEventListener("click", () => {
  alert("Coffee Value extracts coffee attributes from a roaster product page, predicts rating and fair price, and compares that with the listed price.");
});

document.querySelector("#historyButton").addEventListener("click", () => {
  alert("History is not enabled yet.");
});

render({
  api_version: "v1",
  coffee: {
    coffee_name: "Example Coffee",
    roaster: "Example Roaster",
    roaster_country: "United States",
    origin_country: "Kenya",
    origin_region: "Nyeri",
    process_method: ["washed"],
    variety: ["sl28", "sl34"],
    producer_or_farm: "Example Cooperative",
    altitude: "1800-2000 masl",
    is_blend: false,
    is_espresso: false,
    is_decaf: false,
    sensory_text: "Blackcurrant, citrus, florals",
    producer_text: "Washed coffee from Nyeri.",
    source_snippets: [],
  },
  price: {
    listed_price: 23,
    bag_size_value: 250,
    bag_size_unit: "g",
    price_100g_usd: 9.2,
    assumptions: ["Assumed USD because page used $ and no other currency was found"],
  },
  model_input: {},
  prediction: {
    rating: { predicted: 93, interval_low: null, interval_high: null, model_version: "rating/model.pkl" },
    price: { predicted_price_100g_usd: 8.5, predicted_bag_price_usd: 21.25, interval_low: null, interval_high: null, model_version: "price/model.pkl" },
    value: { verdict: "priced_about_right", listed_vs_predicted_delta_pct: 8.2 },
  },
  quality: { extraction_quality: "good", missing_fields: [], warnings: [] },
});
renderPendingHero();
