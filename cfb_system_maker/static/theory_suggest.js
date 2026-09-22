(function () {
  "use strict";

  const trigger = document.getElementById("theory-suggest");
  const textarea = document.getElementById("theory-input");
  const statusEl = document.getElementById("theory-status");
  const form = document.getElementById("filters-form");
  if (!trigger || !textarea || !statusEl || !form) {
    return;
  }

  const MESSAGES = {
    rate_limited: "Just a moment -- try again in half a minute.",
    theory_unavailable: "AI drafting is unavailable. Check ANTHROPIC_API_KEY.",
    missing_data: "No processed games found; run a build first.",
  };

  trigger.addEventListener("click", function () {
    // The filters live in the editor form, so the draft follows unsaved edits rather
    // than whatever was last saved.
    const body = new URLSearchParams(new FormData(form));
    // Never send the existing prose back: this drafts from the filters, and the reply
    // overwrites the box.
    body.delete("theory");

    trigger.disabled = true;
    statusEl.classList.remove("error");
    statusEl.textContent = "Drafting...";

    fetch("/theory/suggest", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
      body: body,
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) {
            throw new Error(data.error || "theory_unavailable");
          }
          return data;
        });
      })
      .then(function (data) {
        textarea.value = data.text.trim();
        statusEl.textContent = "Draft written -- edit it to say what you actually think.";
        trigger.disabled = false;
      })
      .catch(function (error) {
        statusEl.classList.add("error");
        statusEl.textContent = MESSAGES[error.message] || "Could not draft a theory right now.";
        trigger.disabled = false;
      });
  });
})();
