---
phase: 01-system-editor-main-page
reviewed: 2026-07-17T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - cfb_system_maker/backtest.py
  - cfb_system_maker/describe.py
  - cfb_system_maker/models.py
  - cfb_system_maker/static/styles.css
  - cfb_system_maker/storage.py
  - cfb_system_maker/templates/index.html
  - cfb_system_maker/web.py
  - tests/test_backtest.py
  - tests/test_describe.py
  - tests/test_storage_systems.py
  - tests/test_web.py
  - tests/test_web_features.py
findings:
  critical: 1
  warning: 6
  info: 3
  total: 10
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-07-17T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the system-editor main page rework: stat-chip header restyle, margin computation, `describe()` plain-English filter sentences, remove-link query-string materialization, the cumulative-money-won chart, and the new `theory` field round-trip through storage/web/template. The full existing test suite for these files passes (75 tests, verified locally).

The most serious finding is a genuine crash: any query-string value for `bet_type`, `side`, or `total_side` outside the small allowed set (e.g. `?bet_type=nonsense`) reaches an unguarded `raise ValueError` inside `matches_system` and returns an unhandled HTTP 500 — reproduced directly against `create_app()`. The rest of the findings are in the newly added "remove filter" affordance (`_query_href_removing`/`_REMOVE_PARAM_MAP`), which has several edge cases where the visible "×" button silently does nothing or removes the wrong filter, and in the loaded-system→form round-trip, which silently collapses multi-value season/week/team/conference/provider restrictions back to "All ...". None of these are caught by the current test suite because the tests only exercise well-formed, single-value query strings.

## Critical Issues

### CR-01: Unvalidated `bet_type`/`side`/`total_side` query params crash the index route (HTTP 500)

**File:** `cfb_system_maker/web.py:80` (calls into `cfb_system_maker/backtest.py:112-117`)
**Issue:** `_system_from_form` builds a `SystemFilter` straight from `request.args.get("bet_type", ...)` / `.get("side", ...)` / `.get("total_side", ...)` with no validation (`web.py:465-467`). `matches_system` only validates these values *after* being called from `run_backtest`, and does so by raising a bare `ValueError` (`backtest.py:112-117`) instead of returning `False` or being validated earlier. Since `index()` (`web.py:80`) calls `run_backtest` with no try/except, any request like `GET /?bet_type=nonsense`, `GET /?side=diagonal`, or `GET /?bet_type=total&total_side=sideways` produces an unhandled exception and a 500 response instead of a graceful "invalid filter" state. Reproduced directly:
```
GET /?bet_type=nonsense       -> 500 (ValueError: bet_type must be 'spread' or 'total')
GET /?side=diagonal           -> 500 (ValueError: system side must be 'home' or 'away')
GET /?bet_type=total&total_side=sideways -> 500 (ValueError: total_side must be 'over' or 'under')
```
This is trivially reachable by anyone editing the URL bar or a bookmarked/shared link with a stale query string — no authentication or special tooling required.
**Fix:** Validate `bet_type`/`side`/`total_side` in `web.py` before calling `run_backtest` (clamp to the allowed set or render the existing `error=` state), and/or make `matches_system` fail closed (return `False`) for unknown values instead of raising:
```python
# web.py, in _system_from_form or index()
bet_type = str(form["bet_type"])
if bet_type not in {"spread", "total"}:
    bet_type = "spread"
side = str(form["side"])
if side not in {"home", "away"}:
    side = "home"
total_side = str(form["total_side"])
if total_side not in {"over", "under"}:
    total_side = "over"
```

## Warnings

### WR-01: "Remove filter" link is a no-op for legacy `season`/`week`/`team`/`conference`/`provider` query params

