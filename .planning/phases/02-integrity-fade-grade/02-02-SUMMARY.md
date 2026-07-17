---
phase: 02-integrity-fade-grade
plan: 02
subsystem: backtest-engine
tags: [python, flask, dataclasses, jinja2, stats]

# Dependency graph
requires:
  - phase: 02-01
    provides: "SystemFilter.fade field -- count_overfit_filters must know not to count it (D-06); shared file set (models.py, backtest.py, templates/index.html, tests/test_backtest.py, tests/test_web.py) drove Wave 2 ordering, not a content dependency"
provides:
  - "BacktestResult.grade: str | None -- new trailing field populated by run_backtest"
  - "compute_grade(result, system) -> str | None -- equal-weighted composite of 5 sub-scores bucketed into A/B/C/D/F, or None for zero matched bets"
  - "_sample_size_score, _roi_significance_score, _consistency_score, _permutation_score, _overfit_score -- 5 pure sub-score helpers with documented threshold boundaries"
  - "count_overfit_filters(system) -- D-06 counting rule (per-field=1, teams/conferences/seasons/weeks/in-list values counted individually), fade never counted"
  - "Grade chip in templates/index.html renders the computed letter or em-dash fallback"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "compute_grade is called once inside run_backtest via dataclasses.replace(result, grade=compute_grade(result, system)) after the base BacktestResult is constructed -- avoids the circular dependency of needing result.stats/season_breakdown before they exist, and keeps compute_grade a pure function of an already-complete result."
    - "Sub-score boundary style: functions read as a cascading if/elif ladder, each branch's threshold check written 'if metric < X: return lower_tier', so the value AT the threshold falls into the next (higher) tier -- consistent across all 5 helpers."

key-files:
  created: []
  modified:
    - cfb_system_maker/models.py
    - cfb_system_maker/backtest.py
    - cfb_system_maker/templates/index.html
    - tests/test_backtest.py
    - tests/test_web.py

key-decisions:
  - "Sample-size sub-score uses stats.wilson_low - stats.break_even_rate (margin), floored by decided bet count < 30, per D-04's explicit wilson_low/wilson_high naming -- not a raw bet-count-only tier as 02-RESEARCH.md's Pattern 2 example code showed. This plan's Task 1 action superseded the research doc for this one sub-score, per the plan's own annotation."
  - "Grade chip markup mirrors the Margin chip's existing {% if %}/{% else %} conditional style exactly, rendering result.grade through plain Jinja auto-escaping with no |safe filter."

patterns-established:
  - "New composite/derived BacktestResult fields should be wired via dataclasses.replace on the already-built result, not by threading extra parameters into the constructor call -- keeps the base construction call from growing new circular data dependencies."

requirements-completed: [INTG-02]

coverage:
  - id: D1
    description: "compute_grade and its 5 sub-score helpers return the documented value at and one step beyond each threshold boundary"
    requirement: "INTG-02"
    verification:
      - kind: unit
        ref: "tests/test_backtest.py#test_grade_sample_size_score_boundaries"
        status: pass
      - kind: unit
        ref: "tests/test_backtest.py#test_grade_roi_significance_score_boundaries"
        status: pass
      - kind: unit
        ref: "tests/test_backtest.py#test_grade_consistency_score_boundaries"
        status: pass
      - kind: unit
        ref: "tests/test_backtest.py#test_grade_permutation_score_boundaries"
        status: pass
      - kind: unit
        ref: "tests/test_backtest.py#test_grade_overfit_score_boundaries"
        status: pass
    human_judgment: false
  - id: D2
    description: "count_overfit_filters follows D-06's exact counting rule and never counts system.fade"
    requirement: "INTG-02"
    verification:
      - kind: unit
        ref: "tests/test_backtest.py#test_count_overfit_filters_follows_d06_counting_rule"
        status: pass
    human_judgment: false
  - id: D3
    description: "compute_grade returns None for zero matched bets (distinct from a graded F) and the correct letter for representative high/low composite fixtures"
    requirement: "INTG-02"
    verification:
      - kind: unit
        ref: "tests/test_backtest.py#test_compute_grade_returns_none_for_zero_matched_bets"
        status: pass
      - kind: unit
        ref: "tests/test_backtest.py#test_compute_grade_returns_a_for_all_high_subscores"
        status: pass
      - kind: unit
        ref: "tests/test_backtest.py#test_compute_grade_returns_f_for_all_low_subscores"
        status: pass
    human_judgment: false
  - id: D4
    description: "run_backtest populates BacktestResult.grade via dataclasses.replace without perturbing any pre-existing field (bets/wins/losses/season_breakdown unchanged)"
    requirement: "INTG-02"
    verification:
      - kind: unit
        ref: "tests/test_backtest.py#test_run_backtest_populates_grade_field"
        status: pass
    human_judgment: false
  - id: D5
    description: "Grade chip renders the computed letter for systems with matched bets, and the em-dash fallback for zero matched bets (with and without fade), through plain Jinja auto-escaping"
    requirement: "INTG-02"
    verification:
      - kind: integration
        ref: "tests/test_web.py#test_web_index_loads_filters_and_default_results"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_grade_chip_renders_computed_letter_for_default_system"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_grade_chip_renders_em_dash_for_zero_matched_bets"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-17
