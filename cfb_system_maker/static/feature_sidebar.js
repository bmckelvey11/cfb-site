// Feature Filters sidebar: live substring search + per-group collapse.
// Kept separate from filter_modal.js so the two can be changed independently.
(function () {
  "use strict";

  var section = document.querySelector(".feature-filters");
  if (!section) {
    return;
  }

  var search = section.querySelector(".filter-search");
  var fieldsets = Array.prototype.slice.call(section.querySelectorAll(".feature-group"));
  if (!fieldsets.length) {
    return;
  }

  // Own progressive-enhancement flag rather than reusing the "js" class that
  // filter_modal.js sets, so neither script depends on the other having loaded.
  document.documentElement.classList.add("feature-sidebar-js");

  // A team-scoped stat keeps its name in .stat-row__label and its buttons read
  // only "Bet-side"/"Opponent", so matching button text alone would miss every
  // stat name and match every row on "opponent".
  function rowText(row) {
    var parts = row.querySelectorAll(".stat-row__label, .filter-launcher");
    var text = "";
    for (var i = 0; i < parts.length; i += 1) {
      text += " " + parts[i].textContent;
    }
    return text.toLowerCase();
  }

  var groups = fieldsets.map(function (fieldset) {
    var rows = Array.prototype.slice.call(fieldset.querySelectorAll(".filter-launch-row"));
    return {
      fieldset: fieldset,
      rows: rows,
      // Match against the launcher labels within the row, so a row holding more
      // than one button still matches on either label.
      texts: rows.map(rowText),
    };
  });

  function apply() {
    var term = search ? search.value.trim().toLowerCase() : "";
    // While a term is active the collapse rule goes inert (see styles.css), so
    // a collapsed group still reveals its matches: search overrides collapse.
    section.classList.toggle("is-searching", term !== "");

    groups.forEach(function (group) {
      var matched = 0;
      group.rows.forEach(function (row, index) {
        var hit = term === "" || group.texts[index].indexOf(term) !== -1;
        if (hit) {
          matched += 1;
        }
        // Hide with display only -- never `disabled`. Disabled inputs are
        // dropped from FormData, so searching would silently drop filters the
        // user already committed; display:none inputs still serialize.
        row.style.display = hit ? "" : "none";
      });
      // A group with no matches disappears entirely, legend included, so the
      // user does not scroll past a stack of empty legends.
      group.fieldset.style.display = term !== "" && matched === 0 ? "none" : "";
    });
  }

  groups.forEach(function (group) {
    var legend = group.fieldset.querySelector("legend");
    if (!legend) {
      return;
    }
    // Read the label before appending anything, or it picks up the badge count
    // and the toggle glyph.
    var label = legend.textContent.trim();

    // Counts the same data-has-filter chips the rows already render as solid
    // pills, so the badge and the pills can never disagree. A team-scoped stat
    // with both sides set counts 2, matching what the eye sees.
    // Counted once, at load. Saving in the modal calls requestSubmit() on the
    // filters form, which is a full page reload -- there is no live state to
    // observe, so no MutationObserver.
    var active = group.fieldset.querySelectorAll('[data-has-filter="1"]').length;
    if (active > 0) {
      var badge = document.createElement("span");
      badge.className = "feature-group__badge";
      badge.textContent = String(active);
      badge.setAttribute("aria-label", active + " active");
      legend.appendChild(badge);
    }

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "feature-group__toggle";
    // Groups start expanded: search, not collapse, is what solves "scroll to
    // find Wind Speed", and collapsing by default would hide the whole sidebar.
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Collapse " + label);
    toggle.textContent = "−";
    toggle.addEventListener("click", function () {
      var collapsed = group.fieldset.classList.toggle("is-collapsed");
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      toggle.setAttribute("aria-label", (collapsed ? "Expand " : "Collapse ") + label);
      toggle.textContent = collapsed ? "+" : "−";
    });
    legend.appendChild(toggle);
  });

  if (search) {
    search.addEventListener("input", apply);
    search.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        // The input sits inside filters-form; Enter would submit the backtest.
        event.preventDefault();
      }
    });
    apply();
  }
})();
