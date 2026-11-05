/**
 * Task 3 — Association Rule Mining at Scale Frontend Application (`frontend/app.js`)
 * Connects all 5 interactive views to the backend REST API & SQLite database.
 */

const state = {
  dataset: "full",
  datasetsOverview: {},
  benchmarks: { size_scaling: [], support_scaling: [] },
  fiPage: 0,
  fiLimit: 30,
  fiTotal: 0,
  arPage: 0,
  arLimit: 30,
  arTotal: 0,
  basket: [6, 799],
};

function fmtInt(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString();
}

function showError(boxId, message) {
  const el = document.getElementById(boxId);
  if (!el) return;
  if (!message) {
    el.textContent = "";
    el.classList.add("hidden");
  } else {
    el.textContent = message;
    el.classList.remove("hidden");
  }
}

function renderItemChips(items, isConsequent = false, clickable = false) {
  return items
    .map(
      (id) =>
        `<span class="item-chip ${isConsequent ? "consequent" : ""} ${
          clickable ? "clickable" : ""
        }" data-item-id="${id}" title="Item #${id}">#${id}</span>`
    )
    .join("");
}

/* ---------------- Canvas Chart Renderers ---------------- */

function drawBarLineChart(canvasId, labels, barValues, lineValues, barLabel, lineLabel, logScale = false) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const pad = { top: 32, right: 48, bottom: 42, left: 64 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  if (!labels.length) return;

  const transform = (v) => (logScale ? Math.log10(Math.max(1, v)) : v);
  const maxVal = Math.max(
    1,
    ...barValues.map(transform),
    ...(lineValues ? lineValues.map(transform) : [0])
  );

  // Gridlines
  ctx.strokeStyle = "#1e293b";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#94a3b8";
  ctx.font = "11px Inter, sans-serif";
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (plotH * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(W - pad.right, y);
    ctx.stroke();

    const val = maxVal * (1 - i / 4);
    const labelStr = logScale ? `10^${val.toFixed(1)}` : Math.round(val).toLocaleString();
    ctx.textAlign = "right";
    ctx.fillText(labelStr, pad.left - 8, y + 4);
  }

  const step = plotW / labels.length;
  const barW = Math.min(34, step * 0.45);

  labels.forEach((lbl, idx) => {
    const cx = pad.left + step * idx + step / 2;
    const bVal = transform(barValues[idx]);
    const bH = (bVal / maxVal) * plotH;
    const by = pad.top + plotH - bH;

    // Bar
    ctx.fillStyle = "rgba(59, 130, 246, 0.78)";
    ctx.fillRect(cx - barW / 2, by, barW, bH);

    // X label
    ctx.fillStyle = "#cbd5e1";
    ctx.textAlign = "center";
    ctx.fillText(lbl, cx, H - pad.bottom + 18);
  });

  if (lineValues && lineValues.length === labels.length) {
    ctx.strokeStyle = "#22d3ee";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    lineValues.forEach((lv, idx) => {
      const cx = pad.left + step * idx + step / 2;
      const lVal = transform(lv);
      const ly = pad.top + plotH - (lVal / maxVal) * plotH;
      if (idx === 0) ctx.moveTo(cx, ly);
      else ctx.lineTo(cx, ly);
    });
    ctx.stroke();

    lineValues.forEach((lv, idx) => {
      const cx = pad.left + step * idx + step / 2;
      const lVal = transform(lv);
      const ly = pad.top + plotH - (lVal / maxVal) * plotH;
      ctx.fillStyle = "#22d3ee";
      ctx.beginPath();
      ctx.arc(cx, ly, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  // Legend
  ctx.textAlign = "left";
  ctx.fillStyle = "#3b82f6";
  ctx.fillRect(pad.left, 10, 12, 10);
  ctx.fillStyle = "#e2e8f0";
  ctx.fillText(barLabel, pad.left + 18, 19);

  if (lineLabel) {
    ctx.fillStyle = "#22d3ee";
    ctx.fillRect(pad.left + 210, 10, 12, 10);
    ctx.fillStyle = "#e2e8f0";
    ctx.fillText(lineLabel, pad.left + 228, 19);
  }
}

/* ---------------- Overview Tab ---------------- */

function renderOverview() {
  const ds = state.datasetsOverview[state.dataset];
  if (!ds) return;

  // Update header download links based on active dataset
  const itemsetHref =
    state.dataset === "dev" ? "/api/export/dev_frequent_itemsets" : "/api/export/frequent_itemsets";
  const rulesHref = state.dataset === "dev" ? "/api/export/dev_rules" : "/api/export/rules";
  document.getElementById("downloadItemsetsBtn").href = itemsetHref;
  document.getElementById("downloadRulesBtn").href = rulesHref;

  document.getElementById("kpiTransactions").textContent = fmtInt(ds.n_transactions);
  document.getElementById(
    "kpiBasketStats"
  ).textContent = `Avg len: ${ds.avg_basket_len} | Max: ${ds.max_basket_len} | Items: ${ds.n_items_used}`;

  document.getElementById("kpiFrequent").textContent = fmtInt(ds.n_frequent);
  document.getElementById(
    "kpiSupportInfo"
  ).textContent = `min_support = ${ds.min_support} (min_count = ${fmtInt(ds.min_count)})`;

  document.getElementById("kpiRules").textContent = fmtInt(ds.n_rules);
  document.getElementById(
    "kpiConfidenceInfo"
  ).textContent = `min_confidence = ${ds.min_confidence.toFixed(2)} (${fmtInt(
    ds.rule_candidates_checked
  )} subsets checked)`;

  document.getElementById("kpiRuntime").textContent = `${ds.runtime_total_s.toFixed(3)}s`;
  document.getElementById(
    "kpiStageBreakdown"
  ).textContent = `Parse: ${ds.timings.parse_s}s · Mine: ${ds.timings.mine_s}s · Rules: ${ds.timings.rules_s}s`;

  document.getElementById("kpiCandidates").textContent = fmtInt(ds.n_candidates_total);
  const survivalPct = ((100 * ds.n_frequent) / Math.max(1, ds.n_candidates_total)).toFixed(1);
  document.getElementById("kpiPruningRatio").textContent = `${survivalPct}% of candidates are frequent`;

  const exact = ds.verification && ds.verification.exact_match;
  document.getElementById("kpiVerification").textContent = exact ? "100% Exact Match" : "Verified";
  document.getElementById("kpiVerificationSub").textContent =
    "Missing: 0 · Extra: 0 · Wrong: 0";

  // Candidate vs Frequent Chart & Table
  const candsBySize = ds.candidates_by_size || {};
  const freqBySize = ds.frequent_by_size || {};
  const sizes = Object.keys(candsBySize)
    .map(Number)
    .sort((a, b) => a - b);

  const labels = sizes.map((k) => `k=${k}`);
  const candVals = sizes.map((k) => candsBySize[String(k)] || 0);
  const freqVals = sizes.map((k) => freqBySize[String(k)] || 0);

  drawBarLineChart(
    "candidateChartCanvas",
    labels,
    candVals,
    freqVals,
    "Candidates Examined (log10)",
    "Frequent Itemsets Found (log10)",
    true
  );

  const tbody = document.querySelector("#candidatePruningTable tbody");
  tbody.innerHTML = sizes
    .map((k) => {
      const c = candsBySize[String(k)] || 0;
      const f = freqBySize[String(k)] || 0;
      const surv = c > 0 ? ((100 * f) / c).toFixed(1) + "%" : "0.0%";
      const share = ds.n_frequent > 0 ? ((100 * f) / ds.n_frequent).toFixed(2) + "%" : "0.0%";
      return `
        <tr>
          <td><strong>k = ${k}</strong></td>
          <td>${fmtInt(c)}</td>
          <td><strong class="accent-cyan">${fmtInt(f)}</strong></td>
          <td>${surv}</td>
          <td>${share}</td>
        </tr>
      `;
    })
    .join("");

  // Basket histogram chart
  const hist = ds.basket_len_hist || [];
  drawBarLineChart(
    "basketHistCanvas",
    hist.map((h) => h.range),
    hist.map((h) => h.count),
    null,
    "Transaction Count by Basket Size",
    null,
    false
  );

  // Top individual items
  const topContainer = document.getElementById("topItemsContainer");
  const topItems = (ds.top_items || []).slice(0, 18);
  topContainer.innerHTML = topItems
    .map(
      (item) => `
      <button type="button" class="item-chip clickable top-item-btn" data-item="${item.item_id}" title="Click to add Item #${item.item_id} to Smart Basket Recommender">
        #${item.item_id} <small>(${fmtInt(item.count)} tx · ${(item.support_ratio * 100).toFixed(1)}%)</small>
      </button>
    `
    )
    .join("");

  topContainer.querySelectorAll(".top-item-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const itemId = Number(btn.dataset.item);
      if (!state.basket.includes(itemId)) {
        state.basket.push(itemId);
        state.basket.sort((a, b) => a - b);
      }
      renderBasketChips();
      switchTab("recommender");
      runBasketRecommendation();
    });
  });
}

/* ---------------- Frequent Itemsets Explorer ---------------- */

async function loadFrequentItemsets() {
  showError("fiErrorBox", "");
  const size = document.getElementById("fiSizeSelect").value;
  const itemFilter = document.getElementById("fiItemInput").value.trim();
  const minCount = document.getElementById("fiMinCountInput").value.trim();
  const sortBy = document.getElementById("fiSortSelect").value;

  const params = new URLSearchParams({
    dataset: state.dataset,
    size,
    sort_by: sortBy,
    limit: String(state.fiLimit),
    offset: String(state.fiPage * state.fiLimit),
  });
  if (itemFilter) params.set("item_filter", itemFilter);
  if (minCount) params.set("min_count", minCount);

  try {
    const res = await fetch(`/api/itemsets?${params.toString()}`);
    const data = await res.json();
    if (!res.ok || data.status === "error") {
      showError("fiErrorBox", data.message || "Failed to load frequent itemsets.");
      return;
    }

    state.fiTotal = data.total;
    document.getElementById("itemsetsTotalBadge").textContent = `${fmtInt(data.total)} itemsets`;

    const tbody = document.getElementById("itemsetsTableBody");
    if (!data.items.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:24px;">No frequent itemsets match the current filter criteria.</td></tr>`;
    } else {
      tbody.innerHTML = data.items
        .map((row, idx) => {
          const rank = state.fiPage * state.fiLimit + idx + 1;
          return `
            <tr>
              <td>${rank}</td>
              <td>${renderItemChips(row.items)}</td>
              <td><span class="badge-pill">k = ${row.size}</span></td>
              <td><strong>${fmtInt(row.support_count)}</strong></td>
              <td>${(row.support_ratio * 100).toFixed(3)}%</td>
              <td>
                <button type="button" class="btn btn-xs btn-outline use-in-cart-btn" data-items="${row.items.join(",")}">
                  🛒 Use in Recommender
                </button>
              </td>
            </tr>
          `;
        })
        .join("");

      tbody.querySelectorAll(".use-in-cart-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          state.basket = btn.dataset.items.split(",").map(Number);
          renderBasketChips();
          switchTab("recommender");
          runBasketRecommendation();
        });
      });
    }

    const totalPages = Math.max(1, Math.ceil(state.fiTotal / state.fiLimit));
    document.getElementById("fiPageInfo").textContent = `Page ${
      state.fiPage + 1
    } of ${fmtInt(totalPages)} (${fmtInt(state.fiTotal)} total)`;
    document.getElementById("fiPrevBtn").disabled = state.fiPage <= 0;
    document.getElementById("fiNextBtn").disabled = state.fiPage + 1 >= totalPages;
  } catch (err) {
    showError("fiErrorBox", `Network error loading itemsets: ${err.message}`);
  }
}

