(function () {
  "use strict";
  var form = document.getElementById("filters-form");
  if (!form) return;
  document.documentElement.classList.add("editor-js");
  var panel = document.getElementById("system-filters");
  var toggle = document.querySelector(".filter-panel-toggle");
  var narrow = window.matchMedia("(max-width: 900px)");
  function setOpen(open) {
    document.documentElement.classList.toggle("filters-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.textContent = open ? "Hide filters" : "Show filters";
    panel.inert = narrow.matches && !open;
  }
  toggle.addEventListener("click", function () { setOpen(toggle.getAttribute("aria-expanded") !== "true"); });
  narrow.addEventListener("change", function () { setOpen(false); });
  setOpen(false);
  document.querySelectorAll(".stat-row__side").forEach(function (button) {
    button.setAttribute("aria-label", button.dataset.label || button.closest(".stat-row").querySelector(".stat-row__label").textContent + ": " + button.textContent);
  });
  var status = document.querySelector(".system-run-status");
  var run = document.getElementById("run-system");
  document.addEventListener("change", function (event) {
    if (event.target.form !== form || !event.target.name || ["theory", "save_name"].includes(event.target.name)) return;
    if (status) status.textContent = "Filters changed. Run system to update results.";
    run.textContent = "Run system";
    var summaryRun = document.querySelector(".system-summary-heading button");
    if (summaryRun) summaryRun.textContent = "Run system";
  });
  document.addEventListener("keydown", function (event) {
    if (document.querySelector("dialog[open]")) return;
    if (event.key === "Escape" && narrow.matches) { setOpen(false); toggle.focus(); }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); form.requestSubmit(run); }
    if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "f") {
      var search = document.querySelector(".filter-search");
      if (search) { event.preventDefault(); setOpen(true); search.focus(); }
    }
  });
  run.title = "Ctrl+Enter to run. Ctrl+Shift+F to search filters.";
})();
