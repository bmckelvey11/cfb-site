(function () {
  "use strict";

  const dialog = document.getElementById("filter-modal");
  const filtersForm = document.getElementById("filters-form");
  if (!dialog || !filtersForm) {
    return;
  }

  const titleEl = document.getElementById("filter-modal-title");
  const aboutEl = document.getElementById("filter-modal-about");
  const controlsEl = document.getElementById("filter-modal-controls");
  const exploreEl = document.getElementById("filter-modal-explore");
  const emptyEl = document.getElementById("filter-modal-empty");
  const statusEl = document.getElementById("filter-modal-status");
  const recordEl = document.getElementById("filter-modal-record");
  const moneyEl = document.getElementById("filter-modal-money");
  const roiEl = document.getElementById("filter-modal-roi");
  const saveBtn = document.getElementById("filter-modal-save");
  const cancelBtn = document.getElementById("filter-modal-cancel");
  const closeBtn = document.getElementById("filter-modal-close");
  const viewToggle = document.getElementById("filter-modal-view-toggle");
  const viewChartBtn = document.getElementById("filter-modal-view-chart");
  const viewListBtn = document.getElementById("filter-modal-view-list");
  const maxRoiBtn = document.getElementById("filter-modal-max-roi");

  const CORE_PARAM = {
    "core:season": "filter_seasons",
    "core:week": "filter_weeks",
    "core:team": "filter_teams",
    "core:conference": "filter_conferences",
    "core:provider": "filter_providers",
  };

  const CORE_RANGE_FIELDS = {
    "core:spread_range": { min: "min_spread", max: "max_spread" },
    "core:total_range": { min: "min_total", max: "max_total" },
  };

  let launcher = null;
  let state = null;
  let lastSummary = null;
  let liveOk = false;
  let liveGeneration = 0;
  let liveAbort = null;
  let liveTimer = null;
  let detailGeneration = 0;
  const LIVE_DEBOUNCE_MS = 250;

  const PERSPECTIVE_OPTIONS = [
    { value: "bet_side", label: "Bet-side" },
    { value: "opponent", label: "Opponent" },
    { value: "either", label: "Either" },
  ];

  document.documentElement.classList.add("js");

  function defaultPerspective() {
    const betTypeEl = filtersForm.querySelector('[name="bet_type"]');
    const betType = betTypeEl ? String(betTypeEl.value || "spread") : "spread";
    return betType === "total" ? "either" : "bet_side";
  }

  function syncBetSideFieldsets() {
    const betTypeEl = filtersForm.querySelector('[name="bet_type"]');
    const spreadFieldset = document.getElementById("spread-side-fieldset");
    const totalFieldset = document.getElementById("total-side-fieldset");
    if (!betTypeEl || !spreadFieldset || !totalFieldset) {
      return;
    }
    const isTotal = betTypeEl.value === "total";
    // Grey out via a class, NOT the disabled attribute: disabled controls are
    // omitted from FormData, so the server would fall back to its "home"/"over"
    // default and silently overwrite the side the user actually picked -- which
    // then gets persisted by Save System.
    spreadFieldset.classList.toggle("fieldset-inactive", isTotal);
    totalFieldset.classList.toggle("fieldset-inactive", !isTotal);
  }

  syncBetSideFieldsets();
  const betTypeSelect = filtersForm.querySelector('[name="bet_type"]');
  if (betTypeSelect) {
    betTypeSelect.addEventListener("change", syncBetSideFieldsets);
  }

  function resolveInitialPerspective(button, committed) {
    const teamScoped = button.getAttribute("data-team-scoped") === "1";
    if (!teamScoped) {
      return "single";
    }
    const fromEdit = button.getAttribute("data-perspective");
    if (fromEdit) {
      return fromEdit;
    }
    if (committed && committed.perspective && committed.perspective !== "single") {
      return committed.perspective;
    }
    return defaultPerspective();
  }

  function formatMoney(moneyWon) {
    if (moneyWon > 0) {
      return "+$" + Math.round(moneyWon).toLocaleString("en-US");
    }
    if (moneyWon < 0) {
      return "-$" + Math.round(Math.abs(moneyWon)).toLocaleString("en-US");
    }
    return "$0";
  }

  function formatRoiFixed(roi) {
    return (Number(roi) * 100).toFixed(2) + "%";
  }

  function formatRowMoney(money) {
    if (money > 0) {
      return "+$" + Math.round(money).toLocaleString("en-US");
    }
    if (money < 0) {
      return "-$" + Math.round(Math.abs(money)).toLocaleString("en-US");
    }
    return "$0";
  }

  function formatRowRoi(roi) {
    return (Number(roi) * 100).toFixed(2) + "%";
  }

  // Snap numeric controls to a sensible interval instead of continuous input.
  // Scaled off the feature's domain span so betting lines (spread ~120, total
  // ~70) land on the half-point convention the sidebar inputs already use,
  // while 0-1 rate features keep enough granularity to stay usable — a flat
  // 0.5 would collapse those sliders to three positions.
  function stepForDomain(domainMin, domainMax) {
    const span = Math.abs(Number(domainMax) - Number(domainMin));
    if (!isFinite(span) || span === 0) {
      return "any";
    }
    if (span <= 2) {
      return "0.01";
    }
    if (span <= 20) {
      return "0.1";
    }
    if (span <= 1000) {
      return "0.5";
    }
    return "1";
  }

  function applyChipTone(el, value) {
    el.classList.remove("positive", "negative");
    if (value > 0) {
      el.classList.add("positive");
    } else if (value < 0) {
      el.classList.add("negative");
    }
  }

  function renderChips(summary) {
    recordEl.textContent = summary.wins + "-" + summary.losses + "-" + summary.pushes;
    moneyEl.textContent = formatMoney(summary.money_won);
    roiEl.textContent = formatRoiFixed(summary.roi);
    applyChipTone(moneyEl, summary.money_won);
    applyChipTone(roiEl, summary.roi);
    const total = summary.wins + summary.losses + summary.pushes;
    emptyEl.hidden = total > 0;
  }

  function setUpdating(updating) {
    statusEl.replaceChildren();
    if (updating) {
      statusEl.textContent = "Updating…";
    }
    recordEl.style.opacity = updating ? "0.55" : "1";
    moneyEl.style.opacity = updating ? "0.55" : "1";
    roiEl.style.opacity = updating ? "0.55" : "1";
  }

  function showLiveError() {
    statusEl.textContent = "";
    statusEl.replaceChildren();
    const msg = document.createElement("span");
    msg.textContent = "Couldn’t update live stats. ";
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "filter-modal__retry";
    retry.textContent = "Retry";
    retry.addEventListener("click", () => {
      refreshLive({ immediate: true });
    });
    statusEl.appendChild(msg);
    statusEl.appendChild(retry);
    recordEl.style.opacity = "1";
    moneyEl.style.opacity = "1";
    roiEl.style.opacity = "1";
  }

  function abortLiveFetch() {
    if (liveTimer != null) {
      window.clearTimeout(liveTimer);
      liveTimer = null;
    }
    if (liveAbort) {
      liveAbort.abort();
      liveAbort = null;
    }
  }

  function committedCoreList(paramName) {
    const select = filtersForm.querySelector('[name="' + paramName + '"]');
    if (!select) {
      return [];
    }
    const value = String(select.value || "").trim();
    if (!value) {
      return [];
    }
    return value.split(",").map((part) => part.trim()).filter(Boolean);
  }

  function committedFeature(key) {
    const fallback = document.querySelector('[data-fallback-for="feature:' + key + '"]');
    if (!fallback) {
      return null;
    }
    const enable = fallback.querySelector('input[name="ff_enable"]');
    if (!enable || !enable.checked) {
      return null;
    }
    const opEl = fallback.querySelector('[name="ff_op"]');
    const valueEl = fallback.querySelector('[name="ff_value"]');
    const perspectiveEl = fallback.querySelector('[name="ff_perspective"]');
    const raw = valueEl ? String(valueEl.value || "") : "";
    let values;
    if (opEl && opEl.value === "in") {
      values = raw.split(",").map((part) => part.trim()).filter(Boolean);
    } else if (raw === "true" || raw === "false") {
      values = [raw === "true"];
    } else {
      values = raw ? [raw] : [];
    }
    return {
      op: opEl ? opEl.value : "eq",
      values: values,
      perspective: perspectiveEl ? perspectiveEl.value : "single",
    };
  }

  function committedNumericBounds(candidateId) {
    const fields = CORE_RANGE_FIELDS[candidateId];
    if (fields) {
      const minEl = filtersForm.querySelector('[name="' + fields.min + '"]');
      const maxEl = filtersForm.querySelector('[name="' + fields.max + '"]');
      const minRaw = minEl ? String(minEl.value || "").trim() : "";
      const maxRaw = maxEl ? String(maxEl.value || "").trim() : "";
      if (minRaw === "" && maxRaw === "") {
        return null;
      }
      return {
        min: minRaw === "" ? null : Number(minRaw),
        max: maxRaw === "" ? null : Number(maxRaw),
        perspective: "single",
      };
    }
    if (candidateId.indexOf("feature:") !== 0) {
      return null;
    }
    const fallback = document.querySelector('[data-fallback-for="' + candidateId + '"]');
    if (!fallback) {
      return null;
    }
    const enable = fallback.querySelector('input[name="ff_enable"]');
    if (!enable || !enable.checked) {
      return null;
    }
    const minInput = fallback.querySelector('[data-bound="min"]');
    const maxInput = fallback.querySelector('[data-bound="max"]');
    const perspectiveEl = fallback.querySelector('[name="ff_perspective"]');
    const minRaw = minInput ? String(minInput.value || "").trim() : "";
    const maxRaw = maxInput ? String(maxInput.value || "").trim() : "";
    if (minRaw === "" && maxRaw === "") {
      return null;
    }
    return {
      min: minRaw === "" ? null : Number(minRaw),
      max: maxRaw === "" ? null : Number(maxRaw),
      perspective: perspectiveEl ? perspectiveEl.value : "single",
    };
  }

  function boundsAreValid() {
    if (!state || state.kind !== "numeric") {
      return false;
    }
    const min = Number(state.min);
    const max = Number(state.max);
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      return false;
    }
    return min <= max;
  }

  function draftQuery() {
    const params = new URLSearchParams(new FormData(filtersForm));
    if (!state) {
      return params;
    }
    if (state.kind === "core-list") {
      params.delete(state.param);
      params.delete(state.param.replace("filter_", ""));
      if (state.selected.length) {
        params.set(state.param, state.selected.join(","));
      }
    } else if (state.kind === "feature") {
      const key = state.featureKey;
      const enables = params.getAll("ff_enable").filter((item) => item !== key);
      const keys = params.getAll("ff_key");
      const ops = params.getAll("ff_op");
      const values = params.getAll("ff_value");
      const perspectives = params.getAll("ff_perspective");
      params.delete("ff_enable");
      params.delete("ff_key");
      params.delete("ff_op");
      params.delete("ff_value");
      params.delete("ff_perspective");
      enables.forEach((item) => params.append("ff_enable", item));
      keys.forEach((item, index) => {
        if (item === key) {
          return;
        }
        params.append("ff_key", item);
        params.append("ff_op", ops[index] || "eq");
        params.append("ff_value", values[index] || "");
        params.append("ff_perspective", perspectives[index] || "single");
      });
      if (state.control === "bool" && state.selected.length === 1) {
        params.append("ff_enable", key);
        params.append("ff_key", key);
        params.append("ff_op", "eq");
        params.append("ff_value", state.selected[0] === true || state.selected[0] === "true" ? "true" : "false");
        params.append("ff_perspective", state.perspective || "single");
      } else if (state.control === "categorical" && state.selected.length) {
        params.append("ff_enable", key);
        params.append("ff_key", key);
        params.append("ff_op", "in");
        params.append("ff_value", state.selected.map(String).join(","));
        params.append("ff_perspective", state.perspective || "single");
      }
    } else if (state.kind === "numeric" && boundsAreValid()) {
      const fields = CORE_RANGE_FIELDS[state.candidateId];
      if (fields) {
        params.set(fields.min, String(state.min));
        params.set(fields.max, String(state.max));
      } else if (state.featureKey) {
        const key = state.featureKey;
        const enables = params.getAll("ff_enable").filter((item) => item !== key);
        const keys = params.getAll("ff_key");
        const ops = params.getAll("ff_op");
        const values = params.getAll("ff_value");
        const perspectives = params.getAll("ff_perspective");
        params.delete("ff_enable");
        params.delete("ff_key");
        params.delete("ff_op");
        params.delete("ff_value");
        params.delete("ff_perspective");
        enables.forEach((item) => params.append("ff_enable", item));
        keys.forEach((item, index) => {
          if (item === key) {
            return;
          }
          params.append("ff_key", item);
          params.append("ff_op", ops[index] || "eq");
          params.append("ff_value", values[index] || "");
          params.append("ff_perspective", perspectives[index] || "single");
        });
        params.append("ff_enable", key);
        params.append("ff_key", key);
        params.append("ff_op", "gte");
        params.append("ff_value", String(state.min));
        params.append("ff_perspective", state.perspective || "single");
        params.append("ff_enable", key);
        params.append("ff_key", key);
        params.append("ff_op", "lte");
        params.append("ff_value", String(state.max));
        params.append("ff_perspective", state.perspective || "single");
      }
    }
    return params;
  }

  function refreshLive(options) {
    const immediate = options && options.immediate;
    if (!state) {
      return;
    }
    if (state.kind === "feature" && state.control === "bool" && state.selected.length !== 1) {
      abortLiveFetch();
      saveBtn.disabled = true;
      liveOk = false;
      setUpdating(false);
      statusEl.textContent = "Choose Yes or No.";
      return;
    }
    if (state.kind === "numeric" && !boundsAreValid()) {
      abortLiveFetch();
      saveBtn.disabled = true;
      liveOk = false;
      setUpdating(false);
      statusEl.textContent = "Max must be greater than or equal to min.";
      return;
    }

    abortLiveFetch();
    saveBtn.disabled = true;
    liveOk = false;
    const run = () => {
      liveTimer = null;
      if (!state) {
        return;
      }
      const generation = ++liveGeneration;
      if (liveAbort) {
        liveAbort.abort();
      }
      liveAbort = new AbortController();
      setUpdating(true);
      const url = "/api/backtest?" + draftQuery().toString();
      fetch(url, { headers: { Accept: "application/json" }, signal: liveAbort.signal })
        .then((response) => {
          if (!response.ok) {
            throw new Error("live_failed");
          }
          return response.json();
        })
        .then((summary) => {
          if (generation !== liveGeneration) {
            return;
          }
          lastSummary = summary;
          liveOk = true;
          renderChips(summary);
          setUpdating(false);
          updateSaveEnabled();
          statusEl.textContent = "";
        })
        .catch((err) => {
          if (err && err.name === "AbortError") {
            return;
          }
          if (generation !== liveGeneration) {
            return;
          }
          setUpdating(false);
          if (lastSummary) {
            renderChips(lastSummary);
          }
          liveOk = false;
          saveBtn.disabled = true;
          showLiveError();
        });
    };

    if (immediate) {
      run();
    } else {
      liveTimer = window.setTimeout(run, LIVE_DEBOUNCE_MS);
    }
  }

  function updateSaveEnabled() {
    if (!state) {
      saveBtn.disabled = true;
      return;
    }
    if (state.kind === "feature" && state.control === "bool") {
      saveBtn.disabled = !(liveOk && state.selected.length === 1);
      return;
    }
    if (state.kind === "numeric") {
      saveBtn.disabled = !(liveOk && boundsAreValid());
      return;
    }
    saveBtn.disabled = !liveOk;
  }

  function setViewToggleVisible(visible) {
    if (!viewToggle) {
      return;
    }
    viewToggle.hidden = !visible;
    if (!visible || !state) {
      return;
    }
    const isChart = state.view !== "list";
    if (viewChartBtn) {
      viewChartBtn.setAttribute("aria-pressed", isChart ? "true" : "false");
      viewChartBtn.classList.toggle("is-active", isChart);
    }
    if (viewListBtn) {
      viewListBtn.setAttribute("aria-pressed", isChart ? "false" : "true");
      viewListBtn.classList.toggle("is-active", !isChart);
    }
  }

  function setMaxRoiVisible(visible) {
    if (!maxRoiBtn) {
      return;
    }
    maxRoiBtn.hidden = !visible;
  }

  // Minimum decided bets a window must hold before it can win. Without a floor,
  // ranking by profit-per-bet always picks the smallest sample: one win at -110
  // scores 0.91, while a genuine +5% ROI over a thousand bets scores 0.05. The
  // floor is what keeps "Max ROI" from handing back a 1-bet window.
  const MAX_ROI_MIN_DECISIONS = 30;

  // Best contiguous [min,max] window by ROI, not just the single best bucket.
  // ROI isn't additive, but stake is constant across buckets, so ranking
  // windows by profit / decisions is equivalent to ranking by ROI without
  // needing to know the stake value.
  function bestRoiWindow(rows) {
    if (!rows || !rows.length) {
      return { min: null, max: null };
    }
    const sorted = rows.slice().sort((a, b) => Number(a.value) - Number(b.value));
    const totalDecisions = sorted.reduce(
      (sum, row) => sum + Number(row.wins) + Number(row.losses),
      0
    );
    // On a filter too small to ever clear the floor, fall back to the whole
    // range rather than silently returning an unqualified single bucket.
    if (totalDecisions < MAX_ROI_MIN_DECISIONS) {
      return { min: Number(sorted[0].value), max: Number(sorted[sorted.length - 1].value) };
    }
    let bestStart = 0;
    let bestEnd = sorted.length - 1;
    let bestRatio = -Infinity;
    for (let i = 0; i < sorted.length; i++) {
      let money = 0;
      let decisions = 0;
      for (let j = i; j < sorted.length; j++) {
        money += Number(sorted[j].money);
        decisions += Number(sorted[j].wins) + Number(sorted[j].losses);
        if (decisions < MAX_ROI_MIN_DECISIONS) {
          continue;
        }
        const ratio = money / decisions;
        if (ratio > bestRatio) {
          bestRatio = ratio;
          bestStart = i;
          bestEnd = j;
        }
      }
    }
    return { min: Number(sorted[bestStart].value), max: Number(sorted[bestEnd].value) };
  }

  function applyMaxRoi() {
    if (!state || !state.rows || !state.rows.length) {
      return;
    }
    if (state.kind === "numeric") {
      const window = bestRoiWindow(state.rows);
      state.min = window.min;
      state.max = window.max;
      syncBoundInputs();
      refreshLive();
    } else {
      const decided = (row) => Number(row.wins) + Number(row.losses);
      // Same sample floor as bestRoiWindow -- a lone winning bet otherwise
      // outranks every real edge in the table.
      const eligible = state.rows.filter((row) => decided(row) >= MAX_ROI_MIN_DECISIONS);
      const pool = eligible.length ? eligible : state.rows;
      let best = pool[0];
      pool.forEach((row) => {
        if (Number(row.roi) > Number(best.roi)) {
          best = row;
        }
      });
      state.selected = [best.value];
      renderValueTable();
      refreshLive();
    }
  }

  function sortedVisibleRows() {
    if (!state || !state.rows) {
      return [];
    }
    const query = (state.search || "").trim().toLowerCase();
    let rows = state.rows.slice();
    if (query) {
      rows = rows.filter((row) => String(row.description).toLowerCase().includes(query));
    }
    const key = state.sortKey || "description";
    const dir = state.sortDir === "desc" ? -1 : 1;
    rows.sort((a, b) => {
      let av = a[key];
      let bv = b[key];
      if (key === "description") {
        av = String(av).toLowerCase();
        bv = String(bv).toLowerCase();
        if (av < bv) {
          return -1 * dir;
        }
        if (av > bv) {
          return 1 * dir;
        }
        return 0;
      }
      av = Number(av);
      bv = Number(bv);
      if (av < bv) {
        return -1 * dir;
      }
      if (av > bv) {
        return 1 * dir;
      }
      return 0;
    });
    return rows;
  }

  function isSelected(value) {
    if (!state) {
      return false;
    }
    return state.selected.some((item) => String(item) === String(value));
  }

  function toggleSelected(value, checked) {
    if (!state) {
      return;
    }
    if (state.control === "bool") {
      state.selected = checked ? [value] : [];
      return;
    }
    const asString = String(value);
    if (checked) {
      if (!state.selected.some((item) => String(item) === asString)) {
        state.selected.push(value);
      }
    } else {
      state.selected = state.selected.filter((item) => String(item) !== asString);
    }
  }

  function renderPerspectiveControl(onChange) {
    if (!state || !state.teamScoped) {
      return;
    }
    const group = document.createElement("div");
    group.className = "filter-modal__perspective";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", "Perspective");
    const options = PERSPECTIVE_OPTIONS.slice();
    if (state.perspective && !options.some((opt) => opt.value === state.perspective)) {
      const label = state.perspective.charAt(0).toUpperCase() + state.perspective.slice(1);
      options.unshift({ value: state.perspective, label: label });
    }
    options.forEach((opt) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = opt.label;
      btn.setAttribute("aria-pressed", state.perspective === opt.value ? "true" : "false");
      if (state.perspective === opt.value) {
        btn.classList.add("is-active");
      }
      btn.addEventListener("click", () => {
        if (state.perspective === opt.value) {
          return;
        }
        state.perspective = opt.value;
        onChange();
      });
      group.appendChild(btn);
    });
    controlsEl.appendChild(group);
  }

  function reloadFeatureDetail() {
    if (!state || (state.kind !== "feature" && !(state.kind === "numeric" && state.featureKey))) {
      return;
    }
    statusEl.textContent = "Loading values…";
    saveBtn.disabled = true;
    liveOk = false;
    const detailParams = new URLSearchParams(new FormData(filtersForm));
    detailParams.set("candidate_id", state.candidateId);
    if (state.perspective && state.perspective !== "single") {
      detailParams.set("perspective", state.perspective);
    }
    const generation = ++detailGeneration;
    fetch("/filter-detail?" + detailParams.toString(), { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) {
          throw new Error("detail_failed");
        }
        return response.json();
      })
      .then((payload) => {
        if (!state || generation !== detailGeneration) {
          return;
        }
        if (payload.description) {
          aboutEl.textContent = payload.description;
          if (payload.lookahead_warning) {
            const warning = typeof payload.lookahead_warning === "string"
              ? payload.lookahead_warning
              : "lookahead — analysis only";
            aboutEl.textContent = payload.description + "\n\n" + warning;
          }
        }
        state.rows = payload.rows || [];
        state.chartPoints = payload.chart_points || [];
        if (payload.domain) {
          state.domainMin = payload.domain.min != null ? Number(payload.domain.min) : state.domainMin;
          state.domainMax = payload.domain.max != null ? Number(payload.domain.max) : state.domainMax;
        }
        if (payload.perspective) {
          state.perspective = payload.perspective;
        }
        if (state.kind === "numeric") {
          renderNumericControls();
        } else {
          renderValueTable();
        }
        refreshLive();
      })
      .catch(() => {
        if (!state || generation !== detailGeneration) {
          return;
        }
        statusEl.textContent = "Couldn’t load filter values.";
        saveBtn.disabled = true;
      });
  }

  function renderValueTable() {
    controlsEl.innerHTML = "";
    if (exploreEl) {
      exploreEl.innerHTML = "";
    }
    if (!state) {
      return;
    }

    renderPerspectiveControl(() => reloadFeatureDetail());

    if (!state.rows.length) {
      setMaxRoiVisible(false);
      const empty = document.createElement("p");
      empty.className = "filter-modal__hint";
      empty.textContent = "No values in range";
      controlsEl.appendChild(empty);
      const body = document.createElement("p");
      body.className = "filter-modal__hint";
      body.textContent = "No observed values remain after the rest of this system. Adjust other filters, or cancel.";
      controlsEl.appendChild(body);
      return;
    }
    setMaxRoiVisible(true);

    const search = document.createElement("input");
    search.type = "search";
    search.className = "filter-modal__search";
    search.placeholder = "Search values";
    search.value = state.search || "";
    search.setAttribute("aria-label", "Search values");
    search.addEventListener("input", () => {
      state.search = search.value;
      renderValueTable();
      const next = controlsEl.querySelector(".filter-modal__search");
      if (next) {
        next.focus();
        const end = next.value.length;
        next.setSelectionRange(end, end);
      }
    });
    controlsEl.appendChild(search);

    const wrap = document.createElement("div");
    wrap.className = "filter-modal__table-wrap";
    const table = document.createElement("table");
    table.className = "filter-modal__table";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");

    const selectTh = document.createElement("th");
    selectTh.scope = "col";
    selectTh.textContent = state.control === "bool" ? "Pick" : "Select";
    headRow.appendChild(selectTh);

    [
      { key: "description", label: "Description" },
      { key: "record", label: "Record", sortValue: "wins" },
      { key: "roi", label: "ROI" },
      { key: "money", label: "Money" },
    ].forEach((col) => {
      const th = document.createElement("th");
      th.scope = "col";
      const sortKey = col.key === "record" ? "wins" : col.key;
      if (col.key === "description" || col.key === "roi" || col.key === "money" || col.key === "record") {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "filter-modal__sort";
        btn.textContent = col.label;
        if ((state.sortKey || "description") === sortKey) {
          th.setAttribute("aria-sort", state.sortDir === "desc" ? "descending" : "ascending");
        } else {
          th.removeAttribute("aria-sort");
        }
        btn.addEventListener("click", () => {
          if ((state.sortKey || "description") === sortKey) {
            state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
          } else {
            state.sortKey = sortKey;
            state.sortDir = sortKey === "description" ? "asc" : "desc";
          }
          renderValueTable();
        });
        th.appendChild(btn);
      } else {
        th.textContent = col.label;
      }
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    const inputType = state.control === "bool" ? "radio" : "checkbox";
    sortedVisibleRows().forEach((row) => {
      const tr = document.createElement("tr");
      const pickTd = document.createElement("td");
      const input = document.createElement("input");
      input.type = inputType;
      if (inputType === "radio") {
        input.name = "filter-modal-bool";
      }
      input.checked = isSelected(row.value);
      input.addEventListener("change", () => {
        toggleSelected(row.value, input.checked);
        if (state.control === "bool") {
          renderValueTable();
        }
        refreshLive();
      });
      pickTd.appendChild(input);
      tr.appendChild(pickTd);

      const descTd = document.createElement("td");
      descTd.textContent = String(row.description);
      tr.appendChild(descTd);

      const recordTd = document.createElement("td");
      recordTd.textContent = String(row.record);
      tr.appendChild(recordTd);

      const roiTd = document.createElement("td");
      roiTd.textContent = formatRowRoi(row.roi);
      if (row.roi > 0) {
        roiTd.className = "positive";
      } else if (row.roi < 0) {
        roiTd.className = "negative";
      }
      tr.appendChild(roiTd);

      const moneyTd = document.createElement("td");
      moneyTd.textContent = formatRowMoney(row.money);
      if (row.money > 0) {
        moneyTd.className = "positive";
      } else if (row.money < 0) {
        moneyTd.className = "negative";
      }
      tr.appendChild(moneyTd);

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    controlsEl.appendChild(wrap);
  }

  function syncBoundInputs(source) {
    if (!state || state.kind !== "numeric") {
      return;
    }
    let min = Number(state.min);
    let max = Number(state.max);
    if (source === "minRange" || source === "minNumber") {
      if (Number.isFinite(min) && Number.isFinite(max) && min > max) {
        max = min;
        state.max = max;
      }
    } else if (source === "maxRange" || source === "maxNumber") {
      if (Number.isFinite(min) && Number.isFinite(max) && max < min) {
        min = max;
        state.min = min;
      }
    }
    const minRange = controlsEl.querySelector('[data-role="min-range"]');
    const maxRange = controlsEl.querySelector('[data-role="max-range"]');
    const minNumber = controlsEl.querySelector('[data-role="min-number"]');
    const maxNumber = controlsEl.querySelector('[data-role="max-number"]');
    const hint = controlsEl.querySelector('[data-role="bound-hint"]');
    if (minRange && source !== "minRange") {
      minRange.value = String(state.min);
    }
    if (maxRange && source !== "maxRange") {
      maxRange.value = String(state.max);
    }
    if (minNumber && source !== "minNumber") {
      minNumber.value = String(state.min);
    }
    if (maxNumber && source !== "maxNumber") {
      maxNumber.value = String(state.max);
    }
    const valid = boundsAreValid();
    if (hint) {
      hint.hidden = valid;
    }
    updateSelectedSpan();
    updateSaveEnabled();
  }

  function updateSelectedSpan() {
    const fill = controlsEl.querySelector(".filter-modal__dual-range-fill");
    if (!fill || !state || state.domainMin == null || state.domainMax == null) {
      return;
    }
    const span = Number(state.domainMax) - Number(state.domainMin) || 1;
    const left = ((Number(state.min) - Number(state.domainMin)) / span) * 100;
    const right = ((Number(state.max) - Number(state.domainMin)) / span) * 100;
    fill.style.left = Math.max(0, Math.min(100, left)) + "%";
    fill.style.width = Math.max(0, Math.min(100, right - left)) + "%";
  }

  function renderMoneyChart() {
    if (!exploreEl || !state) {
      return;
    }
    exploreEl.innerHTML = "";
    const points = state.chartPoints || [];
    if (!points.length) {
      const empty = document.createElement("p");
      empty.className = "filter-modal__hint";
      empty.textContent = "No values in range";
      exploreEl.appendChild(empty);
      return;
    }
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 520 150");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Money by value");
    svg.classList.add("filter-modal__chart");

    const moneys = points.map((point) => Number(point.money));
    const minMoney = Math.min(0, ...moneys);
    const maxMoney = Math.max(0, ...moneys);
    const span = maxMoney - minMoney || 1;
    const zeroY = 150 - 18 - ((0 - minMoney) / span) * (150 - 36);

    const zero = document.createElementNS("http://www.w3.org/2000/svg", "line");
    zero.setAttribute("x1", "28");
    zero.setAttribute("x2", "492");
    zero.setAttribute("y1", String(zeroY));
    zero.setAttribute("y2", String(zeroY));
    zero.setAttribute("class", "zero-line");
    svg.appendChild(zero);

    points.forEach((point) => {
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      const x = point.x != null ? point.x : 28;
      const y = point.y != null ? point.y : zeroY;
      circle.setAttribute("cx", String(x));
      circle.setAttribute("cy", String(y));
      circle.setAttribute("r", "3.5");
      circle.setAttribute("class", Number(point.money) >= 0 ? "positive" : "negative");
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = String(point.value) + ": " + formatRowMoney(point.money);
      circle.appendChild(title);
      svg.appendChild(circle);
    });
    exploreEl.appendChild(svg);
  }

  function renderNumericList() {
    if (!exploreEl || !state) {
      return;
    }
    exploreEl.innerHTML = "";
    if (!state.rows.length) {
      const empty = document.createElement("p");
      empty.className = "filter-modal__hint";
      empty.textContent = "No values in range";
      exploreEl.appendChild(empty);
      return;
    }
    const wrap = document.createElement("div");
    wrap.className = "filter-modal__table-wrap";
    const table = document.createElement("table");
    table.className = "filter-modal__table";
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Description", "Record", "ROI", "Money"].forEach((label) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = label;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    state.rows.forEach((row) => {
      const tr = document.createElement("tr");
      const cells = [
        String(row.description),
        String(row.record),
        formatRowRoi(row.roi),
        formatRowMoney(row.money),
      ];
      cells.forEach((text, index) => {
        const td = document.createElement("td");
        td.textContent = text;
        if (index === 2) {
          if (row.roi > 0) {
            td.className = "positive";
          } else if (row.roi < 0) {
            td.className = "negative";
          }
        }
        if (index === 3) {
          if (row.money > 0) {
            td.className = "positive";
          } else if (row.money < 0) {
            td.className = "negative";
          }
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    exploreEl.appendChild(wrap);
  }

  function renderNumericExplore() {
    if (!state || state.kind !== "numeric") {
      return;
    }
    if (state.view === "list") {
      renderNumericList();
    } else {
      renderMoneyChart();
    }
    setViewToggleVisible(true);
    setMaxRoiVisible(true);
  }

  function renderNumericControls() {
    controlsEl.innerHTML = "";
    if (!state || state.kind !== "numeric") {
      return;
    }

    renderPerspectiveControl(() => reloadFeatureDetail());

    if (state.domainMin == null || state.domainMax == null || !state.rows.length) {
      const empty = document.createElement("p");
      empty.className = "filter-modal__hint";
      empty.textContent = "No values in range";
      controlsEl.appendChild(empty);
      const body = document.createElement("p");
      body.className = "filter-modal__hint";
      body.textContent = "No observed values remain after the rest of this system. Adjust other filters, or cancel.";
      controlsEl.appendChild(body);
      if (exploreEl) {
        exploreEl.innerHTML = "";
      }
      setViewToggleVisible(false);
      setMaxRoiVisible(false);
      saveBtn.disabled = true;
      return;
    }

    const dual = document.createElement("div");
    dual.className = "filter-modal__dual-range";
    const track = document.createElement("div");
    track.className = "filter-modal__dual-range-track";
    const fill = document.createElement("div");
    fill.className = "filter-modal__dual-range-fill";
    track.appendChild(fill);

    const rangeStep = stepForDomain(state.domainMin, state.domainMax);

    const minRange = document.createElement("input");
    minRange.type = "range";
    minRange.className = "filter-modal__range filter-modal__range--min";
    minRange.dataset.role = "min-range";
    minRange.min = String(state.domainMin);
    minRange.max = String(state.domainMax);
    minRange.step = rangeStep;
    minRange.value = String(state.min);
    minRange.setAttribute("aria-label", "Minimum");

    const maxRange = document.createElement("input");
    maxRange.type = "range";
    maxRange.className = "filter-modal__range filter-modal__range--max";
    maxRange.dataset.role = "max-range";
    maxRange.min = String(state.domainMin);
    maxRange.max = String(state.domainMax);
    maxRange.step = rangeStep;
    maxRange.value = String(state.max);
    maxRange.setAttribute("aria-label", "Maximum");

    minRange.addEventListener("input", () => {
      state.min = Number(minRange.value);
      syncBoundInputs("minRange");
      refreshLive();
    });
    maxRange.addEventListener("input", () => {
      state.max = Number(maxRange.value);
      syncBoundInputs("maxRange");
      refreshLive();
    });

    dual.appendChild(track);
    dual.appendChild(minRange);
    dual.appendChild(maxRange);
    controlsEl.appendChild(dual);

    const between = document.createElement("div");
    between.className = "filter-modal__between";
    const betweenLabel = document.createElement("span");
    betweenLabel.textContent = "BETWEEN";
    const minNumber = document.createElement("input");
    minNumber.type = "number";
    minNumber.dataset.role = "min-number";
    minNumber.step = rangeStep;
    minNumber.value = String(state.min);
    minNumber.setAttribute("aria-label", "Minimum");
    const andLabel = document.createElement("span");
    andLabel.textContent = "AND";
    const maxNumber = document.createElement("input");
    maxNumber.type = "number";
    maxNumber.dataset.role = "max-number";
    maxNumber.step = rangeStep;
    maxNumber.value = String(state.max);
    maxNumber.setAttribute("aria-label", "Maximum");
    minNumber.addEventListener("input", () => {
      const parsed = minNumber.value.trim() === "" ? NaN : Number(minNumber.value);
      state.min = parsed;
      syncBoundInputs("minNumber");
      refreshLive();
    });
    maxNumber.addEventListener("input", () => {
      const parsed = maxNumber.value.trim() === "" ? NaN : Number(maxNumber.value);
      state.max = parsed;
      syncBoundInputs("maxNumber");
      refreshLive();
    });
    between.appendChild(betweenLabel);
    between.appendChild(minNumber);
    between.appendChild(andLabel);
    between.appendChild(maxNumber);
    controlsEl.appendChild(between);

    const hint = document.createElement("p");
    hint.className = "filter-modal__hint";
    hint.dataset.role = "bound-hint";
    hint.textContent = "Max must be greater than or equal to min.";
    hint.hidden = boundsAreValid();
    controlsEl.appendChild(hint);

    updateSelectedSpan();
    renderNumericExplore();
  }

  function writeCoreListToForm() {
    if (!state || state.kind !== "core-list") {
      return;
    }
    const select = filtersForm.querySelector('[name="' + state.param + '"]');
    if (!select) {
      return;
    }
    const joined = state.selected.slice().map(String).sort().join(",");
    let draftOpt = select.querySelector("option[data-modal-draft='1']");
    if (joined && !Array.from(select.options).some((opt) => opt.value === joined)) {
      if (!draftOpt) {
        draftOpt = document.createElement("option");
        draftOpt.dataset.modalDraft = "1";
        select.appendChild(draftOpt);
      }
      draftOpt.value = joined;
      draftOpt.textContent = joined;
    }
    select.value = joined;
  }

  function writeFeatureToForm() {
    if (!state || state.kind !== "feature") {
      return;
    }
    const fallback = document.querySelector('[data-fallback-for="feature:' + state.featureKey + '"]');
    if (!fallback) {
      return;
    }
    const enable = fallback.querySelector('input[name="ff_enable"]');
    const opEl = fallback.querySelector('[name="ff_op"]');
    const valueEl = fallback.querySelector('[name="ff_value"]');
    const perspectiveEl = fallback.querySelector('[name="ff_perspective"]');
    if (state.control === "bool") {
      if (state.selected.length !== 1) {
        return;
      }
      if (enable) {
        enable.checked = true;
      }
      if (opEl) {
        opEl.value = "eq";
      }
      if (valueEl) {
        valueEl.value = state.selected[0] === true || state.selected[0] === "true" ? "true" : "false";
      }
    } else if (state.control === "categorical") {
      if (!state.selected.length) {
        if (enable) {
          enable.checked = false;
        }
        if (valueEl) {
          valueEl.value = "";
        }
        return;
      }
      if (enable) {
        enable.checked = true;
      }
      if (opEl) {
        opEl.value = "in";
      }
      if (valueEl) {
        valueEl.value = state.selected.map(String).join(",");
      }
    }
    if (perspectiveEl && state.perspective) {
      perspectiveEl.value = state.perspective;
    }
  }

  function writeNumericToForm() {
    if (!state || state.kind !== "numeric" || !boundsAreValid()) {
      return;
    }
    const fields = CORE_RANGE_FIELDS[state.candidateId];
    if (fields) {
      const minEl = filtersForm.querySelector('[name="' + fields.min + '"]');
      const maxEl = filtersForm.querySelector('[name="' + fields.max + '"]');
      if (minEl) {
        minEl.value = (state.domainMin != null && Number(state.min) <= Number(state.domainMin)) ? "" : String(state.min);
      }
      if (maxEl) {
        maxEl.value = (state.domainMax != null && Number(state.max) >= Number(state.domainMax)) ? "" : String(state.max);
      }
      return;
    }
    const fallback = document.querySelector('[data-fallback-for="' + state.candidateId + '"]');
    if (!fallback) {
      return;
    }
    const enable = fallback.querySelector('input[name="ff_enable"]');
    if (enable) {
      enable.checked = true;
    }
    const minInput = fallback.querySelector('[data-bound="min"]');
    const maxInput = fallback.querySelector('[data-bound="max"]');
    if (minInput) {
      minInput.value = String(state.min);
    }
    if (maxInput) {
      maxInput.value = String(state.max);
    }
    fallback.querySelectorAll('[name="ff_perspective"]').forEach((el) => {
      el.value = state.perspective || "single";
    });
  }

  function cleanupAfterClose() {
    abortLiveFetch();
    liveGeneration += 1;
    detailGeneration += 1;
    liveOk = false;
    state = null;
    setViewToggleVisible(false);
    setMaxRoiVisible(false);
    if (exploreEl) {
      exploreEl.innerHTML = "";
    }
    if (statusEl) {
      statusEl.textContent = "";
    }
    if (launcher) {
      launcher.focus();
    }
  }

  function discardAndClose() {
    dialog.close();
    cleanupAfterClose();
  }

  dialog.addEventListener("close", () => {
    if (state) {
      cleanupAfterClose();
    }
  });

  function saveAndSubmit() {
    if (!liveOk || !state) {
      return;
    }
    if (state.kind === "feature" && state.control === "bool" && state.selected.length !== 1) {
      return;
    }
    if (state.kind === "numeric" && !boundsAreValid()) {
      return;
    }
    if (state.kind === "core-list") {
      writeCoreListToForm();
    } else if (state.kind === "feature") {
      writeFeatureToForm();
    } else if (state.kind === "numeric") {
      writeNumericToForm();
    }
    state = null;
    dialog.close();
    if (filtersForm.requestSubmit) {
      filtersForm.requestSubmit();
    } else {
      filtersForm.submit();
    }
  }

  function openNumericCandidate(candidateId, description, lookahead, button) {
    const committed = committedNumericBounds(candidateId);
    const teamScoped = button ? button.getAttribute("data-team-scoped") === "1" : false;
    const perspective = button
      ? resolveInitialPerspective(button, committed)
      : (committed && committed.perspective && committed.perspective !== "single"
        ? committed.perspective
        : "single");
    state = {
      kind: "numeric",
      candidateId: candidateId,
      featureKey: candidateId.indexOf("feature:") === 0 ? candidateId.split(":").slice(1).join(":") : null,
      control: "numeric",
      teamScoped: teamScoped,
      perspective: perspective,
      min: null,
      max: null,
      domainMin: null,
      domainMax: null,
      rows: [],
      chartPoints: [],
      view: "chart",
    };
    setViewToggleVisible(false);
    setMaxRoiVisible(false);
    statusEl.textContent = "Loading values…";
    const detailParams = new URLSearchParams(new FormData(filtersForm));
    detailParams.set("candidate_id", candidateId);
    if (state.perspective && state.perspective !== "single") {
      detailParams.set("perspective", state.perspective);
    }
    const generation = ++detailGeneration;
    fetch("/filter-detail?" + detailParams.toString(), { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) {
          throw new Error("detail_failed");
        }
        return response.json();
      })
      .then((payload) => {
        if (!state || generation !== detailGeneration) {
          return;
        }
        if (payload.lookahead_warning) {
          const warning = typeof payload.lookahead_warning === "string"
            ? payload.lookahead_warning
            : "lookahead — analysis only";
          aboutEl.textContent = (payload.description || description) + "\n\n" + warning;
        } else if (payload.description) {
          aboutEl.textContent = payload.description;
        } else if (lookahead) {
          aboutEl.textContent = description + (description ? "\n\n" : "") + lookahead;
        }
        state.rows = payload.rows || [];
        state.chartPoints = payload.chart_points || [];
        state.domainMin = payload.domain && payload.domain.min != null ? Number(payload.domain.min) : null;
        state.domainMax = payload.domain && payload.domain.max != null ? Number(payload.domain.max) : null;
        if (payload.perspective) {
          state.perspective = payload.perspective;
        }
        if (committed && (Number.isFinite(committed.min) || Number.isFinite(committed.max))) {
          state.min = Number.isFinite(committed.min) ? committed.min : state.domainMin;
          state.max = Number.isFinite(committed.max) ? committed.max : state.domainMax;
        } else if (state.domainMin != null && state.domainMax != null) {
          state.min = state.domainMin;
          state.max = state.domainMax;
        }
        renderNumericControls();
        const first = controlsEl.querySelector("input");
        if (first) {
          first.focus();
        }
        refreshLive();
      })
      .catch(() => {
        if (!state || generation !== detailGeneration) {
          return;
        }
        statusEl.textContent = "Couldn’t load filter values.";
        const empty = document.createElement("p");
        empty.className = "filter-modal__hint";
        empty.textContent = "No values in range";
        controlsEl.appendChild(empty);
        saveBtn.disabled = true;
      });
  }

  function openCandidate(button) {
    launcher = button;
    const candidateId = button.getAttribute("data-candidate-id") || "";
    const control = button.getAttribute("data-control") || "categorical";
    const description = button.getAttribute("data-description") || "";
    const lookahead = button.getAttribute("data-lookahead-warning") || "";
    const label = button.getAttribute("data-label") || button.textContent.trim() || "Filter";
    titleEl.textContent = label;
    aboutEl.textContent = description;
    if (lookahead) {
      aboutEl.textContent = description + (description ? "\n\n" : "") + lookahead;
    }
    abortLiveFetch();
    lastSummary = null;
    liveOk = false;
    liveGeneration += 1;
    detailGeneration += 1;
    controlsEl.innerHTML = "";
    if (exploreEl) {
      exploreEl.innerHTML = "";
    }
    if (statusEl) {
      statusEl.textContent = "";
    }
    renderChips({ wins: 0, losses: 0, pushes: 0, money_won: 0, roi: 0 });
    dialog.showModal();

    if (control === "numeric") {
      openNumericCandidate(candidateId, description, lookahead, button);
      return;
    }

    setViewToggleVisible(false);
    setMaxRoiVisible(false);
    const param = CORE_PARAM[candidateId] || button.getAttribute("data-param") || "";
    if (candidateId.indexOf("core:") === 0) {
      state = {
        kind: "core-list",
        candidateId: candidateId,
        control: "categorical",
        teamScoped: false,
        param: param,
        selected: committedCoreList(param),
        rows: [],
        search: "",
        sortKey: "description",
        sortDir: "asc",
      };
    } else {
      const featureKey = candidateId.split(":").slice(1).join(":");
      const committed = committedFeature(featureKey);
      let selected = [];
      if (control === "bool") {
        if (committed && committed.values.length === 1) {
          selected = [committed.values[0] === true || committed.values[0] === "true"];
        }
      } else if (committed) {
        selected = committed.values.slice();
      }
      const teamScoped = button.getAttribute("data-team-scoped") === "1";
      state = {
        kind: "feature",
        candidateId: candidateId,
        featureKey: featureKey,
        control: control,
        teamScoped: teamScoped,
        perspective: resolveInitialPerspective(button, committed),
        selected: selected,
        rows: [],
        search: "",
        sortKey: "description",
        sortDir: "asc",
      };
    }

    statusEl.textContent = "Loading values…";
    const detailParams = new URLSearchParams(new FormData(filtersForm));
    detailParams.set("candidate_id", candidateId);
    if (state.kind === "feature" && state.perspective && state.perspective !== "single") {
      detailParams.set("perspective", state.perspective);
    }
    const generation = ++detailGeneration;
    fetch("/filter-detail?" + detailParams.toString(), { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) {
          throw new Error("detail_failed");
        }
        return response.json();
      })
      .then((payload) => {
        if (!state || generation !== detailGeneration) {
          return;
        }
        if (payload.lookahead_warning) {
          const warning = typeof payload.lookahead_warning === "string"
            ? payload.lookahead_warning
            : "lookahead — analysis only";
          aboutEl.textContent = (payload.description || description) + "\n\n" + warning;
        } else if (payload.description) {
          aboutEl.textContent = payload.description;
        }
        state.rows = payload.rows || [];
        if (payload.perspective) {
          state.perspective = payload.perspective;
        }
        renderValueTable();
        const first = controlsEl.querySelector("input, button");
        if (first) {
          first.focus();
        }
        refreshLive();
      })
      .catch(() => {
        if (!state || generation !== detailGeneration) {
          return;
        }
        statusEl.textContent = "Couldn’t load filter values.";
        const empty = document.createElement("p");
        empty.className = "filter-modal__hint";
        empty.textContent = "No values in range";
        controlsEl.appendChild(empty);
        saveBtn.disabled = true;
      });
  }

  document.querySelectorAll("[data-candidate-id]").forEach((button) => {
    button.addEventListener("click", () => openCandidate(button));
  });

  const modalForm = document.getElementById("filter-modal-form");
  if (modalForm) {
    modalForm.addEventListener("submit", (event) => {
      event.preventDefault();
    });
  }

  cancelBtn.addEventListener("click", discardAndClose);
  closeBtn.addEventListener("click", discardAndClose);
  saveBtn.addEventListener("click", saveAndSubmit);
  if (maxRoiBtn) {
    maxRoiBtn.addEventListener("click", applyMaxRoi);
  }

  if (viewChartBtn) {
    viewChartBtn.addEventListener("click", () => {
      if (!state || state.kind !== "numeric") {
        return;
      }
      state.view = "chart";
      renderNumericExplore();
    });
  }
  if (viewListBtn) {
    viewListBtn.addEventListener("click", () => {
      if (!state || state.kind !== "numeric") {
        return;
      }
      state.view = "list";
      renderNumericExplore();
    });
  }

  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    discardAndClose();
  });

  dialog.addEventListener("click", (event) => {
    // Backdrop clicks neither commit nor discard (D-21).
    if (event.target === dialog) {
      event.preventDefault();
      event.stopPropagation();
    }
  });
})();
