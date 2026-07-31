(function () {
  "use strict";

  const panel = document.getElementById("narration-panel");
  const trigger = document.getElementById("narrate-trigger");
  const statusEl = document.getElementById("narration-status");
  const textEl = document.getElementById("narration-text");
  if (!panel || !trigger || !statusEl || !textEl) {
    return;
  }

  const runName = panel.getAttribute("data-run-name");
  let requested = false;

  trigger.addEventListener("click", function () {
    if (requested) {
      return;
    }
    requested = true;
    trigger.disabled = true;
    statusEl.classList.remove("error");
    statusEl.textContent = "Narrating...";

    fetch("/search-runs/" + encodeURIComponent(runName) + "/narrate", {
      method: "POST",
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) {
            throw new Error(data.error || "narration_failed");
          }
          return data;
        });
      })
      .then(function (data) {
        statusEl.textContent = "";
        textEl.textContent = data.text;
      })
      .catch(function () {
        statusEl.classList.add("error");
        statusEl.textContent = "Narration unavailable right now.";
        trigger.disabled = false;
        requested = false;
      });
  });
})();
