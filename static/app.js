const form = document.querySelector("#analyzeForm");
const urlInput = document.querySelector("#urlInput");
const analyzeButton = document.querySelector("#analyzeButton");
const statusNote = document.querySelector("#statusNote");
const appraisal = document.querySelector("#appraisal");
const kicker = document.querySelector("#kicker");
const verdictHead = document.querySelector("#verdictHead");
const verdictDek = document.querySelector("#verdictDek");
const caveat = document.querySelector("#caveat");
const ledgerTable = document.querySelector("#ledgerTable");
const recordLog = document.querySelector("#recordLog");
const appendixContent = document.querySelector("#appendixContent");
const toggleAppendix = document.querySelector("#toggleAppendix");
const tabs = document.querySelectorAll(".tab");

const UNKNOWN = "unknown";

let currentData = null;
let currentTab = "json";
let workingTimer = null;

/* ---------- formatting helpers ---------- */

const isMissing = (value) =>
  value == null || value === "" || String(value).trim().toLowerCase() === UNKNOWN;

function formatCurrency(value, currency) {
  if (value == null) return "—";
  const code = (currency || "USD").toUpperCase();
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: code,
      currencyDisplay: "narrowSymbol",
    }).format(value);
  } catch {
    return `${code} ${Number(value).toFixed(2)}`;
  }
}

const formatUsd = (value) => (value == null ? "—" : formatCurrency(value, "USD"));

const formatNumber = (value, digits = 1) =>
  value == null || !Number.isFinite(Number(value)) ? "—" : Number(value).toFixed(digits);

function verbatimJoin(values) {
  if (!Array.isArray(values)) return null;
  const kept = values.filter((v) => !isMissing(v));
  return kept.length ? kept.join(", ") : null;
}

function formatDelta(delta) {
  if (delta == null) return "—";
  return `${delta > 0 ? "+" : ""}${Number(delta).toFixed(1)}%`;
}

function bagDescription(price) {
  const parts = [];
  if (price.bag_size_value != null && price.bag_size_unit) {
    parts.push(`${price.bag_size_value} ${price.bag_size_unit}`);
  } else if (price.package_grams != null) {
    parts.push(`${price.package_grams} g`);
  }
  if (price.bags_count != null && price.bags_count > 1) parts.push(`× ${price.bags_count} bags`);
  return parts.join(" ");
}

/* ---------- record log ---------- */

function logLine(text, cls = "", timestamp = null) {
  const line = document.createElement("div");
  line.className = `line${cls ? ` ${cls}` : ""}`;
  const t = document.createElement("span");
  t.className = "t";
  t.textContent = timestamp == null ? "" : `${timestamp.toFixed(1)}s`;
  line.appendChild(t);
  line.appendChild(document.createTextNode(text));
  recordLog.appendChild(line);
  return line;
}

function clearLog() {
  recordLog.innerHTML = "";
}

/* ---------- headline copy ---------- */

const PAGE_TYPE_COPY = {
  coffee_equipment: {
    head: "That's coffee equipment, not coffee.",
    dek: "This page looks like a machine, grinder, or other gear listing. The ledger appraises roasted coffee only — paste a bag of beans instead.",
  },
  other_product: {
    head: "That's a product page — but not coffee.",
    dek: "The extractor read the page and found a product that isn't coffee. Nothing here for the cupping table.",
  },
  not_a_product_page: {
    head: "No single product found on that page.",
    dek: "This looks like a homepage, article, or collection rather than one product's page. Paste the page for a specific coffee.",
  },
};

const VERDICT_COPY = {
  good_value: { head: "Priced ", em: "below", tail: " its predicted quality.", cls: "good" },
  priced_about_right: { head: "Priced ", em: "about right", tail: ".", cls: "good" },
  expensive_for_predicted_quality: { head: "Priced ", em: "well above", tail: " its predicted quality.", cls: "bad" },
  insufficient_information: { head: "Not enough to ", em: "judge the price", tail: ".", cls: "" },
};