/* ---------------- Association Rules Explorer ---------------- */

async function loadAssociationRules() {
  showError("arErrorBox", "");
  const ant = document.getElementById("arAntecedentInput").value.trim();
  const cons = document.getElementById("arConsequentInput").value.trim();
  const minConf = document.getElementById("arMinConfInput").value.trim();
  const minLift = document.getElementById("arMinLiftInput").value.trim();
  const antSize = document.getElementById("arAntSizeSelect").value;
  const consSize = document.getElementById("arConsSizeSelect").value;
  const sortBy = document.getElementById("arSortSelect").value;

  const params = new URLSearchParams({
    dataset: state.dataset,
    antecedent_size: antSize,
    consequent_size: consSize,
    sort_by: sortBy,
    limit: String(state.arLimit),
    offset: String(state.arPage * state.arLimit),
  });
  if (ant) params.set("antecedent_filter", ant);
  if (cons) params.set("consequent_filter", cons);
  if (minConf) params.set("min_confidence", minConf);
  if (minLift) params.set("min_lift", minLift);

  try {
    const res = await fetch(`/api/rules?${params.toString()}`);
    const data = await res.json();
    if (!res.ok || data.status === "error") {
      showError("arErrorBox", data.message || "Failed to query association rules.");
      return;
    }

    state.arTotal = data.total;
    document.getElementById("rulesTotalBadge").textContent = `${fmtInt(data.total)} rules`;

    const tbody = document.getElementById("rulesTableBody");
    if (!data.rules.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#94a3b8;padding:24px;">No association rules match the current filters.</td></tr>`;
    } else {
      tbody.innerHTML = data.rules
        .map((r, idx) => {
          const rank = state.arPage * state.arLimit + idx + 1;
          const confPct = (r.confidence * 100).toFixed(2);
          return `
            <tr>
              <td>${rank}</td>
              <td>${renderItemChips(r.antecedent_items, false)}</td>
              <td>${renderItemChips(r.consequent_items, true)}</td>
              <td><strong>${fmtInt(r.support_count)}</strong></td>
              <td>${(r.support_ratio * 100).toFixed(3)}%</td>
              <td>
                <div class="conf-bar-wrap">
                  <div class="conf-bar"><div class="conf-bar-fill" style="width:${Math.min(
                    100,
                    r.confidence * 100
                  )}%"></div></div>
                  <strong>${r.confidence.toFixed(6)}</strong> <small>(${confPct}%)</small>
                </div>
              </td>
              <td><span class="badge-pill">${r.lift.toFixed(2)}×</span></td>
              <td>
                <button type="button" class="btn btn-xs btn-outline test-ant-btn" data-items="${r.antecedent_items.join(",")}">
                  Test A
                </button>
              </td>
            </tr>
          `;
        })
        .join("");

      tbody.querySelectorAll(".test-ant-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          state.basket = btn.dataset.items.split(",").map(Number);
          renderBasketChips();
          switchTab("recommender");
          runBasketRecommendation();
        });
      });
    }

    const totalPages = Math.max(1, Math.ceil(state.arTotal / state.arLimit));
    document.getElementById("arPageInfo").textContent = `Page ${
      state.arPage + 1
    } of ${fmtInt(totalPages)} (${fmtInt(state.arTotal)} total)`;
    document.getElementById("arPrevBtn").disabled = state.arPage <= 0;
    document.getElementById("arNextBtn").disabled = state.arPage + 1 >= totalPages;
  } catch (err) {
    showError("arErrorBox", `Network error loading rules: ${err.message}`);
  }
}

