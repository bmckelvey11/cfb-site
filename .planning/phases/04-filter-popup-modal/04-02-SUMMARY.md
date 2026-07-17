---
phase: 04-filter-popup-modal
plan: 02
subsystem: ui
tags: [flask, jinja, dialog, filter-detail, categorical, boolean, vanilla-js]

requires:
  - phase: 04-filter-popup-modal
    provides: Season modal shell, /api/backtest, CORE_FILTER_META, FeatureDef.description
provides:
  - GET /filter-detail one-pass per-value aggregation
  - remove_candidate_filters + aggregate_filter_value_rows
  - Grouped D-01 launchers for core + registry filters
  - Categorical/boolean searchable sortable value table with Save→GET commit
affects:
  - 04-03 numeric dual-handle/chart modal controls
  - 04-04 debounce and Edit launchers

tech-stack:
  added: []
  patterns:
    - One-pass match→resolve→grade→bucket for /filter-detail
    - Progressive enhancement launchers with filter-fallback canonical controls
    - Draft table selection commits via ff_*/core list write then filters-form.submit

key-files:
  created: []
  modified:
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/index.html
    - cfb_system_maker/static/filter_modal.js
    - cfb_system_maker/static/styles.css
    - tests/test_filter_modal.py

key-decisions:
  - "Boolean domain always emits Yes/No rows even when a side has zero observed games"
  - "Numeric launchers open About + live chips; range editors deferred to 04-03"
  - "Feature Save updates existing per-feature fallback controls (not rebuilt parallel arrays from scratch)"

patterns-established:
  - "remove_candidate_filters clears both range bounds / all same-key FeatureFilters before distribution"
  - "Value table built with DOM APIs + textContent; search/sort client-side with aria-sort"
  - "Cancel/Escape never call write*ToForm; Save always requestSubmit/submit after atomic write"

requirements-completed: [MODAL-01, MODAL-04, MODAL-05, MODAL-06]

duration: 18min
completed: 2026-07-17
status: complete
---

# Phase 4 Plan 02: Filter Detail + Categorical/Boolean Table Summary

**All D-01 filters launch the shared modal; categorical/boolean candidates load one-pass `/filter-detail` value tables with search/sort/select, and Save commits through `filters-form` GET.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-17T18:35:44Z
- **Completed:** 2026-07-17T18:54:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `remove_candidate_filters`, `resolve_candidate_value`, and `aggregate_filter_value_rows` with GET `/filter-detail` (allowlisted `candidate_id`/`perspective`, empty domain → 200).
- Converted sidebar core + registry filters into grouped launchers while keeping canonical fallback controls until `.js` enhancement.
- Extended `filter_modal.js` with searchable/sortable Description/Record/ROI/Money table, boolean Yes/No radio semantics, lookahead About warnings, and Save→write→submit / Cancel discard.

## Task Commits

Each task was committed atomically:

1. **Task 1: One-pass /filter-detail for categorical and boolean candidates** - `8e843c5` (feat)
2. **Task 2: Grouped launchers + categorical/boolean table UI** - `8ebf819` (feat)

**Plan metadata:** `114efe0` (docs: complete plan)

## Files Created/Modified

- `cfb_system_maker/web.py` - `/filter-detail`, aggregation helpers, list-size bounds, richer feature options metadata
- `cfb_system_maker/templates/index.html` - D-01 launchers + fallback wrappers for core ranges and registry groups
- `cfb_system_maker/static/filter_modal.js` - Categorical/boolean table state machine and commit path
- `cfb_system_maker/static/styles.css` - Table/search/sort and horizontal scroll styles
- `tests/test_filter_modal.py` - filter-detail, launcher, table, Save/Cancel contracts

## Decisions Made

- Boolean rows are always Yes then No (fixed domain) so Save can require exactly one choice.
- Numeric launchers exist and open the shell with live chips; dual-handle/chart UI remains 04-03.
- Feature commit mutates the existing fallback `ff_*` controls for that key so parallel arrays stay aligned.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 04-03 (numeric dual handles, BETWEEN inputs, chart from `chart_points`). Launchers and `/filter-detail` rows already cover numeric candidates.

## Self-Check: PASSED

- FOUND: `cfb_system_maker/web.py` (`/filter-detail`, `aggregate_filter_value_rows`)
- FOUND: `cfb_system_maker/static/filter_modal.js` (search, aria-sort, write*ToForm)
- FOUND: commit `8e843c5`
- FOUND: commit `8ebf819`
- FOUND: `python -m pytest tests/test_filter_modal.py tests/test_web.py tests/test_web_features.py -x` → 58 passed

---
*Phase: 04-filter-popup-modal*
*Completed: 2026-07-17*