function setVerdictHead(copy) {
  verdictHead.innerHTML = "";
  verdictHead.appendChild(document.createTextNode(copy.head));
  const em = document.createElement("em");
  if (copy.cls) em.classList.add(copy.cls);
  em.textContent = copy.em;
  verdictHead.appendChild(em);
  verdictHead.appendChild(document.createTextNode(copy.tail));
}

function plainHead(text) {
  verdictHead.innerHTML = "";
  verdictHead.textContent = text;
}

function ratingPhrase(predicted) {
  if (predicted == null) return null;
  if (predicted >= 90) return "likely excellent";
  if (predicted >= 86) return "likely very good";
  if (predicted >= 82) return "solid";
  return "modest";
}

/* ---------- rendering ---------- */

function addLedgerRow(label, value, options = {}) {
  const row = document.createElement("tr");
  if (options.notes) row.className = "notes";
  const labelCell = document.createElement("td");
  labelCell.textContent = label;
  const valueCell = document.createElement("td");
  if (isMissing(value)) {
    const none = document.createElement("span");
    none.className = "none";
    none.textContent = "—";
    valueCell.appendChild(none);
  } else {
    valueCell.textContent = value;
  }
  row.appendChild(labelCell);
  row.appendChild(valueCell);
  ledgerTable.appendChild(row);
}

function renderLedger(data) {
  const coffee = data.coffee;
  const price = data.price;
  ledgerTable.innerHTML = "";

  addLedgerRow("Notes", coffee.display_tasting_notes || coffee.sensory_text, { notes: true });
  addLedgerRow("Coffee", coffee.coffee_name);
  addLedgerRow(
    "Origin",
    [coffee.origin_country, coffee.origin_region].filter((v) => !isMissing(v)).join(" · ")
  );
  addLedgerRow("Producer", coffee.producer_or_farm);
  addLedgerRow(
    "Roaster",
    [coffee.roaster, coffee.roaster_location || coffee.roaster_country]
      .filter((v) => !isMissing(v))
      .join(" — ")
  );
  addLedgerRow("Process", verbatimJoin(coffee.process_method));
  addLedgerRow("Variety", verbatimJoin(coffee.variety));
  addLedgerRow("Altitude", coffee.altitude);
  if (!isMissing(coffee.roast_level)) addLedgerRow("Roast level", coffee.roast_level);
  if (!isMissing(coffee.harvest_period)) addLedgerRow("Harvest", coffee.harvest_period);
  addLedgerRow("Bag", bagDescription(price));

  const remarks = [];
  remarks.push(coffee.is_blend ? "blend" : "single origin");
  if (coffee.is_espresso) remarks.push("espresso");
  if (coffee.is_decaf) remarks.push("decaf");
  if (coffee.is_coferment_or_infused) remarks.push("co-fermented / infused");
  if (price.availability && price.availability !== UNKNOWN && price.availability !== "in_stock") {
    remarks.push(price.availability.replaceAll("_", " "));
  }
  addLedgerRow("Remarks", remarks.join(" · "));
}

function renderScore(rating) {
  document.querySelector("#scoreValue").textContent = formatNumber(rating.predicted, 1);
  document.querySelector("#scoreGrade").textContent =
    rating.predicted == null ? "no prediction" : `${ratingPhrase(rating.predicted)} quality`;
  document.querySelector("#scoreInterval").textContent =
    rating.interval_low == null
      ? ""
      : `${formatNumber(rating.interval_low, 1)} – ${formatNumber(rating.interval_high, 1)} interval`;
}

