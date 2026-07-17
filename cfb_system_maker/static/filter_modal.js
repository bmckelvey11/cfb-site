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
  const emptyEl = document.getElementById("filter-modal-empty");
  const statusEl = document.getElementById("filter-modal-status");
  const recordEl = document.getElementById("filter-modal-record");
  const moneyEl = document.getElementById("filter-modal-money");
  const roiEl = document.getElementById("filter-modal-roi");
  const saveBtn = document.getElementById("filter-modal-save");
  const cancelBtn = document.getElementById("filter-modal-cancel");
  const closeBtn = document.getElementById("filter-modal-close");

  const CORE_PARAM = {
    "core:season": "filter_seasons",
    "core:week": "filter_weeks",
    "core:team": "filter_teams",
    "core:conference": "filter_conferences",
    "core:provider": "filter_providers",
  };

  let launcher = null;
  let state = null;
  let lastSummary = null;
  let liveOk = false;

  document.documentElement.classList.add("js");

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
    statusEl.textContent = updating ? "Updating…" : "";
    recordEl.style.opacity = updating ? "0.55" : "1";
    moneyEl.style.opacity = updating ? "0.55" : "1";
    roiEl.style.opacity = updating ? "0.55" : "1";
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
    }
    return params;
  }

  function refreshLive() {
    if (!state) {
      return;
    }
    if (state.kind === "feature" && state.control === "bool" && state.selected.length !== 1) {
      saveBtn.disabled = true;
      liveOk = false;
      setUpdating(false);
      statusEl.textContent = "Choose Yes or No.";
      return;
    }
    setUpdating(true);
    saveBtn.disabled = true;
    liveOk = false;
    const url = "/api/backtest?" + draftQuery().toString();
    fetch(url, { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) {
          throw new Error("live_failed");
        }
        return response.json();
      })
      .then((summary) => {
        lastSummary = summary;
        liveOk = true;
        renderChips(summary);
        setUpdating(false);
        updateSaveEnabled();
        statusEl.textContent = "";
      })
      .catch(() => {
        setUpdating(false);
        if (lastSummary) {
          renderChips(lastSummary);
        }
        statusEl.textContent = "Couldn’t update live stats.";
        saveBtn.disabled = true;
      });
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
      saveBtn.disabled = !liveOk;
      return;
    }
    saveBtn.disabled = !liveOk;
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

  function renderValueTable() {
    controlsEl.innerHTML = "";
    if (!state) {
      return;
    }

    if (!state.rows.length) {
      const empty = document.createElement("p");
      empty.className = "filter-modal__hint";
      empty.textContent = "No values in range";
      controlsEl.appendChild(empty);
      return;
    }

    const search = document.createElement("input");
    search.type = "search";
    search.className = "filter-modal__search";
    search.placeholder = "Search values";
    search.value = state.search || "";
    search.setAttribute("aria-label", "Search values");
    search.addEventListener("input", () => {
      state.search = search.value;
      renderValueTable();
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

  function renderNumericPlaceholder() {
    controlsEl.innerHTML = "";
    const hint = document.createElement("p");
    hint.className = "filter-modal__hint";
    hint.textContent = "Numeric range controls open here. Save keeps the current committed range.";
    controlsEl.appendChild(hint);
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

  function discardAndClose() {
    state = null;
    dialog.close();
    if (launcher) {
      launcher.focus();
    }
  }

  function saveAndSubmit() {
    if (!liveOk || !state) {
      return;
    }
    if (state.kind === "feature" && state.control === "bool" && state.selected.length !== 1) {
      return;
    }
    if (state.kind === "core-list") {
      writeCoreListToForm();
    } else if (state.kind === "feature") {
      writeFeatureToForm();
    }
    dialog.close();
    if (filtersForm.requestSubmit) {
      filtersForm.requestSubmit();
    } else {
      filtersForm.submit();
    }
  }

  function openCandidate(button) {
    launcher = button;
    const candidateId = button.getAttribute("data-candidate-id") || "";
    const control = button.getAttribute("data-control") || "categorical";
    const description = button.getAttribute("data-description") || "";
    const lookahead = button.getAttribute("data-lookahead-warning") || "";
    titleEl.textContent = button.textContent.trim() || "Filter";
    aboutEl.textContent = description;
    if (lookahead) {
      aboutEl.textContent = description + (description ? "\n\n" : "") + lookahead;
    }
    lastSummary = null;
    liveOk = false;
    controlsEl.innerHTML = "";
    renderChips({ wins: 0, losses: 0, pushes: 0, money_won: 0, roi: 0 });
    dialog.showModal();

    if (control === "numeric") {
      state = { kind: "numeric", candidateId: candidateId, control: control };
      renderNumericPlaceholder();
      refreshLive();
      saveBtn.focus();
      return;
    }

    const param = CORE_PARAM[candidateId] || button.getAttribute("data-param") || "";
    if (candidateId.indexOf("core:") === 0) {
      state = {
        kind: "core-list",
        candidateId: candidateId,
        control: "categorical",
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
      state = {
        kind: "feature",
        candidateId: candidateId,
        featureKey: featureKey,
        control: control,
        perspective: committed ? committed.perspective : "single",
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
    fetch("/filter-detail?" + detailParams.toString(), { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) {
          throw new Error("detail_failed");
        }
        return response.json();
      })
      .then((payload) => {
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

  cancelBtn.addEventListener("click", discardAndClose);
  closeBtn.addEventListener("click", discardAndClose);
  saveBtn.addEventListener("click", saveAndSubmit);

  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
  });

  dialog.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      discardAndClose();
    }
  });

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      event.stopPropagation();
    }
  });
})();
