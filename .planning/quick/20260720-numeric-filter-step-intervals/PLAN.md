---
type: quick
slug: numeric-filter-step-intervals
created: 2026-07-20
files_modified:
  - cfb_system_maker/static/filter_modal.js
---

# Quick Task: Numeric filter steps in 0.5 intervals, not continuous

## Problem

The filter popup's numeric controls were built with `step = "any"` in four places
(both dual-range slider handles and both BETWEEN number inputs), so dragging a
numeric filter produced continuous values instead of snapping to a usable
interval. Surfaced during Phase 04 UAT Test 2 (numeric explore).

The legacy sidebar spread/total inputs in `index.html` already use `step="0.5"`,
so the popup was inconsistent with the established half-point convention.

## Decision

A flat `step="0.5"` was rejected: ~10 of the 37 numeric registry features have a
0-1 domain (`running_win_pct`, `running_ats_pct`, `running_success_off/def`,
`pregame_win_prob`, `pregame_home_win_prob`, `havoc_*_rate`, `returning_ppa`,
`returning_usage`). A 0.5 step collapses those sliders to three positions
(0, 0.5, 1.0) — strictly worse than continuous.

Chosen instead: derive the step from the feature's domain span, so betting lines
get the requested 0.5 while rate features keep usable granularity.

| Domain span | Step |
|-------------|------|
| 0 (degenerate) | `any` |
| <= 2 | 0.01 |
| <= 20 | 0.1 |
| <= 1000 | 0.5 |
| > 1000 | 1 |

## Tasks

1. Add `stepForDomain(domainMin, domainMax)` helper beside the existing
   formatters in `filter_modal.js`.
2. Compute `rangeStep` once in the numeric builder and apply it to all four
   inputs (`minRange`, `maxRange`, `minNumber`, `maxNumber`).

## Verification

- `node --check` parses.
- Behavioral assertions run against the helper extracted from the shipped file
  (not a copy) across representative domains.
- Served asset contains the new logic; no `step = "any"` remains.
- Python suite unaffected.
