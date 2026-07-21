---
phase: 01-system-editor-main-page
plan: 03
subsystem: backend
tags: [pure-function, dataclasses, tdd]

# Dependency graph
requires: []
provides:
  - "describe(system: SystemFilter) -> list[dict[str, object]] in cfb_system_maker/describe.py — pure, framework-independent mapping of every active SystemFilter constraint to a plain-English sentence with a stable removal key"
  - "Stable sentence 'key' contract (favorite, underdog, home, away, spread_range, total_range, seasons, weeks, teams, conferences, providers, ff:<feature_key>) that Plan 04's web.py index() route depends on verbatim for remove-links"
affects: [system-editor-main-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure functions with fully defined input/output branch coverage are built test-first (RED commit then GREEN commit) even outside a dedicated TDD-only codebase convention."
    - "Sentence-generation logic for a filter DSL is kept in lockstep with the actual matching logic (matches_system/feature_ok) via explicit branch-mirroring (same bet_type gates, same perspective vocabulary) rather than a separate ad hoc rendering path."

key-files:
  created:
    - cfb_system_maker/describe.py
    - tests/test_describe.py
  modified: []

key-decisions:
  - "Unknown feature_filters keys render a visible 'Unknown filter \"{key}\" is unavailable' sentence instead of being silently dropped, matching features.feature_ok()'s real zero-match behavior for unrecognized keys (01-REVIEWS.md finding #2, blocker)."
  - "Team-scoped feature sentences get a perspective-word prefix (Home/Away/Bet-side/Opponent/Either team's) sourced from a fixed _PERSPECTIVE_PREFIX map that mirrors features._perspective_to_side's vocabulary exactly; non-team-scoped features and the default 'single' perspective get no prefix (01-REVIEWS.md finding #3)."
  - "favorite/underdog/spread_range sentences are gated behind two separate `if system.bet_type == \"spread\":` blocks (rather than one combined block) so canonical output order (favorite, underdog, home, away, spread_range, ...) is preserved without pulling spread_range ahead of home/away."
  - "total_range is never bet_type-gated, matching matches_system()'s min_total/max_total checks appearing in both the spread and total branches."

requirements-completed: [EDIT-03]

coverage:
  - id: D1
    description: "describe() maps every SystemFilter field (favorite/underdog/home/away/spread_range/total_range/seasons/weeks/teams/conferences/providers) and feature_filters entries to sentence/key dicts in fixed order, matching matches_system()'s actual filter semantics including bet_type gating"
    requirement: EDIT-03
    verification:
      - kind: unit
        ref: "tests/test_describe.py#test_describe_spread_range_between_at_least_at_most_and_exact"
        status: pass
      - kind: unit
        ref: "tests/test_describe.py#test_describe_spread_fields_ignored_for_total_bet_type"
        status: pass
      - kind: unit
        ref: "tests/test_describe.py#test_describe_total_range_applies_regardless_of_bet_type"
        status: pass
      - kind: unit
        ref: "tests/test_describe.py#test_describe_output_order_is_fixed_and_deterministic"
        status: pass
    human_judgment: false
  - id: D2
    description: "Unknown feature_filters keys and team-scoped perspective prefixes render correctly per 01-REVIEWS.md findings #2 and #3"
    requirement: EDIT-03
    verification:
      - kind: unit
        ref: "tests/test_describe.py#test_describe_unknown_feature_key_renders_warning_sentence"
        status: pass
      - kind: unit
        ref: "tests/test_describe.py#test_describe_feature_filter_perspective_prefixes_team_scoped_label"
        status: pass
      - kind: unit
        ref: "tests/test_describe.py#test_describe_feature_filter_perspective_single_default_has_no_prefix_even_when_team_scoped"
        status: pass
      - kind: unit
        ref: "tests/test_describe.py#test_describe_feature_filter_perspective_ignored_for_non_team_scoped"
        status: pass
    human_judgment: false
  - id: D3
    description: "describe() is pure and framework-independent (no flask/request dependency, deterministic across repeat calls), and does not crash on non-finite crafted input"
    requirement: EDIT-03
    verification:
      - kind: unit
        ref: "tests/test_describe.py#test_describe_module_has_no_flask_dependency"
        status: pass
      - kind: unit
        ref: "tests/test_describe.py#test_describe_is_pure_no_side_effects_call_twice_returns_equal_lists"
        status: pass
      - kind: unit
        ref: "tests/test_describe.py#test_describe_non_finite_numbers_do_not_crash"
        status: pass
    human_judgment: false

# Metrics
duration: 4min
completed: 2026-07-17
status: complete
---

# Phase 1 Plan 3: Plain-English Filter Sentences (describe()) Summary

**Implemented `describe(system) -> list[dict]` as a pure, framework-independent function mapping every active SystemFilter constraint (core fields + feature_filters) to a plain-English sentence with a stable removal key, built test-first with 19 RED tests then a single GREEN implementation.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-07-17T01:18:59-04:00 (previous plan's docs commit)
- **Completed:** 2026-07-17T01:22:06-04:00
- **Tasks:** 2 completed
- **Files created:** 2

## Accomplishments
- Added `tests/test_describe.py` with 19 test functions covering every op-phrase branch (bool/categorical/numeric, eq/in/gte/lte), bet_type gating for favorite/underdog/spread_range vs. always-active total_range, sorted-set-join sentences for seasons/weeks/teams/conferences/providers, the unknown-feature-key warning sentence, perspective-prefix wording for team-scoped features, deterministic output ordering, purity, framework-independence, and non-finite-number safety.
- Added `cfb_system_maker/describe.py` implementing `describe()`, a private `_fmt_num()` helper (strips trailing `.0`), a private `_range_sentence()` helper shared by spread_range/total_range, and a module-level `_PERSPECTIVE_PREFIX` map.
- Verified `describe()`'s bet_type gating and perspective handling mirror `matches_system()`/`resolve_feature_value()`'s actual semantics exactly, closing 01-REVIEWS.md findings #2 (blocker: silent unknown-key drop) and #3 (high: missing perspective naming).
- Full suite (117 tests) passes with no regressions.

## Task Commits

Each task was committed atomically per the RED/GREEN TDD gate:

1. **Task 1 (RED): Write the full failing test suite for describe()** - `0c45274` (test)
2. **Task 2 (GREEN): Implement describe() to pass the full test suite** - `269d96b` (feat)

**Plan metadata:** _(final docs commit follows this summary)_

## TDD Gate Compliance

RED gate (`test(01-03): ...`, commit `0c45274`) confirmed via `pytest tests/test_describe.py -q` failing with `ModuleNotFoundError: No module named 'cfb_system_maker.describe'` before any implementation existed. GREEN gate (`feat(01-03): ...`, commit `269d96b`) confirmed via the same command passing all 19 tests. No REFACTOR commit was needed — the GREEN implementation required no follow-up cleanup.

## Files Created/Modified
- `tests/test_describe.py` - New file. 19 test functions constructing `SystemFilter`/`FeatureFilter` directly (no fixtures/mocks), following `tests/test_backtest.py`'s existing dataclass-construction style.
- `cfb_system_maker/describe.py` - New file. `describe(system) -> list[dict[str, object]]`, `_fmt_num()`, `_range_sentence()`, `_PERSPECTIVE_PREFIX`. Imports only `cfb_system_maker.features.FEATURE_BY_KEY` and `cfb_system_maker.models.SystemFilter` — no flask.

## Decisions Made
- Factored the spread_range/total_range four-way (between/at-least/at-most/exactly) branching into a shared private `_range_sentence()` helper rather than duplicating it, since both ranges use the identical sub-case structure with only the noun/key differing. This is a plan-internal implementation detail, not a deviation — the public `describe()` contract and all sentence text/keys match the plan's task instructions exactly.
- Used `is_integer()` in `_fmt_num()` rather than a string-suffix strip, so `nan`/`inf` inputs from crafted query values render as `"nan"`/`"inf"` strings instead of raising, per the plan's explicit non-finite-safety requirement.

## Deviations from Plan

None - plan executed exactly as written. (One minor internal refactor — extracting `_range_sentence()` as a shared helper for the spread/total range branches — stayed within the plan's specified text/key output and did not change any test-visible behavior.)

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`describe()` is ready for Plan 04 (`01-04-PLAN.md`) to import and call from `web.py`'s `index()` route, pairing each sentence's `key` with a `_REMOVE_PARAM_MAP` lookup to build remove-links. The exact key strings (`favorite`, `underdog`, `home`, `away`, `spread_range`, `total_range`, `seasons`, `weeks`, `teams`, `conferences`, `providers`, `ff:<feature_key>`) are stable and unchanged from the plan's contract. No blockers for the next plan in this phase.

---
*Phase: 01-system-editor-main-page*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created files verified present on disk (`cfb_system_maker/describe.py`, `tests/test_describe.py`); both task commits (`0c45274`, `269d96b`) verified present in git log.
