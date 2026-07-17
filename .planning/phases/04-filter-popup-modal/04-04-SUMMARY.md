---
phase: 04-filter-popup-modal
plan: 04
subsystem: ui
tags: [flask, jinja, dialog, edit-prefill, perspective, debounce, AbortController, a11y, vanilla-js]

requires:
  - phase: 04-filter-popup-modal
    provides: numeric/categorical modal shell, Save→GET, describe BETWEEN coalesce
provides:
  - Active-filter Edit control with server edit metadata prefill
  - Team-scoped Bet-side / Opponent / Either perspective control + D-14 defaults
  - Live /api/backtest debounce (250ms), AbortController, generation guard, Retry
  - Responsive ≤900px About stack + focus-visible
affects:
  - Phase 4 verification / end-of-phase human checks

tech-stack:
  added: []
  patterns:
    - Sentence enrichment attaches edit metadata beside remove_href (D-03)
    - Live fetch identity via liveGeneration + AbortController before chips/Save
    - Perspective segmented control refetches /filter-detail on change

key-files:
  created: []
  modified:
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/index.html
    - cfb_system_maker/static/filter_modal.js
    - cfb_system_maker/static/styles.css
    - tests/test_filter_modal.py

key-decisions:
  - "edit_metadata_for_sentence maps D-01 candidates only; favorite/underdog/home/away stay Remove-only"
  - "Allowed perspectives include bet_side/opponent/either plus home/away for committed edit preservation"
  - "LIVE_DEBOUNCE_MS = 250; Retry uses immediate refresh without mutating filters-form"

patterns-established:
  - "Edit buttons reuse openCandidate via data-candidate-id + data-label for title"
  - "Save stays disabled until liveOk for current generation; failures keep lastSummary"
  - "Backdrop click preventDefault/stopPropagation; Escape/cancel → discardAndClose + focus restore"

requirements-completed: [MODAL-01, MODAL-02, MODAL-06]

duration: 7min
completed: 2026-07-17
status: complete
---

# Phase 4 Plan 04: Edit Prefill, Perspective, Live Reliability Summary

**Active-filter Edit opens the shared modal prefilled; team-scoped filters use Bet-side/Opponent/Either with spread→bet_side and total→either defaults; live chips debounce at 250ms with AbortController, generation guard, Updating…, and Retry without form mutation.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-17T19:06:48Z
- **Completed:** 2026-07-17T19:13:07Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Edit control on modal-eligible sentences with `edit_metadata_for_sentence` (candidate_id, perspective, bounds/values); Remove remains independent.
- Perspective segmented control for team-scoped features; new filters default from `bet_type`; edits preserve committed perspective.
- Live path: 250ms debounce, AbortController, generation check before applying metrics/enabling Save; error copy + Retry; backdrop non-dismiss; focus-visible + ≤900px stack.

## Task Commits

Each task was committed atomically:

1. **Task 1: Active-filter Edit prefill + perspective defaults** - `92395bf` (test RED) + `ff8d4e5` (feat GREEN)
2. **Task 2: Live debounce/stale/retry, a11y focus, responsive layout** - `49c97b5` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `cfb_system_maker/web.py` - `default_perspective`, `edit_metadata_for_sentence`, sentence enrichment on index
- `cfb_system_maker/templates/index.html` - Edit button beside Remove with data-* prefill attrs
- `cfb_system_maker/static/filter_modal.js` - perspective UI, debounce/AbortController/generation, Retry, focus lifecycle
- `cfb_system_maker/static/styles.css` - Edit/perspective/retry styles, focus-visible, 900px stack
- `tests/test_filter_modal.py` - Edit/perspective/prefill + debounce/stale/retry/focus source contracts

## Decisions Made

- Global toggles (favorite/underdog/home/away) intentionally omit Edit; they stay one-click Remove only.
- Modal primary perspective set is Bet-side / Opponent / Either; home/away remain allowlisted so committed edits still validate.
- Escape routes through dialog `cancel` → `discardAndClose` (same as Cancel/close).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 implementation plans 01–04 complete; ready for phase verification / end-of-phase human checks (keyboard, stale/retry, narrow layout).
- Automated: `python -m pytest tests/test_filter_modal.py tests/test_web.py tests/test_web_features.py -x` and full `python -m pytest -q` (213 passed).

## Self-Check: PASSED

- `04-04-SUMMARY.md` present
- Commits `92395bf`, `ff8d4e5`, `49c97b5` present in git log

---
*Phase: 04-filter-popup-modal*
*Completed: 2026-07-17*
