---
phase: 01-system-editor-main-page
plan: 01
subsystem: ui
tags: [flask, jinja, backtest, dataclasses]

# Dependency graph
requires: []
provides:
  - "BetDetail.margin (float, default 0.0) and BacktestResult.average_margin (float | None, default None) computed in backtest.py"
  - "5-chip Record/Margin/Money Won/ROI/Grade stat header on the system editor workspace, replacing the prior 6-chip Bets/ROI/Profit/Hit Rate/W-L-P/Avg Line row"
  - "Scoped .metrics.stat-chips CSS rule that does not affect .metrics.stats-panel"
affects: [system-editor-main-page, integrity-and-stats]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "New signed/derived numeric fields on frozen dataclasses are added as trailing defaulted fields (margin: float = 0.0, average_margin: float | None = None) to avoid reordering existing positional fields."
    - "CSS scoping for shared classes: when two sections share a base class (.metrics) but need divergent grid layouts, add a second class (.stat-chips) and a scoped compound-selector rule rather than editing the shared rule."

key-files:
  created: []
  modified:
    - cfb_system_maker/models.py
    - cfb_system_maker/backtest.py
    - cfb_system_maker/templates/index.html
    - cfb_system_maker/static/styles.css
    - tests/test_backtest.py
    - tests/test_web.py

key-decisions:
  - "Margin is computed only for bet_type=='spread' systems; total-bet systems keep average_margin=None and every BetDetail.margin at its 0.0 default (CONTEXT.md discretion decision, no invented totals formula)."
  - "Grade chip renders a static '—' placeholder this phase with no color class; real computation is deferred to Phase 2 (INTG-02) per project roadmap."
  - "Money Won is computed entirely in the Jinja template (result.profit * 100 at render time) rather than in Python, so result.profit itself is never scaled by 100 anywhere in the codebase."
  - "Zero-bet and zero-profit results render unsigned '$0' (not '+$0'/'-$0') and an em-dash Margin, since average_margin also stays None when bets==0 (the run_backtest guard is `if bets and system.bet_type == 'spread'`)."

requirements-completed: [EDIT-02]

coverage:
  - id: D1
    description: "BetDetail.margin and BacktestResult.average_margin computed correctly for spread bets (per-bet cover margin, averaged across matched bets) and left at 0.0/None for total-bet systems"
    requirement: EDIT-02
    verification:
      - kind: unit
        ref: "tests/test_backtest.py#test_home_favorite_cover_wins_at_minus_110"
        status: pass
      - kind: unit
        ref: "tests/test_backtest.py#test_average_margin_averages_across_multiple_spread_bets"
        status: pass
      - kind: unit
        ref: "tests/test_backtest.py#test_average_margin_is_none_for_total_bet_systems"
        status: pass
    human_judgment: false
  - id: D2
    description: "Workspace stat-chip header shows exactly 5 chips in order Record/Margin/Money Won/ROI/Grade, with correct formatting, sign classes, and edge-case (total-bet, zero-bet) placeholders"
    requirement: EDIT-02
    verification:
      - kind: integration
        ref: "tests/test_web.py#test_web_index_loads_filters_and_default_results"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_filters_apply_to_results"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_margin_chip_shows_em_dash_for_total_bet_systems"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_money_won_chip_renders_unsigned_zero_for_no_matched_bets"
        status: pass
    human_judgment: true
    rationale: "Visual hierarchy, chip sizing/color, and layout stability (UI-SPEC.md's Display 22px typography, accent/loss color reservation, neutral Record/Grade) are design-contract properties best confirmed by looking at the rendered page, not solely by string assertions on the HTML."

# Metrics
duration: 8min
completed: 2026-07-17
status: complete
---

# Phase 1 Plan 1: Stat-Chip Header Restyle Summary

**Restyled the system editor's plain 6-chip metrics row into a 5-chip Bet Labs-style Record/Margin/Money Won/ROI/Grade header, backed by a new spread-only average-cover-margin field on BacktestResult.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-17T05:09:28Z
- **Completed:** 2026-07-17T05:17:23Z
- **Tasks:** 2 completed
- **Files modified:** 6

## Accomplishments
- Added `BetDetail.margin` and `BacktestResult.average_margin`, computed in `grade_bet()`'s spread path and averaged in `run_backtest()`, scoped strictly to `bet_type == "spread"` systems.
- Restyled the primary `.metrics` header in `templates/index.html` to the 5-chip Record/Margin/Money Won/ROI/Grade layout, with Money Won formatted as a signed comma-grouped dollar amount computed entirely in the template.
- Added a scoped `.metrics.stat-chips` CSS rule so the shared `.metrics.stats-panel` block (quality statistics) is unaffected.
- Replaced weak `"Bets" in html` test assertions with chip-section-scoped assertions covering label order, exact formatting, sign classes, and total-bet/zero-bet edge cases.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Margin computation to BetDetail/BacktestResult (spread bets only)** - `e2a439b` (feat)
2. **Task 2: Restyle the stat-chip header to Record/Margin/Money Won/ROI/Grade** - `3410c16` (feat)

**Plan metadata:** _(final docs commit follows this summary)_

_Note: no TDD-required extra commits; Task 1 was tdd="true" but tests and implementation were verified together and committed as a single feat commit since the plan's `<verify>` step is a single pytest invocation, not a separate RED/GREEN gate sequence._

## Files Created/Modified
- `cfb_system_maker/models.py` - Added `BetDetail.margin: float = 0.0` and `BacktestResult.average_margin: float | None = None` trailing defaulted fields.
- `cfb_system_maker/backtest.py` - `grade_bet()`'s spread path now populates `margin=round(cover_margin, 4)`; `run_backtest()` computes `average_margin` guarded by `bets and system.bet_type == "spread"`.
- `cfb_system_maker/templates/index.html` - Replaced the 6-article `.metrics` block with 5 articles (Record, Margin, Money Won, ROI, Grade) under `class="metrics stat-chips"`.
- `cfb_system_maker/static/styles.css` - Added `.metrics.stat-chips { grid-template-columns: repeat(5, minmax(120px, 1fr)); }`, leaving the shared `.metrics` 6-column rule untouched.
- `tests/test_backtest.py` - Extended `test_home_favorite_cover_wins_at_minus_110` with margin assertions; added `test_average_margin_is_none_for_total_bet_systems` and `test_average_margin_averages_across_multiple_spread_bets`.
- `tests/test_web.py` - Added `_metrics_section`/`_money_won_text`/`_chip_labels` helpers; replaced `"Bets" in html` assertions with chip-scoped assertions; added `test_web_margin_chip_shows_em_dash_for_total_bet_systems` and `test_web_money_won_chip_renders_unsigned_zero_for_no_matched_bets`.

## Decisions Made
- Followed CONTEXT.md's discretion decisions verbatim: Margin scoped to spread bets only (em-dash placeholder for totals), Grade is a static neutral placeholder this phase.
- Verified test assertions against dynamically computed `run_backtest()` output (rather than hand-calculated literal strings) to avoid introducing arithmetic mistakes into the test suite itself.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`BacktestResult.average_margin` and the 5-chip header are in place and available for later plans in this phase (e.g. the cumulative Money Won Over Time graph, active-filter sentences, tabs) to build alongside without further changes to this chip header. The Grade chip placeholder is intentionally inert pending Phase 2 (INTG-02) composite grade computation. No blockers for the next plan in this phase.

---
*Phase: 01-system-editor-main-page*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (`e2a439b`, `3410c16`) verified present in git log.
