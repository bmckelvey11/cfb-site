---
phase: 04-filter-popup-modal
plan: 01
subsystem: ui
tags: [flask, jinja, dialog, backtest, filter-modal, vanilla-js]

requires:
  - phase: 03-data-depth-breadth
    provides: Feature registry groups and entering-game running features
  - phase: 02-integrity-fade-grade
    provides: Fade grading and main-page chip conventions
provides:
  - FeatureDef.description on every registry feature
  - run_backtest_summary lightweight Record/Money/ROI seam
  - GET /api/backtest with strict allowlist parse
  - Season vertical-slice native dialog (draft/commit)
affects:
  - 04-02 filter-detail distribution
  - 04-03 numeric/categorical modal controls
  - 04-04 debounce and Edit launchers

tech-stack:
  added: []
  patterns:
    - Lightweight summary helper skips stats/grade/permutation
    - StrictParseError + parse_system_strict for JSON APIs
    - Progressive enhancement via html.js + filter-fallback/launcher

key-files:
  created:
    - tests/test_filter_modal.py
    - cfb_system_maker/static/filter_modal.js
  modified:
    - cfb_system_maker/features.py
    - cfb_system_maker/backtest.py
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/index.html
    - cfb_system_maker/static/styles.css
    - tests/test_features.py

key-decisions:
  - "Season draft uses checkboxes; Save writes comma-joined filter_seasons into the canonical select"
  - "Backdrop light-dismiss blocked via cancel.preventDefault; Escape handled as Cancel"
  - "Live chips render server JSON only via GET /api/backtest"

patterns-established:
  - "CORE_FILTER_META + filter_descriptor for core:* and feature:* About copy"
  - "One reusable dialog#filter-modal shell for all future filter types"
  - "run_backtest_summary for modal/live chips; run_backtest unchanged for main page"

requirements-completed: [MODAL-01, MODAL-02, MODAL-05, MODAL-06]

duration: 7min
completed: 2026-07-17
status: complete
---

# Phase 4 Plan 01: Season Modal Vertical Slice Summary

**Season filter opens in a native dialog with live server Record/Money/ROI chips, About text from CORE_FILTER_META, and Save/Cancel draft commit over filters-form GET.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-17T18:21:49Z
- **Completed:** 2026-07-17T18:28:45Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added non-empty plain-text `FeatureDef.description` on every registry feature (lookahead rows mark analysis-only).
- Introduced `run_backtest_summary` for chip fields only, preserving Fade/push/ROI parity with `grade_bet`.
- Shipped `GET /api/backtest` with strict unknown-key/perspective/non-finite rejection (400) and missing-data 503.
- Season launcher + dialog shell: live chips, About Filter via `textContent`, Save commits seasons, Cancel/Escape/✕ discard without form mutation; backdrop does not close.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 tests, descriptions, and lightweight summary seam** - `3d17904` (feat)
2. **Task 2: /api/backtest + Season dialog Save/Cancel slice** - `c48d70e` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `tests/test_filter_modal.py` - Wave 0 unit/integration contracts for summary, API, markup, Save/Cancel
- `cfb_system_maker/features.py` - trailing `description` field + registry copy
- `cfb_system_maker/backtest.py` - `run_backtest_summary`
- `tests/test_features.py` - nonempty description assertion
- `cfb_system_maker/web.py` - `CORE_FILTER_META`, `filter_descriptor`, `parse_system_strict`, `/api/backtest`
- `cfb_system_maker/templates/index.html` - Season launcher, dialog shell, script include
- `cfb_system_maker/static/filter_modal.js` - Season draft/commit state machine
- `cfb_system_maker/static/styles.css` - modal + progressive-enhancement rules

## Decisions Made

- Season multi-select draft serializes to comma-joined `filter_seasons` (existing `_int_set` parser).
- Native `<dialog>` cancel event is prevented so backdrop clicks never dismiss; Escape explicitly discards.
- Debounce/AbortController deferred to plan 04-04; this slice uses immediate fetch (plan-allowed).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 04-02 (`/filter-detail` + per-value aggregation). Season proves draft/commit + live chips; remaining filters reuse the same dialog and API.

## Self-Check: PASSED

- FOUND: `tests/test_filter_modal.py`
- FOUND: `cfb_system_maker/static/filter_modal.js`
- FOUND: commit `3d17904`
- FOUND: commit `c48d70e`
- FOUND: `run_backtest_summary` importable; `/api/backtest` covered by pytest

---
*Phase: 04-filter-popup-modal*
*Completed: 2026-07-17*
