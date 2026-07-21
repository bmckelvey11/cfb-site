---
phase: 04-filter-popup-modal
plan: 03
subsystem: ui
tags: [flask, jinja, dialog, numeric-range, dual-range, chart, describe, vanilla-js]

requires:
  - phase: 04-filter-popup-modal
    provides: /filter-detail aggregation, launchers, categorical/boolean modal table
provides:
  - describe() gte+lte coalesce into one BETWEEN sentence
  - chart_points downsample (cap 60) on numeric /filter-detail
  - Dual-range + BETWEEN UI with Chart/List SVG money chart
  - Numeric Save writes paired FeatureFilter gte+lte or canonical min/max
affects:
  - 04-04 debounce, Retry, and Edit launchers from active-filter sentences

tech-stack:
  added: []
  patterns:
    - Paired FeatureFilter gte+lte as one logical numeric range (D-07)
    - Visual-only chart_points downsample; domain min/max stay exact
    - Dual native range inputs synced with BETWEEN/AND number fields

key-files:
  created: []
  modified:
    - cfb_system_maker/describe.py
    - cfb_system_maker/web.py
    - cfb_system_maker/static/filter_modal.js
    - cfb_system_maker/templates/index.html
    - cfb_system_maker/static/styles.css
    - tests/test_describe.py
    - tests/test_filter_modal.py

key-decisions:
  - "chart_points capped at 60 with stride downsample; always retain last extreme"
  - "Numeric feature fallback renders paired gte+lte slots for progressive-enhancement GET round-trip"
  - "serialize_numeric_draft rejects non-finite and reversed bounds server-side (T-04-10)"

patterns-established:
  - "describe groups feature_filters by (key, perspective) before emitting sentences"
  - "writeNumericToForm commits core min/max or data-bound min/max then filters-form.submit"
  - "Chart/List toggle changes exploration view only — never bounds or live metric authority"

requirements-completed: [MODAL-03, MODAL-06]

duration: 7min
completed: 2026-07-17
status: complete
---

# Phase 4 Plan 03: Numeric Dual-Range + Chart/List Summary

**Numeric filters explore with synchronized dual handles and BETWEEN inputs, a capped SVG money chart with Chart/List toggle, coalesced BETWEEN sentences, and Save that writes paired gte+lte or canonical min/max into filters-form GET.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-17T18:54:11Z
- **Completed:** 2026-07-17T19:00:52Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Coalesced same-key numeric `gte`+`lte` FeatureFilters into one BETWEEN/exact/at-least/at-most sentence with a single `ff:{key}` edit identity.
- Extended `/filter-detail` with exact numeric rows, domain min/max, and deterministic `chart_points` (cap 60); spread uses `_side_spread`, total uses `GameRecord.total`.
- Built dual-range + BETWEEN UI, Chart/List SVG money chart, invalid-bound Save lockout, and numeric Save→form→GET commit (Cancel unchanged).

## Task Commits

Each task was committed atomically:

1. **Task 1: Paired numeric filters, describe coalesce, numeric detail/chart payload** - `7af7e52` (test RED) + `9bd09e7` (feat GREEN)
2. **Task 2: Dual-range UI, Chart/List toggle, SVG money chart** - `5a2d374` (feat)

**Plan metadata:** `75e109f` (docs: complete plan)

## Files Created/Modified

- `cfb_system_maker/describe.py` - Group-by (key, perspective); numeric coalesce via `_labeled_range_sentence`
- `cfb_system_maker/web.py` - `downsample_chart_points`, `serialize_numeric_draft`, numeric `chart_points` on `/filter-detail`
- `cfb_system_maker/static/filter_modal.js` - Dual-range sync, chart/list explore, `writeNumericToForm`
- `cfb_system_maker/templates/index.html` - Chart/List toggle; numeric feature paired gte+lte fallback slots
- `cfb_system_maker/static/styles.css` - Dual-range track/thumb, chart, view-toggle styles
- `tests/test_describe.py` - Coalesce + exact perspective BETWEEN cases
- `tests/test_filter_modal.py` - chart_points, serialize, UI/Save contracts

## Decisions Made

- Chart downsample uses `_range_chart`-style stride with last-extreme retention so domain extremes stay plottable.
- Numeric registry fallbacks expose two `ff_*` slots (`gte`/`lte`) so progressive-enhancement GET can round-trip paired bounds.
- Server `serialize_numeric_draft` is the canonical validation shape mirrored by client Save writers.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## TDD Gate Compliance

- RED: `7af7e52` — failing coalesce/chart/serialize tests
- GREEN: `9bd09e7` — server contracts implemented

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Numeric MODAL-03 path complete; 04-04 can wire Edit launchers, debounce/AbortController, and Retry without changing Save serialization.
- Live header already substitutes draft range into `/api/backtest`; debounce is still fire-on-every-input (expected until 04-04).

## Self-Check: PASSED

- Files: describe.py, web.py, filter_modal.js, index.html, styles.css, test_describe.py, test_filter_modal.py, 04-03-SUMMARY.md — all present
- Commits: `7af7e52`, `9bd09e7`, `5a2d374` — all present
- Verification: `python -m pytest tests/test_filter_modal.py tests/test_describe.py tests/test_web.py -x` → 84 passed

---
*Phase: 04-filter-popup-modal*
*Completed: 2026-07-17*