**File:** `cfb_system_maker/web.py:23-35` (`_REMOVE_PARAM_MAP`), `cfb_system_maker/web.py:330-334` (`_form_values` legacy fallback)
**Issue:** `_form_values()` still reads `season`/`week`/`team`/`conference`/`provider` as a fallback when `filter_seasons`/etc. aren't present, so a URL like `/?season=2023` is accepted and rendered as an active "the season is 2023" sentence. But `_REMOVE_PARAM_MAP["seasons"]` only pops `filter_seasons` — never the legacy `season` key — so clicking the "×" on that sentence produces an href identical to the current URL. Reproduced: `GET /?season=2023` renders a remove link with `href="?season=2023"` (the filter is never actually removed). Same issue applies to `week`/`team`/`conference`/`provider`.
**Fix:** Either drop the legacy fallback from `_form_values()` (since no current form field emits it) or have `_REMOVE_PARAM_MAP` pop both param names:
```python
"seasons": ("filter_seasons", "season"),
"weeks": ("filter_weeks", "week"),
"teams": ("filter_teams", "team"),
"conferences": ("filter_conferences", "conference"),
"providers": ("filter_providers", "provider"),
```

### WR-02: Removing one feature-filter sentence can silently delete a second, unrelated filter that shares the same key

**File:** `cfb_system_maker/web.py:271-282` (`_query_href_removing`), `cfb_system_maker/describe.py:70-96`
**Issue:** `describe()` keys every feature-filter sentence purely by `f"ff:{filt.key}"`, and `_query_href_removing` removes *every* `ff_key`/`ff_op`/`ff_value`/`ff_perspective` entry matching that key. If two `FeatureFilter`s share the same `key` with different `op`s (e.g. `weather_temperature gte 40` and `weather_temperature lte 90`, reachable via a crafted `ff_key`/`ff_op` query string), `describe()` renders two separate sentences/remove-links, but clicking either "×" removes **both** filters. Reproduced: with `ff_key=weather_temperature&ff_key=weather_temperature&ff_op=gte&ff_op=lte&ff_value=40&ff_value=90`, both rendered remove hrefs are identical (`?side=home`), i.e. both filters vanish no matter which "×" is clicked.
**Fix:** Give each active filter a unique identity in `describe()` (e.g. include an index or `op` in the sentence key, `f"ff:{filt.key}:{index}"`) and have `_query_href_removing` remove only the matching index rather than every entry with the same key.

### WR-03: No validation that `min <= max` for spread/total range filters

**File:** `cfb_system_maker/describe.py:22-33`, `cfb_system_maker/web.py:493-494` (`_optional_float`), `cfb_system_maker/templates/index.html:95-104`
**Issue:** Nothing prevents a user from typing a larger value into "min" than "max" (or vice versa via a crafted URL). `_range_sentence` happily renders a nonsensical "the spread is between 10 and -5" sentence, and `matches_system` silently returns zero matches (both bounds can never be satisfied simultaneously) with no indication to the user that the filter itself is malformed rather than the data being empty. Reproduced: `describe(SystemFilter(min_spread=10, max_spread=-5))` → `"the spread is between 10 and -5"`.
**Fix:** Swap or reject out-of-order bounds before constructing the `SystemFilter` (e.g. in `_system_from_form`), or have `_range_sentence` normalize `minimum, maximum = min(minimum, maximum), max(minimum, maximum)` before formatting.

### WR-04: Loading a saved system with a multi-value season/week/team/conference/provider filter silently collapses it to "All ..." on re-submit

**File:** `cfb_system_maker/web.py:381-410` (`_form_from_system`)
**Issue:** `SystemFilter.seasons` (and `weeks`/`teams`/`conferences`/`providers`) is a `set` that can legitimately hold more than one value (e.g. a system saved with `filter_seasons=2021,2022` via a crafted query string, which `_int_set` happily parses). But `_form_from_system` only round-trips a single value back into the dropdown-backed form field: `next(iter(system.seasons), "") if len(system.seasons) == 1 else ""`. For any saved system with >1 season/week/team/etc., the season dropdown silently shows "All Seasons" even though the loaded system is actually restricted — and if the user then clicks "Run System" or "Save System" again without touching that field, `_system_from_form` re-derives `seasons` from the now-blank form value, permanently dropping the multi-value restriction from the saved/re-run system. This is a real data-loss risk on the load→edit→save round-trip this phase introduces (`load_saved_system`/`_form_from_system`/`save_system`).
**Fix:** Either support multi-select for these fields in the form, or render (and preserve) the full set as a comma-separated value in the corresponding text/select rather than collapsing to `""` whenever `len(...) != 1`.

