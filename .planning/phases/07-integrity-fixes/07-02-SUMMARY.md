---
phase: 07-integrity-fixes
plan: 02
subsystem: ui
tags: [flask, filter-modal, javascript, data-integrity]

# Dependency graph
requires: ["07-01"]
provides:
  - "aggregate_filter_value_rows() matched_game_ids out-param: distinct-game denominator computed inside the loop, after the resolve_candidate_value-None skip"
  - "/filter-detail JSON matched_games field"
  - "renderValueTable() row-sum reconciliation caption, suppressed on empty-rows path and when overlappingRows is false"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional keyword-only out-param (matched_game_ids: set[int] | None = None) added to an existing aggregation function to expose an additional derived count without changing its return type or breaking existing call sites"
    - "Reconciliation captions in filter_modal.js are built via document.createElement + .textContent + .appendChild only, matching the file's existing no-innerHTML-concatenation convention"

key-files:
  created: []
  modified:
    - cfb_system_maker/web.py
    - cfb_system_maker/static/filter_modal.js
    - tests/test_filter_modal.py

key-decisions:
  - "matched_game_ids populated inside aggregate_filter_value_rows's existing loop (after the raw is None skip, before tuple fan-out) rather than via a second matches_system pass, so it reports the exact same denominator the bucket loop uses -- these two counts differ whenever resolve_candidate_value returns None for a matched game"
  - "Caption wording uses only state.matchedGames (never the editor's top-line Record chip number), per 07-UI-SPEC.md's Copywriting Contract forbidding a third number in the reconciliation sentence"
  - "Caption placed after setMaxRoiVisible(true) and before the search input in renderValueTable(), so it never renders on the empty-rows ('No values in range') early-return path"

patterns-established:
  - "When exposing a new derived count from an existing aggregation loop, add it as an optional out-param populated in-place rather than changing the return shape -- preserves all existing call-site contracts"

requirements-completed: [FIX-02]

coverage:
  - id: T1
    description: "aggregate_filter_value_rows accepts optional matched_game_ids out-param reporting the distinct-game count (post resolve_candidate_value-None skip), all 4 existing direct-call tests remain green unmodified"
    requirement: "FIX-02"
    verification:
      - kind: unit
        ref: "tests/test_filter_modal.py::test_aggregate_filter_value_rows_matched_game_ids_distinct_count"
        status: pass
    human_judgment: false
  - id: T2
    description: "/filter-detail JSON exposes matched_games as the distinct-game count, smaller than the per-value row sum for overlapping (shared-team/either-perspective) cases"
    requirement: "FIX-02"
    verification:
      - kind: integration
        ref: "tests/test_filter_modal.py::test_filter_detail_overlapping_rows_flag"
        status: pass
    human_judgment: false
  - id: T3
    description: "renderValueTable() renders a self-contained reconciliation caption whenever overlappingRows is true, built via textContent/appendChild only (never innerHTML +=), suppressed on the empty-rows path"
    requirement: "FIX-02"
    verification:
      - kind: unit
        ref: "tests/test_filter_modal.py::test_filter_modal_js_matched_games_overlap_caption_contract, tests/test_filter_modal.py::test_filter_modal_js_matched_games_caption_suppressed_on_empty_rows"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-26
status: complete
---

# Phase 07 Plan 02: Filter-Detail Reconciliation Caption Summary