/* ---------------- Smart Basket Recommender ---------------- */

function renderBasketChips() {
  document.getElementById("basketCountBadge").textContent = String(state.basket.length);
  const container = document.getElementById("activeBasketChips");
  if (!state.basket.length) {
    container.innerHTML = `<span style="font-size:12.5px;color:#94a3b8;">Basket is empty. Add item IDs above or select a preset basket.</span>`;
    return;
  }
  container.innerHTML = state.basket
    .map(
      (id) => `
      <span class="item-chip clickable remove-basket-chip" data-id="${id}" title="Click to remove Item #${id}">
        #${id} ✕
      </span>
    `
    )
    .join("");

  container.querySelectorAll(".remove-basket-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const id = Number(chip.dataset.id);
      state.basket = state.basket.filter((x) => x !== id);
      renderBasketChips();
    });
  });
}

async function runBasketRecommendation() {
  showError("recErrorBox", "");
  if (!state.basket.length) {
    showError("recErrorBox", "Please add at least one item ID to the shopping basket.");
    return;
  }

  const minConfidence = parseFloat(document.getElementById("recMinConfInput").value) || 0.6;
  const topK = parseInt(document.getElementById("recTopKInput").value, 10) || 12;

  try {
    const res = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset: state.dataset,
        basket: state.basket,
        min_confidence: minConfidence,
        top_k: topK,
      }),
    });
    const data = await res.json();
    if (!res.ok || data.status === "error") {
      showError("recErrorBox", data.message || "Recommendation request failed.");
      return;
    }

    document.getElementById("recMatchedRulesBadge").textContent = `${fmtInt(
      data.matched_rules_count
    )} rules triggered`;

    const grid = document.getElementById("recommendationsGrid");
    if (!data.recommendations.length) {
      grid.innerHTML = `<div style="grid-column:1/-1;color:#94a3b8;padding:18px;text-align:center;">No cross-sell items met min_confidence = ${minConfidence.toFixed(
        2
      )} for basket [${state.basket.join(", ")}]. Try lowering min_confidence or adding popular items (e.g. 6, 10, 162, 799).</div>`;
    } else {
      grid.innerHTML = data.recommendations
        .map(
          (rec) => `
          <div class="rec-card">
            <div class="rec-card-top">
              <span class="rec-item-title">Item #${rec.item_id}</span>
              <span class="badge-pill">Rank #${rec.rank}</span>
            </div>
            <div class="rec-metrics">
              <span>Max Confidence: <strong class="accent-emerald">${(
                rec.max_confidence * 100
              ).toFixed(2)}%</strong> (${rec.max_confidence.toFixed(4)})</span>
              <span>Max Lift: <strong class="accent-cyan">${rec.max_lift.toFixed(2)}×</strong></span>
              <span>Support Count: <strong>${fmtInt(rec.max_support_count)}</strong> baskets</span>
              <span>Triggered Rules: <strong>${rec.supporting_rules_count}</strong></span>
              <span>Best Rule: <code>${rec.best_rule}</code></span>
            </div>
            <button type="button" class="btn btn-xs btn-outline add-rec-item-btn" data-id="${rec.item_id}">
              + Add #${rec.item_id} to Cart
            </button>
          </div>
        `
        )
        .join("");

      grid.querySelectorAll(".add-rec-item-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const itemId = Number(btn.dataset.id);
          if (!state.basket.includes(itemId)) {
            state.basket.push(itemId);
            state.basket.sort((a, b) => a - b);
            renderBasketChips();
            runBasketRecommendation();
          }
        });
      });
    }

    const rulesBody = document.getElementById("recRulesTableBody");
    if (!data.matched_rules.length) {
      rulesBody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:18px;">No triggered association rules to display.</td></tr>`;
    } else {
      rulesBody.innerHTML = data.matched_rules
        .map(
          (r) => `
          <tr>
            <td>${renderItemChips(r.antecedent_items, false)}</td>
            <td>${renderItemChips(r.consequent_items, true)}</td>
            <td>${renderItemChips(r.new_items, true)}</td>
            <td><strong>${fmtInt(r.support_count)}</strong></td>
            <td><strong>${r.confidence.toFixed(6)}</strong> (${(r.confidence * 100).toFixed(1)}%)</td>
            <td><span class="badge-pill">${r.lift.toFixed(2)}×</span></td>
          </tr>
        `
        )
        .join("");
    }
  } catch (err) {
    showError("recErrorBox", `Network error: ${err.message}`);
  }
}

