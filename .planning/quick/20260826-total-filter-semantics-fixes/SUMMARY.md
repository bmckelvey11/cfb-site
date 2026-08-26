---
task: total-filter-semantics-fixes
date: 2026-08-26
status: complete
---

# Summary: Filter audit fixes (findings 1-6 + 5 smaller UX gaps)

Nine commits on `fix/web-app-review-2026-08-26`, 438 tests green.

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

## Smaller UX gaps (non-money-impacting)

1. **3ea1408** — no-JS numeric feature filter perspective sync: the max-row
   perspective was a hidden input frozen at page-render time while the min
   row was live-editable, so a no-JS submit could grade gte and lte against
   different teams. Max row now mirrors the same select.
2. **7a7babe** (bundled with 4-5, see below) — dead perspective buttons: the
   modal's Bet-side/Opponent/Either row was static regardless of what the
   server would accept; now filtered against `allowed_perspectives`, which
   the payload already carried but JS never read.
3. **No new code** — one-sided committed bounds getting silently re-closed at
   the current domain max on re-save was resolved as a byproduct of finding
   3's edge-clearing fix (`atDomainMax`/`atDomainMin` in `writeNumericToForm`
   already handle this case; covered by the existing contract test).
4. **7a7babe** — silent parse failures on the no-JS `/system` page: a typo'd
   `min_spread`/`filter_seasons` value was dropped with the active-filters
   list as the only tell. New `_has_unparseable_input` flags the same input
   shapes the strict API validator 400s on (deliberately not unified with
   it — different failure mode) and surfaces a banner; loading a saved
   system is unaffected since it parses trusted JSON, not query args.
5. **7a7babe** — Max ROI double-counted overlapping rows: either-perspective
   rows (and a total system's team/conference rows from finding 1) can put
   one game's outcome in two buckets. Corrected finding 5's original wording
   here — the *same*-bucket case (home==away value) was already deduped
   correctly by the aggregator; the actual bug is a summed window across
   *different* buckets double-counting a game that appears in both. Server
   now flags `overlapping_rows`; Max ROI falls back to the single best
   bucket (never double-counted) and discloses why in the About panel.
   Committed backtest results were never affected — this is a suggestion-only
   bug, `matches_system` always selects each game exactly once.

Encountered a stale-read error mid-edit on `web.py` where a docstring tweak
failed silently after a concurrent-session commit (`e910e99`,
`fix(web): allow either perspective on spread systems too`) landed on the
shared branch — re-read and reapplied cleanly; verified compatible with my
`overlapping_rows` logic (mechanism applies regardless of bet_type). All
gaps 1/2/4/5 browser-verified live (DOM/state inspection via javascript_tool,
Browser pane can't screenshot in this session's headless mode).