**Added a `matched_games` distinct-game-count field to `/filter-detail`'s JSON response (computed inside `aggregate_filter_value_rows`'s existing bucket loop) and a self-contained reconciliation caption in `renderValueTable()` that explains, whenever `overlappingRows` is true, why the per-value row sum can exceed the true matched-game count.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-26
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `aggregate_filter_value_rows` (web.py) gained an optional keyword-only `matched_game_ids: set[int] | None` out-param, populated in-place inside the existing `for game in games:` loop right after the `resolve_candidate_value`-returns-`None` skip -- this is the exact denominator the per-value buckets are built from, distinct from (and always <=) a naive `matches_system` count.
- The `/filter-detail` Flask route now passes a fresh `set()` into `aggregate_filter_value_rows` and returns its length as `matched_games` in the JSON payload, alongside the existing `overlapping_rows` flag.
- `filter_modal.js`'s `renderValueTable()` renders a `<p class="filter-modal__hint">` reconciliation caption ("These rows cover N games -- each game counts once per matching value, so rows can sum to more than N.") whenever `state.overlappingRows` is true, built exclusively via `createElement`/`textContent`/`appendChild` (never `innerHTML +=`), and placed after `setMaxRoiVisible(true)` so it never appears on the empty-rows ("No values in range") path.
- Both fetch call sites that already set `state.overlappingRows` (`reloadFeatureDetail()` and `openCandidate()`'s initial fetch) now also set `state.matchedGames = payload.matched_games`, so the caption reads correctly regardless of which path populated state.
- Corrected the stale `applyOverlapNote` doc comment, which previously claimed value-table (categorical) filters "don't need it" -- clarified that the `numeric`-only scoping is specific to Max ROI's window-summing fallback, and that the categorical path now has its own separate reconciliation caption.

## Task Commits

Each task was committed atomically (TDD RED/GREEN pairs):

1. **Task 1 (RED):** `eddd91e` test(07-02): add failing tests for matched_game_ids distinct-game denominator
2. **Task 1 (GREEN):** `5fd6c55` feat(07-02): expose distinct matched_games count from aggregate_filter_value_rows
3. **Task 2 (RED):** `6cb4a82` test(07-02): add failing tests for reconciliation caption in renderValueTable()
4. **Task 2 (GREEN):** `59d229e` feat(07-02): render row-sum reconciliation caption in renderValueTable()

_Note: Task 1 is a `type="tracer"` task. Per the tracer feedback gate (auto mode active), its `<verify>` (`python -m pytest tests/test_filter_modal.py -x -q`) was re-run end-to-end after commit and passed before proceeding to Task 2's expansion work._

## Files Created/Modified

- `cfb_system_maker/web.py` - Added `matched_game_ids` out-param to `aggregate_filter_value_rows`; wired it through the `/filter-detail` route as the `matched_games` JSON field.
- `cfb_system_maker/static/filter_modal.js` - Added `state.matchedGames` assignment at both fetch call sites; added reconciliation caption to `renderValueTable()`; corrected stale `applyOverlapNote` comment.
- `tests/test_filter_modal.py` - Added `test_aggregate_filter_value_rows_matched_game_ids_distinct_count`, extended `test_filter_detail_overlapping_rows_flag` with `matched_games` assertions, added `test_filter_modal_js_matched_games_overlap_caption_contract` and `test_filter_modal_js_matched_games_caption_suppressed_on_empty_rows` (source-inspection style, matching the existing `test_describe_module_has_no_flask_dependency` pattern since there is no JS test harness in this repo).

## Decisions Made

- `matched_game_ids` populated exactly at the point in the loop after the `raw is None` skip and before the tuple/non-tuple value-list branching -- this is the CONTEXT.md/UI-SPEC-locked denominator (distinct games that reached `buckets.setdefault(...)`), not a separately-computed `matches_system` count, which would over-count games that later resolve to `None`.
- Caption wording references only `state.matchedGames`, never the top-line Record chip's number, per 07-UI-SPEC.md's explicit prohibition on introducing a third number (the Record chip reflects the full system; the value table reflects `base_system` with the candidate filter removed).
- Reused the existing `filter-modal__hint` CSS class for the caption rather than inventing a new one, matching FIX-02's typography contract and the empty-rows hint paragraphs already using that class.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched their `<action>`/`<behavior>` specs precisely; no Rule 1-4 auto-fixes were needed.

## Issues Encountered

One self-correction during Task 2: the initial doc-comment rewrite split the literal phrase "row-sum reconciliation caption" across two `//`-prefixed comment lines, which failed the source-inspection test's substring assertion (the test checks the live source text, not semantic meaning). Reworded the comment so the full phrase appears contiguously on one line. This was caught by the RED/GREEN loop itself (test failed, fixed, re-ran green) -- not a deviation from the plan's intent, just a wording adjustment to satisfy the plan's own literal-match verification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- FIX-02 is closed. The `/filter-detail` modal's per-value double-count ambiguity is now disclosed via the `matched_games` field and the caption, without altering the underlying (correct) tuple fan-out logic in `aggregate_filter_value_rows`.
- All 451 tests in the full suite pass (45 in `tests/test_filter_modal.py`); no regressions introduced.
- `git diff cfb_system_maker/static/filter_modal.js | grep "innerHTML +="` returns nothing, confirming the T-07-04 mitigation holds.

---
*Phase: 07-integrity-fixes*
*Completed: 2026-08-26*

## Self-Check: PASSED

All modified files verified present on disk (web.py, filter_modal.js, test_filter_modal.py) and SUMMARY.md written; all 4 task commit hashes (eddd91e, 5fd6c55, 6cb4a82, 59d229e) verified present in git history.