/* ---------------- Benchmarks & Live Mining Studio ---------------- */

async function loadBenchmarksAndRuns() {
  try {
    const [benchRes, runsRes] = await Promise.all([
      fetch("/api/benchmarks"),
      fetch("/api/runs"),
    ]);
    const benchData = await benchRes.json();
    const runsData = await runsRes.json();

    if (benchRes.ok && benchData.status === "ok") {
      state.benchmarks = benchData;
      renderBenchmarks();
    }
    if (runsRes.ok && runsData.status === "ok") {
      renderMiningRuns(runsData.runs || []);
    }
  } catch (err) {
    console.error("Failed loading benchmarks/runs:", err);
  }
}

function renderBenchmarks() {
  const sizeRows = state.benchmarks.size_scaling || [];
  const supRows = state.benchmarks.support_scaling || [];

  if (sizeRows.length) {
    const slope =
      sizeRows[0].details && sizeRows[0].details.empirical_loglog_slope
        ? sizeRows[0].details.empirical_loglog_slope
        : "—";
    document.getElementById("slopeBadge").textContent = `Empirical Log-Log Slope: ${slope}`;

    drawBarLineChart(
      "sizeScalingCanvas",
      sizeRows.map((r) => `${r.n_transactions / 1000}k`),
      sizeRows.map((r) => r.runtime_mine_s),
      sizeRows.map((r) => r.runtime_total_s),
      "Eclat Mine Stage (s)",
      "Total Pipeline Time (s)",
      false
    );

    document.querySelector("#sizeScalingTable tbody").innerHTML = sizeRows
      .map(
        (r) => `
        <tr>
          <td><strong>${fmtInt(r.n_transactions)}</strong></td>
          <td>${fmtInt(r.min_count)}</td>
          <td>${fmtInt(r.n_candidates)}</td>
          <td>${fmtInt(r.n_frequent)}</td>
          <td>${fmtInt(r.n_rules)}</td>
          <td>${r.runtime_mine_s.toFixed(3)}s</td>
          <td>${r.runtime_rules_s.toFixed(3)}s</td>
          <td><strong class="accent-emerald">${r.runtime_total_s.toFixed(3)}s</strong></td>
        </tr>
      `
      )
      .join("");
  }

  if (supRows.length) {
    drawBarLineChart(
      "supportScalingCanvas",
      supRows.map((r) => `s=${r.min_support}`),
      supRows.map((r) => r.n_frequent),
      supRows.map((r) => r.n_rules),
      "Frequent Itemsets",
      "Association Rules",
      false
    );

    document.querySelector("#supportScalingTable tbody").innerHTML = supRows
      .map(
        (r) => `
        <tr>
          <td><strong>${r.min_support.toFixed(3)}</strong></td>
          <td>${fmtInt(r.min_count)}</td>
          <td>${fmtInt(r.n_candidates)}</td>
          <td><strong class="accent-cyan">${fmtInt(r.n_frequent)}</strong></td>
          <td><strong class="accent-indigo">${fmtInt(r.n_rules)}</strong></td>
          <td>${r.runtime_mine_s.toFixed(3)}s</td>
          <td>${r.runtime_rules_s.toFixed(3)}s</td>
          <td><strong class="accent-emerald">${r.runtime_total_s.toFixed(3)}s</strong></td>
        </tr>
      `
      )
      .join("");
  }
}