function renderTariff(data) {
  const price = data.price;
  const prediction = data.prediction.price;
  const delta = data.prediction.value.listed_vs_predicted_delta_pct;

  const original =
    price.original_listed_price != null && price.original_listed_currency
      ? formatCurrency(price.original_listed_price, price.original_listed_currency)
      : null;
  document.querySelector("#listedAmt").textContent =
    original || formatCurrency(price.listed_price, price.listed_currency);

  const listedMeta = [];
  const bag = bagDescription(price);
  if (bag) listedMeta.push(bag);
  if (price.price_100g_usd != null) listedMeta.push(`${formatUsd(price.price_100g_usd)} / 100 g`);
  if (original && price.listed_price != null) listedMeta.push(`${formatUsd(price.listed_price)} converted`);
  if (price.price_type && price.price_type !== UNKNOWN && price.price_type !== "one_time") {
    listedMeta.push(`${price.price_type} price`);
  }
  document.querySelector("#listedMeta").textContent = listedMeta.join(" · ") || "not found on page";

  const fairMain =
    prediction.predicted_bag_price_usd != null
      ? formatUsd(prediction.predicted_bag_price_usd)
      : prediction.predicted_price_100g_usd != null
        ? `${formatUsd(prediction.predicted_price_100g_usd)}`
        : "—";
  document.querySelector("#fairAmt").textContent = fairMain;

  const fairMeta = [];
  if (prediction.predicted_bag_price_usd != null && prediction.predicted_price_100g_usd != null) {
    fairMeta.push(`${formatUsd(prediction.predicted_price_100g_usd)} / 100 g`);
  } else if (prediction.predicted_price_100g_usd != null) {
    fairMeta.push("per 100 g — bag size unknown");
  }
  if (prediction.interval_low != null) {
    fairMeta.push(`${formatUsd(prediction.interval_low)}–${formatUsd(prediction.interval_high)} / 100 g interval`);
  }
  document.querySelector("#fairMeta").textContent = fairMeta.join(" · ") || "no prediction";

  const premium = document.querySelector("#premiumAmt");
  premium.textContent = formatDelta(delta);
  premium.classList.remove("delta-over", "delta-under");
  if (delta != null && delta > 20) premium.classList.add("delta-over");
  if (delta != null && delta < -20) premium.classList.add("delta-under");

  const footParts = (price.assumptions || []).slice();
  footParts.push("non-USD prices converted at live Frankfurter rates before prediction");
  document.querySelector("#tariffFoot").textContent = footParts.join(" · ");
}

function renderRecord(data, elapsedSeconds) {
  clearLog();
  const coffee = data.coffee;
  const quality = data.quality || {};
  const missing = quality.missing_fields || [];
  const warnings = quality.warnings || [];
  const assumptions = data.price.assumptions || [];

  logLine(`GET ${data.input?.url || urlInput.value.trim()}`, "", 0);
  logLine(
    `page_type = ${data.page_type} · specialty = ${
      data.is_specialty_coffee == null ? "unclear" : data.is_specialty_coffee ? "yes" : "no"
    }`,
    data.page_type === "coffee_product" ? "ok" : "warn"
  );

  if (data.page_type === "coffee_product") {
    logLine(`extract ok · quality ${quality.extraction_quality || "?"}`, "ok");
    const seen = [];
    if (!isMissing(coffee.origin_country)) {
      seen.push(`origin ${[coffee.origin_country, coffee.origin_region].filter((v) => !isMissing(v)).join(" / ")}`);
    }
    const process = verbatimJoin(coffee.process_method);
    if (process) seen.push(`process ${process}`);
    const variety = verbatimJoin(coffee.variety);
    if (variety) seen.push(`variety ${variety}`);
    if (seen.length) logLine(seen.join(" · "), "dim");
  } else {
    logLine("prediction withheld — page is not a coffee product", "warn");
  }

  warnings.forEach((text) => logLine(`warn ${text}`, "warn"));
  missing.forEach((field) => logLine(`missing ${field}`, "warn"));
  assumptions.forEach((text) => logLine(`assume ${text}`, "warn"));

  if (data.page_type === "coffee_product") {
    const price = data.price;
    if (price.price_100g_usd != null) {
      const source =
        price.original_listed_price != null && price.original_listed_currency
          ? formatCurrency(price.original_listed_price, price.original_listed_currency)
          : formatCurrency(price.listed_price, price.listed_currency);
      logLine(`normalize ${source} → ${formatUsd(price.price_100g_usd)} / 100 g`, "ok");
    }
    const rating = data.prediction.rating;
    const pricePred = data.prediction.price;
    logLine(
      `predict rating ${formatNumber(rating.predicted, 1)} [${formatNumber(rating.interval_low, 1)}–${formatNumber(
        rating.interval_high,
        1
      )}] · fair ${
        pricePred.predicted_price_100g_usd == null ? "—" : `${formatUsd(pricePred.predicted_price_100g_usd)}/100g`
      } · verdict ${data.prediction.value.verdict}`,
      "ok"
    );
    logLine(`models ${rating.model_version} · ${pricePred.model_version}`, "dim");
  }

  logLine(`done · ${elapsedSeconds.toFixed(1)}s total (fetch + extract + predict)`, "", elapsedSeconds);
}

