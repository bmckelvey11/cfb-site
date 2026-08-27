---
phase: 06-merge-stale-stats-audit
reviewed: 2026-08-26T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - cfb_system_maker/static/filter_modal.js
  - tests/test_storage.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-08-26
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Scope note: `git diff 1e9190d..2e86ba5 -- <file>` is byte-identical to `git diff 1e9190d..f0d799f/7a7babe -- <file>` for both files, confirming the merge took the incoming branch's content wholesale for these two files — consistent with the "empty HEAD side, populated incoming side" resolution the phase summary describes. Only `tests/test_storage.py` was a genuinely isolated, additive conflict (one new test, `test_load_normalizes_bet_side_perspective_on_total_systems`); I traced it against `storage.load_system` → `_system_from_dict` → `features.effective_perspective` and confirmed the assertions match the implementation exactly. That file is clean.

`filter_modal.js` is where the risk lives. The conflict itself was narrow (the `allowedPerspectives`/`overlappingRows` block: `renderPerspectiveControl` filtering by `state.allowedPerspectives`, and `applyMaxRoi` branching to `bestSingleNumericBucket` when `state.overlappingRows` is true), but "take incoming wholesale" also pulled in the rest of that branch's `filter_modal.js` changes (domain-edge bound clearing in `draftQuery`/`writeNumericToForm`, the SVG axis chart) as one unit. A wholesale resolution can't catch an interaction bug between two pieces of the same incoming branch, and there is one: `bestSingleNumericBucket` (new, in the conflict region) always returns `min === max`, and the domain-edge-clearing logic (adjacent, pre-existing on the incoming branch) silently drops the filter entirely whenever both bounds sit at the domain edge. Also worth noting: this repo has no JS test runner, so nothing about "441 tests passing" post-merge is evidence this file's conflict resolution is behaviorally correct — it was merged unverified by any automated check.

One item I chased that turned out *not* to be a bug: `draftQuery`'s numeric-feature branch collapsed two `ff_enable` appends into one guarded append (line ~382). Server-side, `enabled = set(values.getlist("ff_enable"))` (`web.py:1094`, `web.py:1217`) is a set-membership check, not a positional zip against `ff_key`/`ff_op`/`ff_value` — so a single `ff_enable` append is sufficient to keep both the `gte` and `lte` rows for that key active. No divergence between live preview and Save.

## Warnings

### WR-01: Max ROI on a single-value domain (or an overlapping-rows bucket pick) silently disables the filter instead of committing it

**File:** `cfb_system_maker/static/filter_modal.js:1355-1396` (also mirrored for core-range fields at `1355-1369`), interacting with `cfb_system_maker/static/filter_modal.js:574-586` (`bestSingleNumericBucket`, part of this merge's conflict-resolved block)

**Issue:** `boundsAreValid()` (line 292-302) allows `min === max`. `writeNumericToForm()` computes `atDomainMin`/`atDomainMax` independently (lines 1379-1380) and, when both are true, sets `enable.checked = false` (line 1383) — i.e. treats "selection spans the full observed domain" as "no filter, clear it." That's correct when the user drags both sliders out to their extremes on a genuinely continuous domain (the documented intent per the comment at 1375-1378). But it's wrong whenever `min === max` lands exactly on a domain edge, which now happens by construction any time `overlappingRows` is true and the user clicks Max ROI: `bestSingleNumericBucket` (added by this merge's conflict resolution) always returns `{min: best.value, max: best.value}` for a single bucket. If that bucket happens to be the highest (or lowest, or the only) observed value, `writeNumericToForm` unchecks `ff_enable` on Save and the filter the user just selected via "Max ROI" silently vanishes — Save commits "no filter" instead of "== X". The same collapse applies to the `CORE_RANGE_FIELDS` path (spread/total range) whenever the domain has exactly one distinct observed value.

There's a related, softer version even without hitting the exact edge: if `bestSingleNumericBucket`'s pick sits at only *one* edge (e.g. `min === max === domainMax` but `domainMin` is different), `atDomainMax` is true and `atDomainMin` is false, so `writeNumericToForm` clears the upper bound and commits only `min = X` (i.e. `>= X`, unbounded above) instead of `== X`. On the dataset that produced the current rows this happens to select the same games (`domainMax` is `max()` of the currently observed rows), so there's no visible discrepancy today — but the persisted `SavedSystem` JSON records an unbounded `>= X` filter, not the single value the modal displayed. Re-run against a later `data/processed/games.csv` with new values above `X` and the saved system silently widens.

**Fix:** Distinguish "user dragged to the domain edge" from "min/max coincide at a specific selected value" instead of inferring intent purely from bound-vs-domain equality. One option: track whether the current bounds came from the raw slider defaults (full domain on open) vs. an explicit selection (Max ROI, manual drag that happens to land on an edge), and only apply the "clear at domain edge" behavior in the former case. At minimum, `bestSingleNumericBucket`'s single-bucket selection should bypass the domain-edge-clearing path entirely (e.g. write both bounds unconditionally when `state.overlappingRows` was true at Max-ROI time), since it is explicitly choosing one value, not spanning a range.

### WR-02: Overlapping-rows disclosure only appears on initial modal open, not when perspective is switched to "either" mid-session

**File:** `cfb_system_maker/static/filter_modal.js:720-780` (`reloadFeatureDetail`, part of the conflict-resolved region) vs. `1493-1521` (`openNumericCandidate`'s `.then` handler)

**Issue:** `openNumericCandidate` appends an explicit note to `aboutEl` when `payload.overlapping_rows` is true: *"Either-perspective values can overlap per game, so Max ROI picks the single best value here instead of a range."* (lines 1517-1521). `reloadFeatureDetail` — the handler invoked when the user clicks a perspective button inside an already-open modal (wired via `renderPerspectiveControl(() => reloadFeatureDetail())`, line 791/1170) — sets `state.overlappingRows = Boolean(payload.overlapping_rows)` (line 765) from the exact same server field, but never appends the note; it only conditionally reassigns `aboutEl.textContent` from `payload.description` (lines 744-751) with no overlap-specific text. Since the server sets `overlapping_rows = true` precisely when `perspective == "either"` (`web.py:766-768`), the one user action that turns overlap semantics *on* for a numeric filter — switching to "Either" via the in-modal perspective toggle — is the one path that gives zero indication Max ROI has silently switched from a windowed-sum algorithm to a single-bucket pick.

**Fix:** Factor the overlap-note append into a shared helper called from both `openNumericCandidate`'s success handler and `reloadFeatureDetail`'s success handler, keyed off `state.overlappingRows` after it's set, rather than duplicating (and now diverging) the disclosure logic between the two fetch call sites.

## Info

### IN-01: No automated verification for this file's conflict resolution

**File:** `cfb_system_maker/static/filter_modal.js` (repo-wide: no JS test runner configured)

**Issue:** The phase summary's Self-Check cites "441 tests passing" pre- and post-merge as verification for the merge. That number is exclusively `pytest` (Python). There is no JS test harness in this repo (`package.json`/`jest`/etc. not present), so the `filter_modal.js` conflict resolution — including the two warnings above — was never exercised by any automated check; it's manually-reasoned-correct only.

**Fix:** Not blocking for this merge, but worth flagging in project conventions: either add light JS unit tests for the pure functions in this file (`bestRoiWindow`, `bestSingleNumericBucket`, `boundsAreValid`, `writeNumericToForm`'s bound-clearing logic) or explicitly document that `filter_modal.js` correctness relies on manual QA, so future merges don't over-trust a green Python suite as coverage for this file.

---

_Reviewed: 2026-08-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