### WR-05: `describe()` silently drops the sentence (and the remove control) for out-of-vocabulary op/control combinations

**File:** `cfb_system_maker/describe.py:83-96`
**Issue:** Only four `(op, control)` combinations are handled (`eq`+bool, `eq`+categorical, `in`+categorical, `gte`/`lte`+numeric). Any other combination (e.g. `op="eq"` on a `numeric`-control feature, reachable via a crafted `ff_op` query param since the template never emits it) leaves `text = None`, so no sentence — and therefore no remove link — is ever rendered for that filter, even though `feature_ok`/`matches_system` still apply it when grading bets. The filter becomes invisible and un-removable through the UI.
**Fix:** Add a fallback sentence for unrecognized combinations (mirroring the existing "Unknown filter" branch), e.g.:
```python
if text is None:
    text = f"{label} {filt.op} {filt.value}"
```

### WR-06: Dead `pageshow` script references a `[data-initial]` hook that no longer exists anywhere in the template

**File:** `cfb_system_maker/templates/index.html:373-379`
**Issue:**
```html
<script>
  window.addEventListener("pageshow", () => {
    document.querySelectorAll("[data-initial]").forEach((input) => {
      input.value = input.dataset.initial || "";
      input.addEventListener("focus", () => input.removeAttribute("readonly"), { once: true });
    });
  });
</script>
```
No element in the template has a `data-initial` attribute or a `readonly` attribute, so this handler is permanently a no-op. It reads as vestigial back/forward-cache handling from an earlier iteration of the form and should either be removed or the feature it was meant to support should be wired up.
**Fix:** Delete the block if the bfcache-restore behavior it was meant to guard against is no longer needed, or restore the `data-initial`/`readonly` markup on the relevant inputs if it's still needed.

## Info

### IN-01: `.theory-field.full-width` class has no effect (dead CSS scoping)

**File:** `cfb_system_maker/templates/index.html:185`, `cfb_system_maker/static/styles.css:146-148`
**Issue:** `<label class="theory-field full-width">` relies on `.full-width { grid-column: 1 / -1; }`, but that rule is scoped to `.field-grid .full-width` (`styles.css:146-148`), and `.theory-field` is a direct child of `.filters` (a single-column grid), not `.field-grid`. The `full-width` class currently does nothing.
**Fix:** Either drop the unused `full-width` class from the theory label, or add a standalone `.full-width { grid-column: 1 / -1; }` rule if `.theory-field` is ever nested inside a multi-column container.

### IN-02: Non-finite filter bounds render verbatim into user-facing sentences

**File:** `cfb_system_maker/describe.py:15-19`
**Issue:** `_fmt_num`/`_range_sentence` don't guard against `nan`/`inf` (only avoid crashing, per the existing test). A filter constructed with `min_spread=float("nan")` renders as `"the spread is at least nan"` in the active-filters panel, which is confusing copy for an end user even though it doesn't crash.
**Fix:** Consider filtering non-finite bounds out before calling `describe()`, or rendering a clearer message (e.g. "invalid value") for non-finite bounds.

### IN-03: "Money Won" chip can show "-$0" for a tiny negative profit

**File:** `cfb_system_maker/templates/index.html:230`
**Issue:** `"{:,.0f}".format(-result.profit * 100)` rounds to the nearest whole dollar after the sign branch has already been chosen by `result.profit < 0`, so a very small negative profit (e.g. `-0.0009`) renders as `-$0` — a negative sign on a zero-looking amount.
**Fix:** Suppress the sign when the rounded display value is `0` (cosmetic only; low priority).

---

_Reviewed: 2026-07-17T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