function renderAppendix() {
  if (!currentData) {
    appendixContent.textContent = "{}";
    return;
  }
  if (currentTab === "json") {
    appendixContent.textContent = JSON.stringify(
      {
        api_version: currentData.api_version,
        page_type: currentData.page_type,
        is_specialty_coffee: currentData.is_specialty_coffee,
        coffee: currentData.coffee,
        price: currentData.price,
        prediction: currentData.prediction,
        quality: currentData.quality,
      },
      null,
      2
    );
  } else if (currentTab === "snippets") {
    appendixContent.textContent = JSON.stringify(currentData.coffee?.source_snippets || [], null, 2);
  } else if (currentTab === "input") {
    appendixContent.textContent = JSON.stringify(currentData.model_input || {}, null, 2);
  }
}

function renderCoffeeResult(data) {
  appraisal.classList.remove("no-result");
  const coffee = data.coffee;
  const rating = data.prediction.rating;
  const verdict = data.prediction.value.verdict;
  const delta = data.prediction.value.listed_vs_predicted_delta_pct;

  const kickerParts = ["The Verdict"];
  const name = [coffee.coffee_name, isMissing(coffee.origin_country) ? null : coffee.origin_country]
    .filter(Boolean)
    .join(", ");
  if (name) kickerParts.push(name);
  kicker.textContent = kickerParts.join(" · ");

  setVerdictHead(VERDICT_COPY[verdict] || { head: "", em: verdict.replaceAll("_", " "), tail: ".", cls: "" });

  verdictDek.innerHTML = "";
  if (delta != null) {
    const spanIntro = document.createTextNode("The listed price sits ");
    const strong = document.createElement("strong");
    strong.className = delta >= 0 ? "delta-over" : "delta-under";
    strong.textContent = `${Math.abs(delta).toFixed(1)}% ${delta >= 0 ? "above" : "below"}`;
    verdictDek.appendChild(spanIntro);
    verdictDek.appendChild(strong);
    verdictDek.appendChild(document.createTextNode(" the model's fair estimate. "));
  } else {
    verdictDek.appendChild(
      document.createTextNode("The ledger needs both a listed price and a fair-price prediction to judge value. ")
    );
  }
  const phrase = ratingPhrase(rating.predicted);
  if (phrase) {
    verdictDek.appendChild(
      document.createTextNode(
        `Predicted quality of ${formatNumber(rating.predicted, 1)} suggests a ${phrase} cup.`
      )
    );
  }

  if (data.is_specialty_coffee === false) {
    caveat.textContent =
      "Caveat: this looks like commodity rather than specialty coffee. The models are trained on specialty lots — read this appraisal skeptically.";
    caveat.classList.remove("hidden");
  }

  renderScore(rating);
  renderLedger(data);
  renderTariff(data);
}

