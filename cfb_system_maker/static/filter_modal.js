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
  const seasonSelect = document.getElementById("filter-seasons");

  let launcher = null;
  let draftSeasons = [];
  let lastSummary = null;
  let liveOk = false;

  document.documentElement.classList.add("js");

  function seasonOptions() {
    if (!seasonSelect) {
      return [];
    }
    return Array.from(seasonSelect.options)
      .map((opt) => opt.value)
      .filter((value) => value !== "");
  }

  function committedSeasons() {
    if (!seasonSelect) {
      return [];
    }
    const value = seasonSelect.value.trim();
    if (!value) {
      return [];
    }
    return value.split(",").map((part) => part.trim()).filter(Boolean);
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

  function draftQuery() {
    const params = new URLSearchParams(new FormData(filtersForm));
    params.delete("filter_seasons");
    params.delete("season");
    if (draftSeasons.length) {
      params.set("filter_seasons", draftSeasons.join(","));
    }
    return params;
  }

  function setUpdating(updating) {
    statusEl.textContent = updating ? "Updating…" : "";
    recordEl.style.opacity = updating ? "0.55" : "1";
    moneyEl.style.opacity = updating ? "0.55" : "1";
    roiEl.style.opacity = updating ? "0.55" : "1";
  }

  function refreshLive() {
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
        saveBtn.disabled = false;
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

  function renderSeasonControls() {
    controlsEl.innerHTML = "";
    const list = document.createElement("div");
    list.className = "filter-modal__season-list";
    const allLabel = document.createElement("label");
    allLabel.className = "check";
    const allBox = document.createElement("input");
    allBox.type = "checkbox";
    allBox.checked = draftSeasons.length === 0;
    allBox.addEventListener("change", () => {
      if (allBox.checked) {
        draftSeasons = [];
        renderSeasonControls();
        refreshLive();
      }
    });
    allLabel.appendChild(allBox);
    allLabel.appendChild(document.createTextNode(" All Seasons"));
    list.appendChild(allLabel);

    seasonOptions().forEach((season) => {
      const label = document.createElement("label");
      label.className = "check";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = season;
      box.checked = draftSeasons.includes(season);
      box.addEventListener("change", () => {
        if (box.checked) {
          if (!draftSeasons.includes(season)) {
            draftSeasons.push(season);
          }
        } else {
          draftSeasons = draftSeasons.filter((value) => value !== season);
        }
        renderSeasonControls();
        refreshLive();
      });
      label.appendChild(box);
      label.appendChild(document.createTextNode(" " + season));
      list.appendChild(label);
    });
    controlsEl.appendChild(list);
  }

  function openSeason(button) {
    launcher = button;
    titleEl.textContent = button.textContent.trim() || "Season";
    aboutEl.textContent = button.getAttribute("data-description") || "";
    draftSeasons = committedSeasons().slice();
    lastSummary = null;
    liveOk = false;
    renderSeasonControls();
    renderChips({ wins: 0, losses: 0, pushes: 0, money_won: 0, roi: 0 });
    dialog.showModal();
    const first = controlsEl.querySelector("input");
    if (first) {
      first.focus();
    }
    refreshLive();
  }

  function discardAndClose() {
    draftSeasons = [];
    dialog.close();
    if (launcher) {
      launcher.focus();
    }
  }

  function writeSeasonsToForm() {
    if (!seasonSelect) {
      return;
    }
    const joined = draftSeasons.slice().sort().join(",");
    let draftOpt = seasonSelect.querySelector("option[data-modal-draft='1']");
    if (joined && !Array.from(seasonSelect.options).some((opt) => opt.value === joined)) {
      if (!draftOpt) {
        draftOpt = document.createElement("option");
        draftOpt.dataset.modalDraft = "1";
        seasonSelect.appendChild(draftOpt);
      }
      draftOpt.value = joined;
      draftOpt.textContent = joined;
    }
    seasonSelect.value = joined;
  }

  function saveAndSubmit() {
    if (!liveOk) {
      return;
    }
    writeSeasonsToForm();
    dialog.close();
    filtersForm.requestSubmit ? filtersForm.requestSubmit() : filtersForm.submit();
  }

  document.querySelectorAll('[data-candidate-id="core:season"]').forEach((button) => {
    button.addEventListener("click", () => openSeason(button));
  });

  cancelBtn.addEventListener("click", discardAndClose);
  closeBtn.addEventListener("click", discardAndClose);
  saveBtn.addEventListener("click", saveAndSubmit);

  // Block native light-dismiss (backdrop). Escape is handled below as Cancel.
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