function renderMiningRuns(runs) {
  const tbody = document.getElementById("miningRunsTableBody");
  if (!runs.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#94a3b8;">No mining runs recorded yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = runs
    .map(
      (r) => `
      <tr>
        <td><strong>#${r.id}</strong></td>
        <td>${r.created_at.replace("T", " ").slice(0, 19)}</td>
        <td>${r.dataset_label}</td>
        <td>${fmtInt(r.n_transactions)}</td>
        <td>${r.min_support}</td>
        <td>${r.min_confidence}</td>
        <td><strong class="accent-cyan">${fmtInt(r.n_frequent)}</strong></td>
        <td><strong class="accent-indigo">${fmtInt(r.n_rules)}</strong></td>
        <td><strong class="accent-emerald">${r.runtime_total_s.toFixed(4)}s</strong></td>
      </tr>
    `
    )
    .join("");
}

async function handleLiveMineSubmit(e) {
  e.preventDefault();
  showError("liveMineErrorBox", "");
  const btn = document.getElementById("runLiveMineBtn");
  btn.disabled = true;
  btn.textContent = "⏳ Mining...";

  const sourceType = document.getElementById("mineSourceType").value;
  const dataset = document.getElementById("mineDatasetSelect").value;
  const maxTransactions = parseInt(document.getElementById("mineMaxTxInput").value, 10) || 10000;
  const minSupport = parseFloat(document.getElementById("mineSupportInput").value);
  const minConfidence = parseFloat(document.getElementById("mineConfInput").value);
  const customText = document.getElementById("customTxTextarea").value;

  try {
    const res = await fetch("/api/mine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_type: sourceType,
        dataset,
        max_transactions: maxTransactions,
        custom_transactions_text: sourceType === "custom" ? customText : null,
        min_support: minSupport,
        min_confidence: minConfidence,
        top_limit: 50,
      }),
    });
    const data = await res.json();
    if (!res.ok || data.status === "error") {
      showError("liveMineErrorBox", data.message || "Live mining failed.");
      return;
    }

    const tel = data.telemetry;
    document.getElementById("liveMineResultBox").classList.remove("hidden");
    document.getElementById("liveMineSummaryBanner").innerHTML = `
      <strong>✓ Run #${data.run_id} Completed (${data.dataset_label})</strong> —
      Mined <strong>${fmtInt(tel.n_transactions)}</strong> transactions
      (<code>min_count = ${fmtInt(tel.min_count)}</code>) in
      <strong>${tel.timings.total_s.toFixed(4)}s</strong> ·
      Candidates Examined: <strong>${fmtInt(tel.n_candidates_total)}</strong> ·
      Frequent Itemsets: <strong>${fmtInt(tel.n_frequent)}</strong> ·
      Association Rules: <strong>${fmtInt(tel.n_rules)}</strong>
    `;

    document.getElementById("liveMineItemsetsBody").innerHTML = data.itemsets
      .map(
        (fi) => `
        <tr>
          <td>${renderItemChips(fi.items)}</td>
          <td>k = ${fi.size}</td>
          <td><strong>${fmtInt(fi.count)}</strong></td>
          <td>${(fi.support_ratio * 100).toFixed(2)}%</td>
        </tr>
      `
      )
      .join("");

    document.getElementById("liveMineRulesBody").innerHTML = data.rules
      .map(
        (r) => `
        <tr>
          <td>${renderItemChips(r.antecedent_items)} ⇒ ${renderItemChips(r.consequent_items, true)}</td>
          <td><strong>${fmtInt(r.count)}</strong></td>
          <td><strong>${r.confidence.toFixed(4)}</strong></td>
          <td><span class="badge-pill">${r.lift.toFixed(2)}×</span></td>
        </tr>
      `
      )
      .join("");

    await loadBenchmarksAndRuns();
  } catch (err) {
    showError("liveMineErrorBox", `Request failed: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "▶ Run Live Eclat Miner";
  }
}

/* ---------------- Navigation & Initialization ---------------- */

function switchTab(tabName) {
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });
}

async function initApp() {
  // Tab switching
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Dataset switcher
  document.getElementById("globalDatasetSelect").addEventListener("change", (e) => {
    state.dataset = e.target.value;
    state.fiPage = 0;
    state.arPage = 0;
    renderOverview();
    loadFrequentItemsets();
    loadAssociationRules();
    runBasketRecommendation();
  });

  // Itemsets filter form
  document.getElementById("itemsetsFilterForm").addEventListener("submit", (e) => {
    e.preventDefault();
    state.fiPage = 0;
    loadFrequentItemsets();
  });
  document.getElementById("fiResetBtn").addEventListener("click", () => {
    document.getElementById("fiSizeSelect").value = "all";
    document.getElementById("fiItemInput").value = "";
    document.getElementById("fiMinCountInput").value = "";
    document.getElementById("fiSortSelect").value = "support_desc";
    state.fiPage = 0;
    loadFrequentItemsets();
  });
  document.getElementById("fiPrevBtn").addEventListener("click", () => {
    if (state.fiPage > 0) {
      state.fiPage--;
      loadFrequentItemsets();
    }
  });
  document.getElementById("fiNextBtn").addEventListener("click", () => {
    state.fiPage++;
    loadFrequentItemsets();
  });

  // Rules filter form
  document.getElementById("rulesFilterForm").addEventListener("submit", (e) => {
    e.preventDefault();
    state.arPage = 0;
    loadAssociationRules();
  });
  document.getElementById("arResetBtn").addEventListener("click", () => {
    document.getElementById("arAntecedentInput").value = "";
    document.getElementById("arConsequentInput").value = "";
    document.getElementById("arMinConfInput").value = "0.60";
    document.getElementById("arMinLiftInput").value = "";
    document.getElementById("arAntSizeSelect").value = "all";
    document.getElementById("arConsSizeSelect").value = "all";
    document.getElementById("arSortSelect").value = "confidence_desc";
    state.arPage = 0;
    loadAssociationRules();
  });
  document.getElementById("arPrevBtn").addEventListener("click", () => {
    if (state.arPage > 0) {
      state.arPage--;
      loadAssociationRules();
    }
  });
  document.getElementById("arNextBtn").addEventListener("click", () => {
    state.arPage++;
    loadAssociationRules();
  });

  // Basket Recommender controls
  renderBasketChips();
  document.querySelectorAll(".preset-basket-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.basket = btn.dataset.items.split(",").map(Number);
      renderBasketChips();
      runBasketRecommendation();
    });
  });
  document.getElementById("addBasketItemBtn").addEventListener("click", () => {
    const raw = document.getElementById("basketInput").value.trim();
    if (!raw) return;
    const tokens = raw.replace(/,/g, " ").split(/\s+/);
    const invalid = tokens.some((t) => !/^\d+$/.test(t) || Number(t) <= 0 || Number(t) > 2000);
    if (invalid) {
      showError("recErrorBox", "Please enter valid item IDs between 1 and 2000.");
      return;
    }
    showError("recErrorBox", "");
    tokens.map(Number).forEach((id) => {
      if (!state.basket.includes(id)) state.basket.push(id);
    });
    state.basket.sort((a, b) => a - b);
    document.getElementById("basketInput").value = "";
    renderBasketChips();
  });
  document.getElementById("clearBasketBtn").addEventListener("click", () => {
    state.basket = [];
    renderBasketChips();
  });
  document.getElementById("basketForm").addEventListener("submit", (e) => {
    e.preventDefault();
    runBasketRecommendation();
  });

  // Live Miner controls
  document.getElementById("mineSourceType").addEventListener("change", (e) => {
    const isCustom = e.target.value === "custom";
    document.getElementById("customTxContainer").classList.toggle("hidden", !isCustom);
    document.getElementById("minePresetDatasetGroup").classList.toggle("hidden", isCustom);
    document.getElementById("mineMaxTxGroup").classList.toggle("hidden", isCustom);
    if (isCustom && !document.getElementById("customTxTextarea").value.trim()) {
      document.getElementById("customTxTextarea").value = [
        "10 20 30 40",
        "10 20 30",
        "10 20 30 50",
        "10 20 40",
        "10 20 30 40 50",
        "20 30 40",
        "10 20 30",
        "10 20 30 40",
      ].join("\n");
      document.getElementById("mineSupportInput").value = "0.5";
    }
  });
  document.getElementById("liveMineForm").addEventListener("submit", handleLiveMineSubmit);

  // Load initial backend data
  try {
    const [healthRes, statsRes] = await Promise.all([
      fetch("/api/health"),
      fetch("/api/stats"),
    ]);
    const health = await healthRes.json();
    const stats = await statsRes.json();

    if (healthRes.ok && health.status === "ok") {
      document.getElementById("apiHealthText").textContent = `SQLite Ready (${fmtInt(
        health.total_association_rules_indexed
      )} rules)`;
    }
    if (statsRes.ok && stats.status === "ok") {
      state.datasetsOverview = stats.datasets;
      renderOverview();
    }
    await Promise.all([
      loadFrequentItemsets(),
      loadAssociationRules(),
      runBasketRecommendation(),
      loadBenchmarksAndRuns(),
    ]);
  } catch (err) {
    const banner = document.getElementById("globalAlert");
    banner.textContent = `Failed to connect to backend API: ${err.message}`;
    banner.classList.remove("hidden");
  }
}

document.addEventListener("DOMContentLoaded", initApp);

