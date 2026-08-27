---
phase: 07-integrity-fixes
plan: 01
subsystem: ui
tags: [flask, jinja2, describe, filter-editor]

# Dependency graph
requires: []
provides:
  - "describe() fallback branch for any (op, control) combo not covered by the 4 hand-written sentence branches"
  - "edit_metadata_for_sentence() renderable-shape gate suppressing the Edit affordance for unrenderable combos"
affects: [07-02, 07-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "describe.py fallback sentences use deliberately distinct wording (\"{label} filter applied (value: {value})\") rather than blending in, so an uncovered registry combo stays visibly flagged instead of silently normalizing"

key-files:
  created: []
  modified:
    - cfb_system_maker/describe.py
    - cfb_system_maker/web.py
    - tests/test_describe.py
    - tests/test_web.py

key-decisions:
  - "Fallback sentence text uses filt.value!r (Python repr) per D-locked wording, not a reformatted/joined value — matches CONTEXT.md's explicit instruction not to blend in"
  - "Edit-suppression gate lives in edit_metadata_for_sentence() as an explicit renderable-shape check (numeric needs gte/lte, bool needs eq, categorical needs eq/in) rather than relying on filter_descriptor()'s pre-existing accidental gap"

patterns-established:
  - "When adding a new branch to a groups-of-filters describe() function, mirror any downstream edit-metadata builder with the same op/control shape check so Edit affordances never outrun what has a real modal representation"

requirements-completed: [FIX-01]

coverage:
  - id: D1
    description: "describe() renders a visibly-distinct fallback sentence for any (op, control) filter combo not covered by the 4 hand-written branches, instead of silently returning None"
    requirement: "FIX-01"
    verification:
      - kind: unit
        ref: "tests/test_describe.py::test_describe_uncovered_op_control_combo_renders_distinct_fallback_sentence"
        status: pass
    human_judgment: false
  - id: D2
    description: "The fallback sentence's remove link actually clears the filter (key round-trips through _query_href_removing's existing ff: prefix handling)"
    requirement: "FIX-01"
    verification:
      - kind: integration
        ref: "tests/test_web.py::test_web_uncovered_filter_combo_remove_link_actually_clears_it"
        status: pass
    human_judgment: false
  - id: D3
    description: "The fallback row never renders an Edit button, even though filter_descriptor() resolves the underlying feature — edit_metadata_for_sentence() now explicitly gates on the same (op, control) shapes describe() can render"
    requirement: "FIX-01"
    verification:
      - kind: integration
        ref: "tests/test_web.py::test_web_uncovered_filter_combo_renders_fallback_without_edit_button"
        status: pass
    human_judgment: false
  - id: D4
    description: "The Current Matches dashboard panel (the second render surface reusing describe()) shows the identical fallback sentence for the same uncovered combo, with zero production code changes required"
    requirement: "FIX-01"
    verification:
      - kind: integration
        ref: "tests/test_web.py::test_current_matches_uncovered_filter_combo_renders_fallback_sentence"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-27
status: complete
---

# Phase 07 Plan 01: describe() Fallback Sentence Summary

**Added a deliberately-distinct fallback branch to `_feature_group_sentence` for any `(op, control)` combo the four hand-written branches don't cover, plus an explicit renderable-shape gate in `edit_metadata_for_sentence` so the Edit button never appears for a filter with no modal to edit into.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-27T02:02:00Z (approx)
- **Completed:** 2026-08-27T02:27:14Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `describe.py`'s `_feature_group_sentence` no longer silently drops a sentence for a `feature_ok()`-applied `(op, control)` combo it can't hand-write wording for (e.g. `op="in"` on a `bool` control) — it now returns `f"{label} filter applied (value: {filt.value!r})"`, text that never collides with the 4 existing branches' wording.
- `edit_metadata_for_sentence` in `web.py` now explicitly checks that a feature filter's `(op, control)` shape matches one of the 4 renderable combos (numeric: `gte`/`lte`; bool: `eq`; categorical: `eq`/`in`) before building Edit-launcher metadata — closing the T-07-03 threat where `filter_descriptor()` would return non-None and produce a broken/misleading Edit button for an unrenderable combo.
- Confirmed (via test, zero code changes) that the Current Matches dashboard panel — the second surface that reuses `describe()` — renders the identical fallback sentence, since it only extracts `row["text"]` with no edit/remove enrichment.

## Task Commits

Each task was committed atomically (TDD RED/GREEN per subtask):

1. **Task 1a (describe.py, RED):** `6358f1f` test(07-01): add failing test for describe() fallback sentence on uncovered (op,control) combo
2. **Task 1b (describe.py, GREEN):** `b9370c1` feat(07-01): add distinct fallback sentence for uncovered (op,control) combos in describe()
3. **Task 1c (web.py, RED):** `a3db9a5` test(07-01): add failing test for Edit-button suppression on fallback sentence rows
4. **Task 1d (web.py, GREEN):** `83fe4fe` feat(07-01): suppress Edit affordance for filter combos describe() can't render into a modal
5. **Task 2:** `8f2617d` test(07-01): confirm Current Matches panel renders describe() fallback sentence with zero code changes

**Plan metadata:** (this commit)

_Note: this is a `tdd="true"` tracer task, hence the RED→GREEN commit pairs for both describe.py and web.py before Task 2's confirmation-only test._

## Files Created/Modified
- `cfb_system_maker/describe.py` - Added fallback branch to `_feature_group_sentence` for uncovered `(op, control)` combos
- `cfb_system_maker/web.py` - Added renderable-shape gate to `edit_metadata_for_sentence` before building Edit-launcher metadata for `feature:` candidates
- `tests/test_describe.py` - Added `test_describe_uncovered_op_control_combo_renders_distinct_fallback_sentence`
- `tests/test_web.py` - Added `test_web_uncovered_filter_combo_renders_fallback_without_edit_button`, `test_web_uncovered_filter_combo_remove_link_actually_clears_it`, `test_current_matches_uncovered_filter_combo_renders_fallback_sentence`

## Decisions Made
- Used `filt.value!r` (Python repr, e.g. `[True]`) in the fallback text rather than reformatting the value, per CONTEXT.md's D-locked wording and the explicit instruction that a fallback should read as "we don't have a nice sentence for this yet," not as blended-in natural English.
- Placed the Edit-suppression fix as an explicit shape-check gate (mirroring the same 4 combos `_feature_group_sentence` already special-cases) rather than deriving it indirectly from whether `describe()` would return a sentence for that combo — avoids coupling `web.py` to `describe.py`'s internals while enforcing the identical contract.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched their `<action>`/`<behavior>` specs precisely; no Rule 1-4 auto-fixes were needed.

## Issues Encountered

None. The `neutralSite`/`op="in"` test fixture (bool control + in operator) worked as the plan specified — `feature_ok()`'s generic `_value_matches` already supports `in` on any control via `actual in expected`, confirming this is a real uncovered combo (not a hypothetical one) that `feature_ok()` applies but `describe()` previously dropped silently.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- FIX-01 (T-01-03) is closed. `describe.py` and `web.py` changes are minimal and additive — no impact on 07-02 (filter-detail double-count) or 07-03 (PROJECT.md documentation closure), which touch different code paths.
- All 448 tests in the full suite pass; no regressions introduced.

---
*Phase: 07-integrity-fixes*
*Completed: 2026-08-27*

## Self-Check: PASSED

All created/modified files verified present on disk; all 5 task commit hashes verified present in git history.
