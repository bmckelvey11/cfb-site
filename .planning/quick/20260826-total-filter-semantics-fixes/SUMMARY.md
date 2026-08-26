---
task: total-filter-semantics-fixes
date: 2026-08-26
status: complete
---

# Summary: Filter audit fixes (findings 1-6)

Six commits on `fix/web-app-review-2026-08-26`, 433 tests green.

## Findings 1-3 (money-impact)

1. **d9c93e4** — `matches_system` team/conference filters on total systems now
   match either side of the game (spread systems unchanged: bet-side only).
2. **5040b31** — bet_side/opponent perspectives on totals: strict API parsing
   rejects them; form/storage collapse them to "either" via
   `features.effective_perspective`.
3. **249b541** — modal Save clears numeric feature bounds at observed domain
   edges (mirrors core ranges); `draftQuery` matches so preview == commit.
   Browser-verified against real data.

## Findings 4-6 (description/grade/stats accuracy)

4. **01673f7** — Spread Range description corrected: bounds apply to the side
   being bet (home spread negated for away), not always the raw home spread.
5-6. **a8673be** — Two independent fixes bundled in one commit because both
   touch `backtest.py` and were staged before either was committed (noted in
   the commit message):
   - Home/Away checkboxes carried zero selection information beyond `side`
     (search.py already knew this, per its own comment) but still depressed
     `count_overfit_filters` / the letter grade. Excluded from the count;
     checkboxes removed from the form. Legacy saved systems with the flags
     already set are unaffected (fields/matching/removal/describe() untouched)
     — no bet-selection or ROI change for existing systems.
   - `roi_t_stat`'s standard error was decided-only while `roi` is
     pushes-included (pushes contribute 0 profit but count in the ROI
     denominator) — mismatched estimators, understating the t-stat whenever
     pushes exist. `returns` now includes pushes. Deliberately left
     `_permutation_p_value`, `cluster_dependence_stats`, `_hit_rate_z_test`
     untouched — each is decided-only throughout and internally coherent.

An advisor consult during finding 5 caught a wrong first attempt (redefining
Home/Away to filter by physical home/away status) that would have silently
changed bet selection and ROI on already-saved systems — reverted before
commit in favor of the result-preserving fix actually shipped.

Also committed separately first: 3a6e247 (pre-existing uncommitted chart-axis
work in filter_modal.js).
