---
phase: 06-merge-stale-stats-audit
fixed_at: 2026-08-27T01:20:48Z
review_path: .planning/phases/06-merge-stale-stats-audit/06-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-08-27T01:20:48Z
**Source review:** .planning/phases/06-merge-stale-stats-audit/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (Critical: 0, Warning: 2 — IN-01 explicitly excluded per instructions, it's a repo-convention suggestion, not a bug)
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Max ROI on a single-value domain (or an overlapping-rows bucket pick) silently disables the filter instead of committing it

**Files modified:** `cfb_system_maker/static/filter_modal.js`
**Commit:** 040191b
**Status:** fixed: requires human verification (logic/state-interaction fix — no JS test runner in this repo to exercise it; verified by syntax check + manual code trace of the four scenarios listed below)

**Applied fix:** Added `state.singleValuePick`, set to `true` in `applyMaxRoi()` whenever `bestSingleNumericBucket` was used (i.e. `state.overlappingRows` was true at Max-ROI time). Both `draftQuery()` (live preview) and `writeNumericToForm()` (Save) now bypass the "min/max at domain edge means no filter" clearing logic whenever `singleValuePick` is true, writing both bounds unconditionally so a Max ROI single-value pick commits `== X` instead of silently unchecking `ff_enable` or dropping one bound into an unbounded `>= X`/`<= X`. The flag is cleared (restoring normal edge-clearing behavior) whenever the user manually drags/types a bound (`syncBoundInputs(source)` with a truthy `source`) or the modal reloads fresh rows/domain (`reloadFeatureDetail`).

Traced scenarios against the final code:
- Either-perspective Max ROI landing on `domainMax` → both bounds written, `ff_enable` stays checked, live preview matches Save.
- Same pick landing on only one edge → committed as `== X` (both gte and lte set), not `>= X` unbounded.
- Max ROI then manually dragging both sliders to the domain extremes → original domain-edge clearing behavior is restored (flag cleared by the drag handler).

### WR-02: Overlapping-rows disclosure only appears on initial modal open, not when perspective is switched to "either" mid-session

**Files modified:** `cfb_system_maker/static/filter_modal.js`
**Commit:** aedba7c
**Status:** fixed: requires human verification (logic/UI-state fix — no JS test runner in this repo to exercise it; verified by syntax check + manual code trace of the three scenarios listed below)

**Applied fix:** Factored the overlap disclosure ("Either-perspective values can overlap per game, so Max ROI picks the single best value here instead of a range.") into a shared `applyOverlapNote(baseText)` helper that *rebuilds* `aboutEl.textContent` from a base description/lookahead text plus the note (keyed off `state.overlappingRows`), rather than appending. Both `openNumericCandidate`'s and `reloadFeatureDetail`'s success handlers now call this helper after setting `state.overlappingRows`, so switching perspective to "Either" mid-session (which only `reloadFeatureDetail` handles) now shows the note too. The helper is scoped to `state.kind === "numeric"` since value-table (categorical) filters already show one value per row and don't need the disclosure.

Traced scenarios against the final code:
- Switching to "Either" mid-modal → note appears.
- Switching back to a non-either perspective → note disappears (rebuilt from base text, not left appended).
- Switching to "Either" twice in a row → note appears once, not duplicated.

## Skipped Issues

None — both in-scope findings were fixed.

---

_Fixed: 2026-08-27T01:20:48Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
