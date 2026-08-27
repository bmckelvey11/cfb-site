---
phase: 08-neutral-site-indoor-unders-example
plan: 01
subsystem: data
tags: [betting-systems, examples, storage, backtest]

# Dependency graph
requires:
  - phase: 05
    provides: bundled example systems (list_examples()/load_example_system() generic loader), 3 existing examples
provides:
  - "A 4th bundled example system (neutral-site-indoor-unders) on the Example Systems tab"
  - "A verified-against-real-data theory field, not an unverified restatement of the source doc"
  - "A narrowed D-21 weather-filter guard with one documented, scoped exception"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Example JSON added as pure data -- zero code changes to storage.py/web.py, matches Phase 5's generic directory-scan loader design"

key-files:
  created:
    - cfb_system_maker/examples/neutral-site-indoor-unders.json
  modified:
    - tests/test_storage.py

key-decisions:
  - "Measured backtest numbers for the exact 3-filter set (69-40-1, 63.30% under, +20.66% ROI, n=109, p~0.011) matched the source doc's 2-filter cell (69-40, 63.30%, +20.85% ROI, n=109, p=0.014) almost exactly -- in this dataset every indoor game is also played in a dome, so venue_dome adds no additional narrowing beyond neutralSite+gameIndoors. Cited the app's own measured ROI/p-value in the theory text (not the doc's) since a user backtesting this exact system in the app would see the app's numbers, per the must_haves truth requiring numbers 'actually observed.'"
  - "Narrowed (not deleted) the D-21 no-weather-filter guard: added a scoped WEATHER_FILTER_EXCEPTIONS set for exactly (neutral-site-indoor-unders, gameIndoors), documented with a comment citing DATA-01 and 08-CONTEXT.md's Zero-Match Live Weeks decision. Every other example and every other weather key on this example remain blocked."

requirements-completed: [DATA-01]

coverage:
  - id: D1
    description: "4th example system (neutral-site-indoor-unders) appears in list_examples() and on the Example Systems tab with exactly 3 boolean eq/single filters (neutralSite, gameIndoors, venue_dome), bet_type=total, total_side=under"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/test_storage.py::test_neutral_site_indoor_unders_pins_its_exact_filter_set"
        status: pass
      - kind: unit
        ref: "tests/test_storage.py::test_list_examples_returns_the_bundled_names"
        status: pass
      - kind: e2e
        ref: "manual curl verification: GET /?tab=examples renders neutral-site-indoor-unders row with record 69-40-1, 63.3%, ROI 20.66%"
        status: pass
    human_judgment: false
  - id: D2
    description: "Theory field states real, verified sample size/significance for the exact filter set shipped, with honesty caveats (small sample, Bonferroni, era/week stability)"
    requirement: "DATA-01"
    verification:
      - kind: other
        ref: "one-off backtest script against data/games.csv + data/features.json via cfb_system_maker.backtest.run_backtest -- record/rate/ROI/p-value and era/week breakdowns all independently verified against bet_details, recorded in this SUMMARY's Accomplishments section"
        status: pass
    human_judgment: true
    rationale: "Whether the prose is 'honest' (accurately represents caveats, doesn't overstate) and grammatically sound is a qualitative judgment about wording, not something a unit test can assert."
  - id: D3
    description: "Copy to My Systems works for the new example the same way it does for the existing three"
    requirement: "DATA-01"
    verification:
      - kind: e2e
        ref: "manual curl verification: POST /copy-example name=neutral-site-indoor-unders returns 302, GET / shows the system on My Systems tab"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-21 weather-filter guard still blocks every other weather-group feature on every other example, with the gameIndoors exception narrowly scoped"
    requirement: "DATA-01"
    verification:
      - kind: unit
        ref: "tests/test_storage.py::test_no_example_filters_on_provider_weather_or_season_to_date"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-08-27
status: complete
---

# Phase 8 Plan 1: Neutral-Site & Indoor Unders Example Summary

