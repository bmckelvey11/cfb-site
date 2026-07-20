---
phase: 05-dashboard-current-matches
plan: 02
subsystem: backtest
tags: [matching, unplayed-games, dashboard, D-18, D-11]
status: complete

requires:
  - "cfb_system_maker/backtest.py matches_system (existing authoritative matcher)"
provides:
  - "matches_system(..., require_played=False) — the supported way to evaluate unplayed games"
  - "proven equivalence: season slice of an all-time run_backtest == season-restricted run_backtest"
affects:
  - "05-01 upcoming.py (will call matches_system with require_played=False)"
  - "05-03 web.py dashboard (relies on the per-season derivation for timeframe tabs)"

tech-stack:
  added: []
  patterns:
    - "keyword-only flag on an existing path instead of a parallel implementation"
    - "null-fails-closed preserved for spread, total, and feature filters"

key-files:
  created: []
  modified:
    - cfb_system_maker/backtest.py
    - tests/test_backtest.py

decisions:
  - "require_played is keyword-only (`*, require_played: bool = True`) so no existing positional call site can be affected, including the two in files owned by sibling plans."
  - "Only the score guard is conditional. The spread-None and total-None guards stay unconditional — an unplayed game with no posted line is still un-evaluable (D-04)."
  - "Grading functions were not touched and gained no equivalent flag. Current Matches matches but never grades."

metrics:
  duration: ~15 min
  completed: 2026-07-20
  tests_before: 214
  tests_after: 219
---

# Phase 5 Plan 02: Unplayed-Game Matching Summary

Added a keyword-only `require_played` flag to `matches_system` so Current Matches can evaluate unplayed games through the single authoritative matching path, and proved by test that per-season dashboard figures can be derived from one all-time backtest.

## What Was Done

### Task 1 — Failing tests (commit `2b11c26`)

Five tests added to `tests/test_backtest.py`:

- `test_unplayed_game_is_rejected_by_default_and_matched_when_played_not_required` — a `GameRecord` with null `home_points`/`away_points` returns `False` by default and `True` with `require_played=False`.
- `test_require_played_false_still_applies_every_other_filter` — underdog, season, week, and team filters all still reject.
- `test_require_played_false_does_not_relax_the_missing_spread_guard` — a null spread still returns `False`.
- `test_require_played_false_still_evaluates_feature_filters_and_fails_closed_on_null` — feature filters evaluate normally; a null feature value and an absent feature map both fail closed.
- `test_season_slice_of_all_time_backtest_equals_season_restricted_backtest` — across three seasons of five games each, the all-time `bet_details` filtered on `bet.season` equal the season-restricted run by `(game_id, profit)`, and `season_breakdown` reports identical bets/wins/losses/pushes/profit/roi.

No placeholder or fake scores appear anywhere in these tests. An unplayed game carries null points and nothing else.

RED was confirmed as the plan predicted: the four unplayed tests failed with `TypeError: matches_system() got an unexpected keyword argument 'require_played'`, while the season-equivalence test passed immediately against unmodified production code. Per the plan, that test characterizes existing behavior rather than driving a change — it was not treated as a stalled RED gate, and no production code was altered to make it pass.

### Task 2 — Implementation (commit `6ba54ea`)

`matches_system` gained `*, require_played: bool = True` and its leading score guard became `if require_played and (...)`. The complete production diff is the signature lines plus that one guard line plus an explanatory comment.

## Verification

| Check | Result |
|---|---|
| Full suite before change | 214 passed |
| Full suite after change | 219 passed (214 originals + 5 new) |
| Pre-existing assertions edited | 0 |
| `git diff cfb_system_maker/backtest.py` scope | `matches_system` signature + leading guard only |
| `grade_bet` / `_grade_total_bet` modified | No |
| New matcher function added | No |

No existing number moved. The four existing call sites (`run_backtest`, `run_backtest_summary`, `_feature_coverage`, `aggregate_filter_value_rows`) were not edited and continue to reject unplayed games via the default.

## Why This Shape

`matches_system` returning `False` for every unplayed game was the blocking finding of the phase — Current Matches would have rendered zero rows in every state, and no existing test caught it. The alternatives were a parallel matcher (forks the single authoritative path established in Phase 4 D-15, and the fork silently drifts) or placeholder scores (a fake result sitting in a grading path is how a fake result eventually gets counted as real). A default-`True` flag on the one existing function is the change that cannot drift, because there is still only one function.

Making the flag keyword-only matters more than it looks: `feature_map` is passed positionally at every call site, so a positional fourth parameter would have been a live hazard for any future caller, and two of those call sites live in files owned by sibling plans in this wave.

## For Downstream Plans

- **05-01 (`upcoming.py`)**: call `matches_system(game, system, feature_map, require_played=False)`. Do not call `grade_bet` on an upcoming game — it raises, correctly.
- **05-03 (dashboard)**: run `run_backtest` once per system over all seasons and read per-season tab figures off `season_breakdown`, filtering `bet_details` on `bet.season` where individual bets are needed. This is now test-proven equivalent to a season-restricted run, so the timeframe tabs do not need one backtest (including its 1000-iteration permutation test) per system per season.

  One caveat that is correct and should not be "fixed": `result.stats` and `result.grade` on an all-time run are computed over the whole bet population and legitimately differ from a season-restricted run's. Only the bet set and the `season_breakdown` figures are equivalent. Per-season stats/grade are not derivable this way and were not claimed to be.

## Deviations from Plan

None — plan executed exactly as written. No deviation rules were triggered.

## Threat Model Outcomes

| Threat ID | Disposition | Outcome |
|---|---|---|
| T-05-06 | mitigate | `grade_bet` / `_grade_total_bet` unmodified and still raise on null scores. No flag was added to any grading function. No placeholder scores introduced. |
| T-05-07 | mitigate | Default `require_played=True`; full suite green at 219 with zero expectation edits. |
| T-05-08 | mitigate | One function, one flag. No second matcher exists. |
| T-05-SC | accept | No packages installed. |

No new security-relevant surface (no endpoints, auth paths, file access, or schema changes).

## Known Stubs

None.

## Self-Check: PASSED

- `cfb_system_maker/backtest.py` — FOUND
- `tests/test_backtest.py` — FOUND
- `.planning/phases/05-dashboard-current-matches/05-02-SUMMARY.md` — FOUND
- Commit `2b11c26` — FOUND
- Commit `6ba54ea` — FOUND