status: complete
---

# Phase 2 Plan 2: System Grade Summary

**Composite A-F System Grade combining Wilson-bound sample-size significance, ROI z-score, season sign-consistency, permutation p-value, and a D-06 overfit penalty, wired into the Grade chip Phase 1 reserved as a placeholder.**

## Performance

- **Duration:** ~9 min
- **Completed:** 2026-07-17
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `BacktestResult.grade: str | None = None` added as the new trailing field, populated by `run_backtest` via `dataclasses.replace(result, grade=compute_grade(result, system))` -- zero perturbation to any other field
- `compute_grade(result, system) -> str | None` combines 5 pure sub-score helpers (`_sample_size_score`, `_roi_significance_score`, `_consistency_score`, `_permutation_score`, `_overfit_score`) via equal-weighted average into A/B/C/D/F via `_GRADE_BANDS`, returning `None` (not `F`) for zero matched bets
- `_sample_size_score` implements D-04's literal `wilson_low`/`break_even_rate` margin design (superseding 02-RESEARCH.md's raw-bet-count-only example), floored by `decided < 30` before any margin is read
- `count_overfit_filters(system)` implements D-06's exact counting rule -- boolean/bound/provider fields count 1, set-valued fields (teams/conferences/seasons/weeks) and `op="in"` feature-filter lists count every selected value, `fade` is never counted
- Grade chip in `templates/index.html` renders `result.grade` (or the em-dash fallback) through the same conditional style as the existing Margin chip, with no `|safe` filter

## Task Commits

Each task was committed atomically (Task 1 followed the RED/GREEN TDD cycle per `tdd="true"`):

1. **Task 1 (RED): Add failing tests for compute_grade sub-scores and wiring** - `c9bfc4c` (test)
2. **Task 1 (GREEN): Implement compute_grade + 5 sub-score helpers + count_overfit_filters + BacktestResult.grade wiring** - `4c10756` (feat)
3. **Task 2: Render the Grade chip and cover zero-bet/fade em-dash cases** - `c95c97b` (feat)

## Files Created/Modified
- `cfb_system_maker/models.py` - `BacktestResult.grade: str | None = None` trailing field
- `cfb_system_maker/backtest.py` - `_GRADE_BANDS`, 5 sub-score helpers, `count_overfit_filters`, `compute_grade`; `run_backtest`'s return rewired through `dataclasses.replace`
- `cfb_system_maker/templates/index.html` - Grade chip conditional render (mirrors Margin chip's `{% if %}/{% else %}` style)
- `tests/test_backtest.py` - 11 new tests: 5 sub-score boundary tests, `count_overfit_filters` D-06 rule test, `compute_grade` zero-bet/A/F composite tests, `run_backtest` wiring test
- `tests/test_web.py` - updated the pre-existing default-system em-dash assertion to a computed-grade assertion; 2 new tests (computed-letter render, zero-bet em-dash with and without fade)

## Decisions Made
- Followed the plan's explicit supersession note: `_sample_size_score` takes `(decided, wilson_low, break_even_rate)` per D-04, not `_sample_size_score(decided)` as 02-RESEARCH.md's Pattern 2 example showed -- the plan's Task 1 `<action>` is authoritative here.
- Sub-score boundary tests for `_sample_size_score` pass `break_even_rate=0.0` so `margin == wilson_low` exactly (no intervening floating-point addition), avoiding a boundary-equality trap flagged during pre-implementation review (advisor call) -- the other 4 sub-score tests pass threshold literals directly and needed no such adjustment.

## Deviations from Plan
None - plan executed exactly as written. The plan's Task 2 acceptance criteria describes "three grade-named tests" matching `pytest -k grade`, but only 2 of the 3 relevant tests contain "grade" in their name (the third, `test_web_index_loads_filters_and_default_results`, is a pre-existing test whose name predates this phase and wasn't renamed, per the surgical-changes principle of touching only what the task requires). `pytest tests/test_web.py -k grade -x` passes its 2 matching tests; all 3 grade-relevant tests pass under the full suite run.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 2 (integrity-fade-grade) is now complete: both INTG-01 (Fade toggle) and INTG-02 (System Grade) are implemented and tested.
- Full test suite (160 tests) passes with zero failures.
- End-of-phase human-verify (per `human_verify_mode: end-of-phase` config) should include a visual check of the Grade chip rendering a real letter in the browser, alongside the Fade checkbox visual check carried over from 02-01's summary.

---
*Phase: 02-integrity-fade-grade*
*Completed: 2026-07-17*

## Self-Check: PASSED

All 5 modified source/test files and this SUMMARY.md verified present on disk. All 3 task commits (`c9bfc4c`, `4c10756`, `c95c97b`) verified present in git history.