**Bundled a 4th example system (neutral-site+indoor+dome unders) whose theory text cites the app's own measured backtest (69-40-1, 63.30% under rate, +20.66% ROI, n=109, p~0.011) rather than restating the source doc's unverified figures for a different filter combination.**

## Performance

- **Duration:** 45 min
- **Started:** 2026-08-27T00:00:00Z
- **Completed:** 2026-08-27T00:45:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `cfb_system_maker/examples/neutral-site-indoor-unders.json`: a totals/unders system filtering on `neutralSite=true`, `gameIndoors=true`, `venue_dome=true` (all `op: eq`, `perspective: single`), matching the shape of the 3 existing bundled examples.
- Ran the exact 3-filter system against real production data (`data/games.csv` + `data/features.json`) via `cfb_system_maker.backtest.run_backtest` directly (CLI has no `--feature-filter` flag). Measured result: **69 wins - 40 losses - 1 push (n=109 decided, 110 total), 63.30% under rate, +20.66% ROI, p-value approx 0.0112**. Season breakdown confirmed the doc's era split exactly: 2013-2019 = 31-22 (58.49%, n=53) vs 2020-2025 = 38-18 (67.86%, n=56); positive-ROI in 9 of 12 seasons.
- Confirmed the measured population is identical to `docs/under-team-stats-analysis.md`'s 2-condition (neutral+indoor) cell: in this dataset, every indoor game is also played in a dome, so adding `venue_dome` to the filter set narrows nothing further. The theory text cites the app's own measured ROI (+20.66%) and p-value (~0.011) rather than the doc's figures (+20.85%/p=0.014) for the record/rate/n that are numerically identical, since the plan's honesty requirement is "actually observed" numbers from backtesting the exact filter set shipped.
- Wrote the final `theory` field: prose hypothesis style matching the 3 existing examples, stating the record/rate/ROI/n, the era and week-of-season stability, and the small-sample/Bonferroni-does-not-survive caveat from the source doc's own "best available lead, not a proven edge" framing. Both the era split and the week-of-season split were independently verified against this plan's own `bet_details` (not carried from the doc on the assumption of an identical population): bucketing the 109 decided bets by week gives wk1 19-11 (63.33%, n=30), wk2-13 21-12 (63.64%, n=33), wk14+ 29-17 (63.04%, n=46) -- all matching the doc's wk1/wk2-13/wk14+ figures (63.3%/63.6%/63.0%) to the tenth, and the win/loss totals (19+21+29=69, 11+12+17=40) reconcile with the overall 69-40 record.
- Narrowed (not deleted) the pre-existing D-21 "no example filters on weather" guard in `tests/test_storage.py`: added a `WEATHER_FILTER_EXCEPTIONS = {("neutral-site-indoor-unders", "gameIndoors")}` set with a comment citing DATA-01 and 08-CONTEXT.md's Zero-Match Live Weeks decision, and updated the guard's loop to skip only that exact `(name, key)` pair. Every other example and every other weather key on this example remain blocked unchanged.
- Updated `EXPECTED_EXAMPLE_NAMES` to `["neutral-site-indoor-unders", "nonconference-away-dogs", "spread-home-favorites", "total-unders-high-lines"]` (sorted order — "ne" sorts before "no").
- Added `test_neutral_site_indoor_unders_pins_its_exact_filter_set`, a targeted assertion pinning the new example's exact filter set (3 `eq`/`single`/`True` filters on `neutralSite`, `gameIndoors`, `venue_dome`; `bet_type == "total"`; `total_side == "under"`), since the existing generic loops don't check this specific requirement.
- Verified end-to-end in the running web UI (`python -m cfb_system_maker web --data-dir data`): the 4th example renders on the Example Systems tab (first row, alphabetically) with record `69-40-1, 63.3%`, ROI `20.66%`, full theory text with no truncation or escaping issues, and a working Copy to My Systems button. Confirmed `POST /copy-example` with `name=neutral-site-indoor-unders` returns a 302 redirect and the copy appears on the My Systems tab as an ordinary saved system.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create the example JSON, narrow the D-21 weather guard, and backtest it against real data** - `a6dc49b` (feat)
2. **Task 2: Write the honest theory prose against observed numbers and verify the UI end-to-end** - `b026205` (feat)
3. **Post-review copy fix: correct a grammatically broken sentence in the theory prose, drop the venue_dome-no-op implementation detail from user-facing text, and tighten the guard's `continue` to only skip the weather assertion (not season-to-date) for the excepted pair** - `30e81a6` (fix)