function renderNonCoffee(data) {
  appraisal.classList.add("no-result");
  kicker.textContent = "No Appraisal";
  const copy = PAGE_TYPE_COPY[data.page_type] || {
    head: "The ledger declined this page.",
    dek: "The extractor could not treat this page as a coffee product.",
  };
  plainHead(copy.head);
  verdictDek.textContent = `${copy.dek} Recognizing non-coffee pages (instead of hallucinating a coffee) is part of the extraction contract.`;
}

function render(data, elapsedSeconds) {
  currentData = data;
  appraisal.classList.remove("is-pending");
  caveat.classList.add("hidden");
  if (data.page_type === "coffee_product") {
    renderCoffeeResult(data);
  } else {
    renderNonCoffee(data);
  }
  renderRecord(data, elapsedSeconds);
  renderAppendix();
}

function renderError(message, elapsedSeconds) {
  currentData = null;
  recordLog.querySelectorAll(".working").forEach((el) => el.classList.remove("working"));
  appraisal.classList.remove("is-pending");
  appraisal.classList.add("no-result");
  kicker.textContent = "No Appraisal";
  plainHead("The appraisal failed.");
  verdictDek.textContent = message;
  caveat.classList.add("hidden");
  logLine(`error ${message}`, "err", elapsedSeconds);
  renderAppendix();
}

/* ---------- submit flow ---------- */

function startLoading(url) {
  appraisal.classList.remove("hidden", "no-result");
  appraisal.classList.add("is-pending");
  caveat.classList.add("hidden");
  kicker.textContent = "In Progress";
  plainHead("Appraising…");
  verdictDek.textContent = "Fetching the page, extracting details, and running the models.";
  analyzeButton.disabled = true;
  urlInput.disabled = true;
  statusNote.classList.remove("is-error");

  clearLog();
  logLine(`POST /api/analyze ${url}`, "", 0);
  const working = logLine("fetch · extract · normalize · predict", "dim working");
  const startedAt = performance.now();
  workingTimer = setInterval(() => {
    const seconds = (performance.now() - startedAt) / 1000;
    statusNote.textContent = `appraising — ${seconds.toFixed(0)}s elapsed`;
  }, 1000);
  statusNote.textContent = "appraising — 0s elapsed";
  return { startedAt, working };
}

function stopLoading() {
  clearInterval(workingTimer);
  workingTimer = null;
  analyzeButton.disabled = false;
  urlInput.disabled = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  if (!url) return;
  const { startedAt } = startLoading(url);
  let elapsed = 0;
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    elapsed = (performance.now() - startedAt) / 1000;
    if (!response.ok) {
      let detail = `The analysis service returned ${response.status}.`;
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const body = await response.json().catch(() => null);
        if (body?.detail) {
          detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        }
      }
      throw new Error(detail);
    }
    const data = await response.json();
    render(data, elapsed);
    statusNote.textContent = `appraisal complete in ${elapsed.toFixed(1)}s`;
  } catch (error) {
    elapsed = elapsed || (performance.now() - startedAt) / 1000;
    const message =
      error instanceof TypeError
        ? "Could not reach the analysis service. Check your connection and try again."
        : error.message;
    renderError(message, elapsed);
    statusNote.textContent = message;
    statusNote.classList.add("is-error");
  } finally {
    stopLoading();
  }
});

/* ---------- appendix controls ---------- */

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    currentTab = tab.dataset.tab;
    renderAppendix();
    appendixContent.classList.remove("hidden");
    toggleAppendix.textContent = "Hide";
    toggleAppendix.setAttribute("aria-expanded", "true");
  });
});

toggleAppendix.addEventListener("click", () => {
  const nowHidden = appendixContent.classList.toggle("hidden");
  toggleAppendix.textContent = nowHidden ? "Show" : "Hide";
  toggleAppendix.setAttribute("aria-expanded", String(!nowHidden));
});

/* ---------- masthead date ---------- */

document.querySelector("#issueDate").textContent = new Date().toLocaleDateString("en-US", {
  year: "numeric",
  month: "long",
  day: "numeric",
});