_Note: full test suite (457 tests) run and passing after each task and after the post-review fix._

## Files Created/Modified

- `cfb_system_maker/examples/neutral-site-indoor-unders.json` - New bundled example: totals/unders system on `neutralSite`+`gameIndoors`+`venue_dome`, with theory text citing the app's own measured backtest numbers
- `tests/test_storage.py` - Added `WEATHER_FILTER_EXCEPTIONS`, narrowed the D-21 guard loop, updated `EXPECTED_EXAMPLE_NAMES`, renamed `test_list_examples_returns_the_three_bundled_names` -> `test_list_examples_returns_the_bundled_names`, added `test_neutral_site_indoor_unders_pins_its_exact_filter_set`

## Decisions Made

- **Cite measured numbers, not the doc's, where they diverge.** The doc reports +20.85% ROI / p=0.014 for its 2-condition cell; the app's own backtest of the exact 3-condition system shipped measures +20.66% ROI / p~0.0112 for the identical 69-40/n=109 record. Since a user who copies this example and looks at the app's own stats panel sees the app's numbers, the theory text cites those, not the doc's, to avoid a visible self-contradiction between the theory prose and the product's own output.
- **`venue_dome` is a no-op filter in this dataset**, not an additional narrowing of the doc's 2-condition finding — confirmed by the identical 69-40/n=109 record between the doc's neutral+indoor cell and this plan's neutral+indoor+dome system. The theory text describes the three filters as jointly defining the spot rather than claiming `venue_dome` narrows the doc's population further.
- **Narrowed, not deleted, the D-21 guard** — the guard's purpose (prevent a provider/weather/season-to-date filter that would silently zero out live-week matches for the *typical* example) still holds for every other example; this one example's zero-match weeks are an explicit, accepted, documented tradeoff (08-CONTEXT.md), not a general relaxation of the rule.

## Deviations from Plan

None - plan executed exactly as written. The "if observed numbers diverge, cite observed figures" branch of Task 2's decision rule applied for ROI/p-value specifically (record/rate/n were identical to the doc), which the plan anticipated as a possible outcome.

## Issues Encountered

- `data/` is gitignored and not present in this git worktree (worktrees don't inherit untracked/gitignored files from the main checkout). The one-off backtest script and the live web-UI verification both had to point `--data-dir`/module calls at the main checkout's `C:\Users\mckel\dev\cfb-site\data` directory rather than a worktree-local path. No code or test changes were needed for this — `load_processed_games`/`load_features` and the CLI's `--data-dir` flag already parameterize the data directory; this was purely an execution-environment note, not a deviation.
- The live-verification `POST /copy-example` call created `data/systems/neutral-site-indoor-unders.json` in the main checkout as a side effect of testing. Removed it after verification so the main checkout's `data/systems/` directory wasn't left with a stray file from this test run.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DATA-01 is closed: 4 example systems now ship, each honestly disclosing its statistical basis.
- No blockers. The D-21 guard's documented exception pattern (`WEATHER_FILTER_EXCEPTIONS`) is reusable if a future example needs a similar narrow, justified carve-out.

---
*Phase: 08-neutral-site-indoor-unders-example*
*Completed: 2026-08-27*

## Self-Check: PASSED

- FOUND: cfb_system_maker/examples/neutral-site-indoor-unders.json
- FOUND: .planning/phases/08-neutral-site-indoor-unders-example/08-01-SUMMARY.md
- FOUND commit: a6dc49b
- FOUND commit: b026205
